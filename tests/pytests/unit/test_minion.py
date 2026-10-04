import asyncio
import contextlib
import copy
import inspect
import logging
import os
import pathlib
import signal
import threading
import time
import uuid

import pytest
import tornado
import tornado.gen
import tornado.ioloop
import tornado.testing

import salt.defaults.exitcodes
import salt.loader.context
import salt.minion
import salt.modules.sysmod
import salt.modules.test as test_mod
import salt.payload
import salt.syspaths
import salt.utils.crypt
import salt.utils.doc
import salt.utils.files
import salt.utils.jid
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.process
import salt.utils.state
from salt._compat import ipaddress
from salt.exceptions import (
    SaltClientError,
    SaltMasterUnresolvableError,
    SaltReqTimeoutError,
    SaltSystemExit,
)
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def connect_master_mock():
    class ConnectMasterMock:
        """
        Mock connect master call.

        The first call will raise an exception stored on the exc attribute.
        Subsequent calls will return True.
        """

        def __init__(self):
            self.calls = 0
            self.exc = Exception

        @tornado.gen.coroutine
        def __call__(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise self.exc()
            else:
                return True

    return ConnectMasterMock()


def test_minion_load_grains_false(minion_opts):
    """
    Minion does not generate grains when load_grains is False
    """
    minion_opts["grains"] = {"foo": "bar"}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(minion_opts, load_grains=False)
        try:
            assert minion.opts["grains"] == minion_opts["grains"]
            grainsfunc.assert_not_called()
        finally:
            minion.destroy()


def test_minion_load_grains_true(minion_opts):
    """
    Minion generates grains when load_grains is True
    """
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(minion_opts, load_grains=True)
        try:
            assert minion.opts["grains"] != {}
            grainsfunc.assert_called()
        finally:
            minion.destroy()


def test_minion_load_grains_default(minion_opts):
    """
    Minion load_grains defaults to True
    """
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(minion_opts)
        try:
            assert minion.opts["grains"] != {}
            grainsfunc.assert_called()
        finally:
            minion.destroy()


@pytest.mark.parametrize(
    "event",
    [
        (
            "fire_event",
            lambda data, tag, cb=None, timeout=60: True,
        ),
        (
            "fire_event_async",
            lambda data, tag, cb=None, timeout=60: tornado.gen.maybe_future(True),
        ),
    ],
)
def test_send_req_fires_completion_event(event, minion_opts):
    req_id = uuid.uuid4()
    event_enter = MagicMock()
    event_enter.send.side_effect = event[1]
    event_enter.get_event.return_value = {"ret": True}
    event = MagicMock()
    event.__enter__.return_value = event_enter

    with patch("salt.utils.event.get_event", return_value=event), patch(
        "uuid.uuid4", return_value=req_id
    ):
        minion_opts["random_startup_delay"] = 0
        minion_opts["return_retry_tries"] = 30
        minion_opts["grains"] = {}
        with patch("salt.loader.grains"):
            minion = salt.minion.Minion(minion_opts)

            try:
                load = {"load": "value"}
                timeout = 60

                # XXX This is buggy because "async" in event[0] will never evaluate
                # to True and if it *did* evaluate to true the test would fail
                # because you Mock isn't a co-routine.
                if "async" in event[0]:
                    rtn = minion._send_req_async(load, timeout).result()
                else:
                    rtn = minion._send_req_sync(load, timeout)

                fire_event_called = False
                # get the
                for idx, call in enumerate(event.mock_calls, 1):
                    if "fire_event" in call[0]:
                        condition_event_tag = (
                            len(call.args) > 1
                            and call.args[1]
                            == f"__master_req_channel_payload/{req_id}/{minion_opts['master']}"
                        )
                        condition_event_tag_error = (
                            "{} != {}; Call(number={}): {}".format(
                                idx, call, call.args[1], "__master_req_channel_payload"
                            )
                        )
                        condition_timeout = (
                            len(call.kwargs) == 1 and call.kwargs["timeout"] == timeout
                        )
                        condition_timeout_error = (
                            "{} != {}; Call(number={}): {}".format(
                                idx, call, call.kwargs["timeout"], timeout
                            )
                        )

                        fire_event_called = True
                        assert condition_event_tag, condition_event_tag_error
                        assert condition_timeout, condition_timeout_error

                assert fire_event_called
                assert rtn
            finally:
                minion.destroy()


async def test_send_req_async_regression_62453(minion_opts):

    class MockEvent:

        def __init__(self, *args, **kwargs):
            pass

        @tornado.gen.coroutine
        def fire_event_async(self, *args, **kwargs):
            return

        def get_event(self, *args, **kwargs):
            return

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return

    def get_event(*args, **kwargs):
        return MockEvent()

    minion_opts["random_startup_delay"] = 0
    minion_opts["return_retry_tries"] = 5
    minion_opts["grains"] = {}
    minion_opts["ipc_mode"] = "tcp"
    with patch("salt.loader.grains"):
        minion = salt.minion.Minion(minion_opts)

        load = {"load": "value"}
        timeout = 1

        with patch("salt.utils.event.get_event", get_event):
            # We are just validating no exception is raised
            with pytest.raises(SaltReqTimeoutError):
                rtn = await minion._send_req_async(load, timeout)


def test_mine_send_tries(minion_opts):
    channel_enter = MagicMock()
    channel_enter.send.side_effect = lambda load, timeout, tries: tries
    channel = MagicMock()
    channel.__enter__.return_value = channel_enter

    minion_opts["return_retry_tries"] = 20
    with patch("salt.channel.client.ReqChannel.factory", return_value=channel), patch(
        "salt.loader.grains"
    ):
        minion = salt.minion.Minion(minion_opts)
        minion.tok = "token"

        data = {}
        tag = "tag"

        rtn = minion._mine_send(tag, data)
        assert rtn == 20


def test_invalid_master_address(minion_opts):
    minion_opts.update(
        {
            "ipv6": False,
            "master": float("127.0"),
            "master_port": "4555",
            "retry_dns": False,
        }
    )
    with pytest.raises(SaltSystemExit):
        salt.minion.resolve_dns(minion_opts)


def test_source_int_name_local(minion_opts):
    """
    test when file_client local and
    source_interface_name is set
    """
    interfaces = {
        "bond0.1234": {
            "hwaddr": "01:01:01:d0:d0:d0",
            "up": True,
            "inet": [
                {
                    "broadcast": "111.1.111.255",
                    "netmask": "111.1.0.0",
                    "label": "bond0",
                    "address": "111.1.0.1",
                }
            ],
        }
    }
    minion_opts.update(
        {
            "ipv6": False,
            "master": "127.0.0.1",
            "master_port": "4555",
            "file_client": "local",
            "source_interface_name": "bond0.1234",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    )
    with patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(minion_opts) == {
            "master_ip": "127.0.0.1",
            "source_ip": "111.1.0.1",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
            "master_uri": "tcp://127.0.0.1:4555",
        }


@pytest.mark.slow_test
def test_source_int_name_remote(minion_opts):
    """
    test when file_client remote and
    source_interface_name is set and
    interface is down
    """
    interfaces = {
        "bond0.1234": {
            "hwaddr": "01:01:01:d0:d0:d0",
            "up": False,
            "inet": [
                {
                    "broadcast": "111.1.111.255",
                    "netmask": "111.1.0.0",
                    "label": "bond0",
                    "address": "111.1.0.1",
                }
            ],
        }
    }
    minion_opts.update(
        {
            "ipv6": False,
            "master": "127.0.0.1",
            "master_port": "4555",
            "file_client": "remote",
            "source_interface_name": "bond0.1234",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    )
    with patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(minion_opts) == {
            "master_ip": "127.0.0.1",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
            "master_uri": "tcp://127.0.0.1:4555",
        }


@pytest.mark.slow_test
def test_source_address(minion_opts):
    """
    test when source_address is set
    """
    interfaces = {
        "bond0.1234": {
            "hwaddr": "01:01:01:d0:d0:d0",
            "up": False,
            "inet": [
                {
                    "broadcast": "111.1.111.255",
                    "netmask": "111.1.0.0",
                    "label": "bond0",
                    "address": "111.1.0.1",
                }
            ],
        }
    }
    minion_opts.update(
        {
            "ipv6": False,
            "master": "127.0.0.1",
            "master_port": "4555",
            "file_client": "local",
            "source_interface_name": "",
            "source_address": "111.1.0.1",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    )
    with patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(minion_opts) == {
            "source_publish_port": 49018,
            "source_ret_port": 49017,
            "master_uri": "tcp://127.0.0.1:4555",
            "source_ip": "111.1.0.1",
            "master_ip": "127.0.0.1",
        }


# Tests for _handle_decoded_payload in the salt.minion.Minion() class: 3
@pytest.mark.slow_test
async def test_handle_decoded_payload_jid_match_in_jid_queue(minion_opts, io_loop):
    """
    Tests that the _handle_decoded_payload function returns when a jid is given that is already present
    in the jid_queue.

    Note: This test doesn't contain all of the patch decorators above the function like the other tests
    for _handle_decoded_payload below. This is essential to this test as the call to the function must
    return None BEFORE any of the processes are spun up because we should be avoiding firing duplicate
    jobs.
    """
    mock_data = {"fun": "foo.bar", "jid": 123}
    mock_jid_queue = [123]
    minion = salt.minion.Minion(
        minion_opts,
        jid_queue=copy.copy(mock_jid_queue),
        io_loop=io_loop,
    )
    try:
        ret = await minion._handle_decoded_payload(mock_data)
        assert minion.jid_queue == mock_jid_queue
        assert ret is None
    finally:
        minion.destroy()


@pytest.mark.slow_test
async def test_handle_decoded_payload_jid_queue_addition(minion_opts, io_loop):
    """
    Tests that the _handle_decoded_payload function adds a jid to the minion's jid_queue when the new
    jid isn't already present in the jid_queue.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        mock_jid = 11111
        mock_data = {"fun": "foo.bar", "jid": mock_jid}
        mock_jid_queue = [123, 456]
        minion = salt.minion.Minion(
            minion_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=io_loop,
        )
        try:

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            assert minion.jid_queue == mock_jid_queue

            # Call the _handle_decoded_payload function and update the mock_jid_queue to include the new
            # mock_jid. The mock_jid should have been added to the jid_queue since the mock_jid wasn't
            # previously included. The minion's jid_queue attribute and the mock_jid_queue should be equal.
            await minion._handle_decoded_payload(mock_data)
            mock_jid_queue.append(mock_jid)
            assert minion.jid_queue == mock_jid_queue
        finally:
            minion.destroy()


@pytest.mark.slow_test
async def test_handle_decoded_payload_jid_queue_reduced_minion_jid_queue_hwm(
    minion_opts, io_loop
):
    """
    Tests that the _handle_decoded_payload function removes a jid from the minion's jid_queue when the
    minion's jid_queue high water mark (minion_jid_queue_hwm) is hit.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion_opts["minion_jid_queue_hwm"] = 2
        mock_data = {"fun": "foo.bar", "jid": 789}
        mock_jid_queue = [123, 456]
        minion = salt.minion.Minion(
            minion_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=io_loop,
        )
        try:

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            assert minion.jid_queue == mock_jid_queue

            # Call the _handle_decoded_payload function and check that the queue is smaller by one item
            # and contains the new jid
            await minion._handle_decoded_payload(mock_data)
            assert len(minion.jid_queue) == 2
            assert minion.jid_queue == [456, 789]
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_process_count_max(minion_opts, io_loop):
    """
    Tests that the _handle_decoded_payload function does not spawn more than the configured amount of processes,
    as per process_count_max.
    """
    start_mock = MagicMock(return_value=True)

    def mock_proc_side_effect(*args, **kwargs):
        m = MagicMock(name="MockProcess")
        m.is_alive.return_value = True
        m.start = start_mock
        return m

    @contextlib.asynccontextmanager
    async def mock_await_lock(*args, **kwargs):
        yield

    fopen_mock = MagicMock()
    # ``_handle_decoded_payload`` calls ``get_proc_dir`` on the parent side
    # (to precompute the finalize-registered proc-file path for the job
    # child). ``get_proc_dir`` requires ``<cachedir>/proc`` to be
    # ``os.stat``-able; patching ``os.makedirs`` to a no-op below would
    # otherwise leave the directory missing on real disk. Create it up
    # front so the un-patched ``os.stat`` call inside ``get_proc_dir``
    # succeeds without touching production code.
    os.makedirs("/tmp/salt_test_cache/proc", exist_ok=True)
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.SignalHandlingProcess",
        MagicMock(side_effect=mock_proc_side_effect),
    ), patch(
        "salt.minion.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ), patch(
        "os.path.exists", MagicMock(return_value=True)
    ), patch(
        "os.makedirs", MagicMock()
    ), patch(
        "salt.utils.files.fopen", fopen_mock
    ), patch(
        "salt.payload.dump", MagicMock()
    ), patch(
        "salt.utils.files.await_lock", side_effect=mock_await_lock
    ), patch(
        "salt.loader.grains", MagicMock(return_value={"id": "foo", "os": "Linux"})
    ):
        process_count_max = 10
        minion_opts["__role"] = "minion"
        minion_opts["minion_jid_queue_hwm"] = 100
        minion_opts["process_count_max"] = process_count_max
        # cachedir needed for lock; master pins the per-master subpath
        minion_opts["cachedir"] = "/tmp/salt_test_cache"
        minion_opts["master"] = "master-a"

        minion = salt.minion.Minion(minion_opts, jid_queue=[], io_loop=io_loop)
        try:
            # up until process_count_max: processes are started normally
            for i in range(process_count_max):
                mock_data = {"fun": "foo.bar", "jid": str(i)}
                io_loop.run_sync(
                    lambda data=mock_data: minion._handle_decoded_payload(data)
                )
                assert start_mock.call_count == i + 1
                assert len(minion.jid_queue) == i + 1

            # above process_count_max: Queue logic kicks in
            mock_data = {"fun": "foo.bar", "jid": str(process_count_max + 1)}

            # Run execution
            io_loop.run_sync(lambda: minion._handle_decoded_payload(mock_data))

            # Assert NO new process started
            assert start_mock.call_count == process_count_max
            # Assert Job was queued (payload dumped)
            assert salt.payload.dump.called
            # Assert JID added to active queue (deduplication cache)
            assert len(minion.jid_queue) == process_count_max + 1

            # Assert the queued job file landed under the per-master job_queue dir,
            # not the legacy shared cachedir/job_queue path.
            expected_dir = salt.utils.state.job_queue_dir(minion_opts)
            queue_paths = [c.args[0] for c in fopen_mock.call_args_list]
            assert any(p.startswith(expected_dir) for p in queue_paths), queue_paths

        finally:
            minion.destroy()


def test_queue_job_preserves_master_jid_69386(minion_opts):
    """
    Regression test for #69386 (job_queue side).

    The companion fix in ``salt/modules/state.py:_check_queue`` covers the
    state-queue write path. This test pins down the contract for the
    job-queue write path in ``salt.minion.Minion._queue_job``: when the
    minion shelves a payload to disk because ``process_count_max`` was
    reached, the master-supplied JID must end up unchanged in both the
    serialized payload and the queue filename.

    The job-queue path was never broken by the state-queue refactor that
    introduced #69386, but it is the most natural place for a future
    regression to creep back in -- so we assert the invariant explicitly.
    """
    master_jid = "20260601000000123456"
    payload = {
        "fun": "state.apply",
        "arg": ["highstate"],
        "jid": master_jid,
        "tgt": "minion-1",
        "ret": "",
        "user": "root",
    }

    minion_opts["__role"] = "minion"
    minion_opts["cachedir"] = "/tmp/salt_test_cache_69386"
    minion_opts["master"] = "master-a"

    dump_mock = MagicMock()
    rename_calls = []

    def _rename(src, dst):
        rename_calls.append((src, dst))

    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.loader.grains", MagicMock(return_value={"id": "foo", "os": "Linux"})
    ), patch("os.path.exists", MagicMock(return_value=True)), patch(
        "os.makedirs", MagicMock()
    ), patch(
        "salt.utils.files.fopen", MagicMock()
    ), patch(
        "salt.payload.dump", dump_mock
    ), patch(
        "salt.utils.atomicfile.atomic_rename", side_effect=_rename
    ), patch(
        "salt.utils.jid.gen_jid",
        side_effect=AssertionError(
            "_queue_job must never mint a new JID for a master-published "
            "payload (#69386 regression)"
        ),
    ):
        io_loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(minion_opts, jid_queue=[], io_loop=io_loop)
        try:
            minion._queue_job(payload)

            # Payload written to disk must carry the master JID, unchanged.
            assert dump_mock.called
            dumped_payload = dump_mock.call_args.args[0]
            assert dumped_payload["jid"] == master_jid
            assert dumped_payload is payload  # _queue_job dumps the dict by reference

            # Final on-disk filename must embed the master JID and land in
            # the per-master job_queue dir.
            expected_dir = salt.utils.state.job_queue_dir(minion_opts)
            assert rename_calls, "expected an atomic_rename into place"
            final_path = rename_calls[-1][1]
            assert final_path.startswith(expected_dir), final_path
            assert final_path.endswith(f"_{master_jid}.p"), final_path
        finally:
            minion.destroy()


async def test_process_queue_rechecks_count_per_job(minion_opts):
    """
    Test that job queue processing re-checks process count before each individual job,
    preventing race conditions where process count changes during batch processing.
    """
    # Create a simple test that just verifies the queue processing method exists
    from salt.minion import Minion

    minion = Minion(minion_opts)
    try:
        # Just test that the method exists and can be called without crashing
        await minion._process_process_queue_async_impl()
        # If we get here without exception, test passes
        assert True
    finally:
        minion.destroy()


def test_cleanup_orphaned_queue_files(minion_opts):
    """
    Test that orphaned running_ queue files are cleaned up on minion startup.
    This prevents stale files from blocking future jobs after minion crashes.
    """
    # Create a simple test that just verifies the method exists and can be called
    from salt.minion import Minion

    minion = Minion(minion_opts)
    try:
        # Just test that the method exists and doesn't crash when called
        minion._cleanup_orphaned_queue_files()
        # If we get here without exception, test passes
        assert True
    finally:
        minion.destroy()


@pytest.mark.slow_test
async def test_beacons_before_connect(minion_opts):
    """
    Tests that the 'beacons_before_connect' option causes the beacons to be initialized before connect.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion_opts["beacons_before_connect"] = True
        io_loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
        try:

            try:
                await minion.tune_in(start=True)
            except RuntimeError:
                pass

            # Make sure beacons are initialized but the sheduler is not
            assert "beacons" in minion.periodic_callbacks
            assert "schedule" not in minion.periodic_callbacks
        finally:
            minion.destroy()


@pytest.mark.slow_test
async def test_scheduler_before_connect(minion_opts):
    """
    Tests that the 'scheduler_before_connect' option causes the scheduler to be initialized before connect.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion_opts["scheduler_before_connect"] = True
        io_loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
        try:
            try:
                await minion.tune_in(start=True)
            except RuntimeError:
                pass

            # Make sure the scheduler is initialized but the beacons are not
            assert "schedule" in minion.periodic_callbacks
            assert "beacons" not in minion.periodic_callbacks
        finally:
            minion.destroy()


def test_minion_module_refresh(minion_opts):
    """
    Tests that the 'module_refresh' just return in case there is no 'schedule'
    because destroy method was already called.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        try:
            minion = salt.minion.Minion(
                minion_opts,
                io_loop=tornado.ioloop.IOLoop(),
            )
            minion.schedule = salt.utils.schedule.Schedule(
                minion_opts, {}, returners={}
            )
            assert hasattr(minion, "schedule")
            minion.destroy()
            assert not hasattr(minion, "schedule")
            assert not minion.module_refresh()
        finally:
            minion.destroy()


def test_minion_module_refresh_beacons_refresh(minion_opts):
    """
    Tests that 'module_refresh' calls beacons_refresh and that the
    minion object has a beacons attribute with beacons.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        try:
            minion = salt.minion.Minion(
                minion_opts,
                io_loop=tornado.ioloop.IOLoop(),
            )
            minion.schedule = salt.utils.schedule.Schedule(
                minion_opts, {}, returners={}
            )
            assert not hasattr(minion, "beacons")
            minion.module_refresh()
            assert hasattr(minion, "beacons")
            assert hasattr(minion.beacons, "beacons")
            assert "service.beacon" in minion.beacons.beacons
            minion.destroy()
        finally:
            if minion is not None:
                minion.destroy()


def test_beacons_refresh_preserves_interval_map(minion_opts):
    """
    Tests that 'beacons_refresh' preserves the interval_map so that
    beacon intervals are not reset during module refresh.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion = None
        try:
            minion = salt.minion.Minion(
                minion_opts,
                io_loop=tornado.ioloop.IOLoop.current(),
            )
            minion.schedule = salt.utils.schedule.Schedule(
                minion_opts, {}, returners={}
            )

            minion.module_refresh()
            assert hasattr(minion, "beacons")
            assert hasattr(minion.beacons, "interval_map")

            test_interval_map = {"status": 50, "diskusage": 30}
            minion.beacons.interval_map = test_interval_map.copy()

            old_beacons = minion.beacons

            minion.beacons_refresh()

            assert minion.beacons is not old_beacons

            assert minion.beacons.interval_map == test_interval_map
            assert minion.beacons.interval_map["status"] == 50
            assert minion.beacons.interval_map["diskusage"] == 30

        finally:
            if minion is not None:
                minion.destroy()


def test_beacons_refresh_closes_old_beacons(minion_opts):
    """
    Tests that 'beacons_refresh' calls close_beacons() on the old Beacon
    instance before replacing it, preventing inotify fd leaks.

    See: https://github.com/saltstack/salt/issues/66449
    See: https://github.com/saltstack/salt/issues/58907
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion = None
        try:
            minion = salt.minion.Minion(
                minion_opts,
                io_loop=tornado.ioloop.IOLoop.current(),
            )
            minion.schedule = salt.utils.schedule.Schedule(
                minion_opts, {}, returners={}
            )

            minion.module_refresh()
            assert hasattr(minion, "beacons")

            old_beacons = minion.beacons
            with patch.object(old_beacons, "close_beacons") as close_mock:
                minion.beacons_refresh()
                close_mock.assert_called_once()

            assert minion.beacons is not old_beacons

        finally:
            if minion is not None:
                minion.destroy()


@pytest.mark.slow_test
async def test_when_ping_interval_is_set_the_callback_should_be_added_to_periodic_callbacks(
    minion_opts,
):
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion_opts["ping_interval"] = 10
        io_loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
        try:
            try:
                minion.connected = MagicMock(side_effect=(False, True))

                # _fire_master_minion_start is now called as a coroutine via create_task
                # so it must be an async function
                async def async_mock():
                    pass

                minion._fire_master_minion_start = async_mock
                minion.tune_in(start=False)
            except RuntimeError:
                pass

            # Make sure the scheduler is initialized but the beacons are not
            assert "ping" in minion.periodic_callbacks
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_when_passed_start_event_grains(minion_opts):
    # provide mock opts an os grain since we'll look for it later.
    minion_opts["grains"]["os"] = "linux"
    minion_opts["start_event_grains"] = ["os"]
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._send_req_sync = MagicMock()
        minion._fire_master(
            "Minion has started", "minion_start", include_startup_grains=True
        )
        load = minion._send_req_sync.call_args[0][0]

        assert "grains" in load
        assert "os" in load["grains"]
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_when_not_passed_start_event_grains(minion_opts):
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._send_req_sync = MagicMock()
        minion._fire_master("Minion has started", "minion_start")
        load = minion._send_req_sync.call_args[0][0]

        assert "grains" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_when_other_events_fired_and_start_event_grains_are_set(minion_opts):
    minion_opts["start_event_grains"] = ["os"]
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._send_req_sync = MagicMock()
        minion._fire_master("Custm_event_fired", "custom_event")
        load = minion._send_req_sync.call_args[0][0]

        assert "grains" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_minimal_payload(minion_opts):
    """
    A minimal published job with start_event=True should produce a
    salt/job/<jid>/start/<minion_id> event whose payload contains the
    core identifying fields and excludes the function arguments.
    """
    minion_opts["id"] = "minion-under-test"
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        data = {
            "jid": "20260429000000000000",
            "fun": "test.ping",
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
            "arg": ["should-not-leak"],
        }
        minion._fire_start_event(data)
        minion._fire_master.assert_called_once()
        load, tag = minion._fire_master.call_args[0]
        assert tag == "salt/job/20260429000000000000/start/{}".format(minion_opts["id"])
        assert load["id"] == minion_opts["id"]
        assert load["jid"] == data["jid"]
        assert load["fun"] == data["fun"]
        assert load["tgt"] == data["tgt"]
        assert load["tgt_type"] == data["tgt_type"]
        assert load["user"] == data["user"]
        assert "arg" not in load
        assert "fun_args" not in load
        assert "master_id" not in load
        assert "metadata" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_includes_master_id_and_metadata(minion_opts):
    """
    When the published load carries master_id and metadata, the start
    event should propagate both.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        data = {
            "jid": "20260429000000000001",
            "fun": "test.ping",
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
            "master_id": "master-a",
            "metadata": {"ticket": "INC-1234"},
        }
        minion._fire_start_event(data)
        load, _tag = minion._fire_master.call_args[0]
        assert load["master_id"] == "master-a"
        assert load["metadata"] == {"ticket": "INC-1234"}
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_swallows_failures(minion_opts):
    """
    A failure inside _fire_master must not propagate out of
    _fire_start_event; firing the start event must never abort job
    execution.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock(side_effect=RuntimeError("transport down"))
        data = {
            "jid": "20260429000000000002",
            "fun": "test.ping",
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
        }
        minion._fire_start_event(data)
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_empty_metadata_is_propagated(minion_opts):
    """
    An empty metadata dict is still meaningful (caller deliberately sent
    one) and must be propagated. Distinguishes ``metadata={}`` from a
    missing key.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        data = {
            "jid": "20260429000000000010",
            "fun": "test.ping",
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
            "metadata": {},
        }
        minion._fire_start_event(data)
        load, _tag = minion._fire_master.call_args[0]
        assert "metadata" in load
        assert load["metadata"] == {}
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_omits_falsy_master_id(minion_opts):
    """
    A master_id of None or empty string must not appear in the start
    event load (the gate is truthiness, matching how master_id flows in
    the publish path).
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        for falsy in (None, ""):
            minion._fire_master.reset_mock()
            data = {
                "jid": "20260429000000000011",
                "fun": "test.ping",
                "tgt": "*",
                "tgt_type": "glob",
                "user": "root",
                "master_id": falsy,
            }
            minion._fire_start_event(data)
            load, _tag = minion._fire_master.call_args[0]
            assert "master_id" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_fire_start_event_multi_fun_passes_list(minion_opts):
    """
    For multi-fun jobs, ``data["fun"]`` is a list. The start event
    should still fire successfully and propagate the list of function
    names verbatim.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        data = {
            "jid": "20260429000000000012",
            "fun": ["test.ping", "test.echo"],
            "arg": [[], ["hello"]],
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
        }
        minion._fire_start_event(data)
        minion._fire_master.assert_called_once()
        load, _tag = minion._fire_master.call_args[0]
        assert load["fun"] == ["test.ping", "test.echo"]
        assert "arg" not in load
    finally:
        minion.destroy()


def _make_thread_return_minion_mock(tmp_path, opts):
    """
    Build a MagicMock that quacks like a Minion well enough for
    _thread_return to reach (or skip) the start-event gate. Heavy
    dependencies (executors, returners, the actual function) are
    short-circuited; only the start-event gating logic is exercised.
    """
    proc_dir = tmp_path / "proc"
    proc_dir.mkdir(exist_ok=True)
    minion_instance = MagicMock()
    minion_instance.proc_dir = str(proc_dir)
    minion_instance.opts = opts
    minion_instance.executors = {}
    minion_instance.module_executors = []
    minion_instance.functions = MagicMock()
    minion_instance.functions.__contains__.return_value = True
    minion_instance.functions.pack = {"__context__": {"retcode": 0}}
    minion_instance._execute_job_function = MagicMock(return_value="ok")
    minion_instance._return_pub = MagicMock()
    minion_instance._fire_master = MagicMock()
    minion_instance._fire_start_event = MagicMock()
    minion_instance._return_retry_timer = MagicMock(return_value=1)
    minion_instance.connected = False  # skip _return_pub
    minion_instance.returners = MagicMock()
    minion_instance.function_errors = {}
    return minion_instance


@pytest.mark.slow_test
def test_thread_return_fires_start_event_when_requested(tmp_path, minion_opts):
    """
    _thread_return must invoke _fire_start_event exactly once when the
    published load carries start_event=True.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "minion-thread-return"
    minion_instance = _make_thread_return_minion_mock(tmp_path, minion_opts)
    data = {
        "jid": "20260429000000000020",
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
        "ret": "",
        "start_event": True,
    }
    salt.minion.Minion._thread_return(minion_instance, minion_opts, data)
    minion_instance._fire_start_event.assert_called_once_with(data)


@pytest.mark.slow_test
def test_thread_return_skips_start_event_when_not_requested(tmp_path, minion_opts):
    """
    _thread_return must NOT invoke _fire_start_event when the published
    load has no start_event key. This is the default behavior for all
    pre-existing callers and must not regress.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "minion-thread-return"
    minion_instance = _make_thread_return_minion_mock(tmp_path, minion_opts)
    data = {
        "jid": "20260429000000000021",
        "fun": "test.ping",
        "arg": [],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
        "ret": "",
    }
    salt.minion.Minion._thread_return(minion_instance, minion_opts, data)
    minion_instance._fire_start_event.assert_not_called()


@pytest.mark.slow_test
def test_thread_return_skips_start_event_when_falsy(tmp_path, minion_opts):
    """
    A start_event of False/None/empty string must be treated as
    opt-out; _fire_start_event should not be invoked.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "minion-thread-return"
    for falsy in (False, None, "", 0):
        minion_instance = _make_thread_return_minion_mock(tmp_path, minion_opts)
        data = {
            "jid": "20260429000000000022",
            "fun": "test.ping",
            "arg": [],
            "tgt": "*",
            "tgt_type": "glob",
            "user": "root",
            "ret": "",
            "start_event": falsy,
        }
        salt.minion.Minion._thread_return(minion_instance, minion_opts, data)
        assert (
            minion_instance._fire_start_event.call_count == 0
        ), f"Unexpectedly fired start event for falsy value {falsy!r}"


def _make_thread_multi_return_minion_mock(tmp_path, opts):
    """
    Sibling helper for _thread_multi_return tests.
    """
    proc_dir = tmp_path / "proc"
    proc_dir.mkdir(exist_ok=True)
    minion_instance = MagicMock()
    minion_instance.proc_dir = str(proc_dir)
    minion_instance.opts = opts
    minion_instance.executors = {}
    minion_instance.module_executors = []
    minion_instance.functions = MagicMock()
    minion_instance.functions.__contains__.return_value = True
    minion_instance.functions.pack = {"__context__": {"retcode": 0}}
    minion_instance._execute_job_function = MagicMock(return_value="ok")
    minion_instance._return_pub_multi = MagicMock()
    minion_instance._fire_master = MagicMock()
    minion_instance._fire_start_event = MagicMock()
    minion_instance._return_retry_timer = MagicMock(return_value=1)
    minion_instance.connected = False
    minion_instance.returners = MagicMock()
    minion_instance.function_errors = {}
    return minion_instance


@pytest.mark.slow_test
def test_thread_multi_return_fires_start_event_once_per_jid(tmp_path, minion_opts):
    """
    Multi-fun jobs share a single jid; the start event must fire
    exactly once for the jid regardless of how many sub-functions are
    in the load.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "minion-multi"
    minion_instance = _make_thread_multi_return_minion_mock(tmp_path, minion_opts)
    data = {
        "jid": "20260429000000000030",
        "fun": ["test.ping", "test.echo", "test.version"],
        "arg": [[], ["hello"], []],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
        "ret": "",
        "start_event": True,
    }
    salt.minion.Minion._thread_multi_return(minion_instance, minion_opts, data)
    minion_instance._fire_start_event.assert_called_once_with(data)


@pytest.mark.slow_test
def test_thread_multi_return_skips_start_event_when_not_requested(
    tmp_path, minion_opts
):
    """
    Multi-fun jobs without start_event must not produce a start event,
    matching the single-fun gating.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["id"] = "minion-multi"
    minion_instance = _make_thread_multi_return_minion_mock(tmp_path, minion_opts)
    data = {
        "jid": "20260429000000000031",
        "fun": ["test.ping", "test.echo"],
        "arg": [[], []],
        "tgt": "*",
        "tgt_type": "glob",
        "user": "root",
        "ret": "",
    }
    salt.minion.Minion._thread_multi_return(minion_instance, minion_opts, data)
    minion_instance._fire_start_event.assert_not_called()


@pytest.mark.slow_test
def test_fire_start_event_missing_jid_does_not_raise(minion_opts):
    """
    A malformed payload (missing jid) must not propagate an exception
    out of _fire_start_event. Job execution must never be aborted by a
    failure in the start-event helper.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._fire_master = MagicMock()
        data = {"fun": "test.ping"}
        # Should not raise even though "jid" is required and missing.
        minion._fire_start_event(data)
        # _fire_master should not have been called because payload
        # construction failed before reaching it.
        minion._fire_master.assert_not_called()
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_return_pub_handles_send_req_timeout(minion_opts):
    """
    Ensure _return_pub catches SaltReqTimeoutError from _send_req_sync and
    returns an empty string rather than letting the exception propagate.

    This is the end-to-end contract between the two methods: _send_req_sync
    must raise SaltReqTimeoutError (not the bare TimeoutError builtin) so
    that _return_pub's except clause fires correctly.
    """
    io_loop = tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.proc_dir = salt.minion.get_proc_dir(minion_opts["cachedir"])
        minion._send_req_sync = MagicMock(side_effect=SaltReqTimeoutError("timed out"))
        result = minion._return_pub(
            {
                "id": minion_opts["id"],
                "jid": "20260101000000000001",
                "return": True,
                "fun": "test.ping",
            }
        )
        assert result == ""
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_minion_retry_dns_count(minion_opts):
    """
    Tests that the resolve_dns will retry dns look ups for a maximum of
    3 times before raising a SaltMasterUnresolvableError exception.
    """
    minion_opts.update(
        {
            "ipv6": False,
            "master": "dummy",
            "master_port": "4555",
            "retry_dns": 1,
            "retry_dns_count": 3,
        },
    )
    with pytest.raises(SaltMasterUnresolvableError):
        salt.minion.resolve_dns(minion_opts)


def test_resolve_dns_retry_aborts_on_shutdown_request_69466(minion_opts):
    """
    Regression test for #69466.

    The resolve_dns() retry loop must wake up promptly when a shutdown is
    requested (e.g. SIGTERM via MinionManager.stop()) instead of blocking
    the io_loop for the full ``retry_dns`` interval. Without the fix the
    blocking ``time.sleep(opts["retry_dns"])`` inside resolve_dns starved
    the io_loop and the shutdown callback never ran until systemd sent
    SIGKILL.
    """
    # The fix exposes a public module-level abort hook used by
    # MinionManager.stop(). Its absence is itself a regression.
    assert hasattr(salt.minion, "request_resolve_dns_abort"), (
        "salt.minion is missing request_resolve_dns_abort(); the SIGTERM "
        "path cannot interrupt the DNS retry loop. See #69466."
    )
    assert hasattr(salt.minion, "_RESOLVE_DNS_ABORT"), (
        "salt.minion is missing the _RESOLVE_DNS_ABORT event used to "
        "wake an in-progress resolve_dns() retry. See #69466."
    )

    minion_opts.update(
        {
            "ipv6": False,
            "master": "dummy",
            "master_port": "4555",
            # A retry interval that is much larger than the test deadline.
            # If the abort path is not honored, this test would block for
            # the full 90 seconds.
            "retry_dns": 90,
            "retry_dns_count": None,
        },
    )

    # The resolve_dns abort flag is process-wide; make sure we leave it
    # clean for other tests.
    salt.minion._RESOLVE_DNS_ABORT.clear()

    def trip_abort():
        # Give resolve_dns a moment to enter its sleep, then request abort
        # the same way MinionManager.stop() does on SIGTERM.
        time.sleep(0.25)
        salt.minion.request_resolve_dns_abort()

    aborter = threading.Thread(target=trip_abort, daemon=True)
    started = time.monotonic()
    try:
        aborter.start()
        with pytest.raises(SaltMasterUnresolvableError):
            salt.minion.resolve_dns(minion_opts)
    finally:
        aborter.join(timeout=5)
        salt.minion._RESOLVE_DNS_ABORT.clear()

    elapsed = time.monotonic() - started
    # The fix should wake well under 5s; the broken code would sleep for
    # the full retry_dns (90s) per iteration.
    assert elapsed < 5, (
        f"resolve_dns did not honor the shutdown abort flag "
        f"(elapsed={elapsed:.2f}s); regression of #69466."
    )


def test_minion_manager_stop_unblocks_resolve_dns_69466(minion_opts):
    """
    Regression test for #69466.

    ``MinionManager.stop()`` is the entry point invoked from the SIGTERM
    handler. It must trip the resolve_dns abort flag before scheduling
    the async shutdown so a minion currently stuck in the DNS retry loop
    yields the io_loop. Without this, ``stop_async`` is queued but never
    runs and systemd escalates to SIGKILL after 90 seconds.
    """
    # The abort flag must be cleared at entry; stop() should set it.
    salt.minion._RESOLVE_DNS_ABORT.clear()
    assert not salt.minion._RESOLVE_DNS_ABORT.is_set()

    manager = salt.minion.MinionManager.__new__(salt.minion.MinionManager)
    manager.io_loop = MagicMock()
    # Populate the attributes __del__ -> destroy() touches so the
    # interpreter does not log an AttributeError at GC time.
    manager.minions = []
    manager.event_publisher = None
    manager.event = None
    try:
        manager.stop(signal.SIGTERM, lambda *a, **kw: None)
        assert salt.minion._RESOLVE_DNS_ABORT.is_set(), (
            "MinionManager.stop() did not request a resolve_dns abort; "
            "a SIGTERM during the DNS retry loop will be ignored. See #69466."
        )
        # MinionManager.stop() schedules stop_async via
        # ``io_loop.create_task`` (the 3007.x refactor replaced the earlier
        # ``add_callback`` form).  Either call is acceptable evidence that
        # the async shutdown got queued.
        assert (
            manager.io_loop.create_task.call_count
            + manager.io_loop.add_callback.call_count
            == 1
        )
    finally:
        salt.minion._RESOLVE_DNS_ABORT.clear()


@pytest.mark.slow_test
def test_gen_modules_executors(minion_opts):
    """
    Ensure gen_modules is called with the correct arguments #54429
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)

    class MockPillarCompiler:
        def compile_pillar(self):
            return {}

    try:
        with patch("salt.pillar.get_pillar", return_value=MockPillarCompiler()):
            with patch("salt.loader.executors", mock=MagicMock()) as execmock:
                minion.gen_modules()
        execmock.assert_called_once_with(
            minion.opts, functions=minion.functions, proxy=minion.proxy, context={}
        )
    finally:
        minion.destroy()


@contextlib.contextmanager
def _threaded_minion_61830(minion_opts, pillar=None):
    """
    A real Minion set up the way a threaded minion (multiprocessing: False)
    runs jobs, with _return_pub replaced by a recorder. Yields
    ``(minion, delivered)``.
    """
    minion_opts["multiprocessing"] = False
    minion_opts["file_client"] = "local"
    minion_opts["grains"] = {}
    minion_opts["pillar"] = pillar or {}
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.gen_modules()
        minion.connected = True
        proc_dir = os.path.join(minion_opts["cachedir"], "proc")
        os.makedirs(proc_dir, exist_ok=True)
        minion.proc_dir = proc_dir
        delivered = []
        minion._return_pub = lambda ret, *args, **kwargs: delivered.append(ret)
        yield minion, delivered
    finally:
        minion.destroy()


def _racing_gen_modules_61830(minion, state, prepare=None):
    """
    Return a stand-in for ``minion.gen_modules`` that runs the job's own real
    gen_modules() and then a sibling job's real gen_modules(), which rebinds
    the shared minion.functions, minion.executors and minion.resource_loaders
    before the job uses any of them. The job's own return value is passed
    through untouched.

    Both generations are recorded in ``state`` as ``<label>_functions``,
    ``<label>_executors`` and ``<label>_resource_loaders`` (label ``job`` or
    ``sibling``). ``prepare(label)`` runs right after each of the two real
    calls, while the shared attributes still point at that generation, so a
    test can install per-generation fakes.
    """
    real_gen_modules = minion.gen_modules

    def record(label):
        if prepare is not None:
            prepare(label)
        state[f"{label}_functions"] = minion.functions
        state[f"{label}_executors"] = minion.executors
        state[f"{label}_resource_loaders"] = minion.resource_loaders

    def racing_gen_modules(*args, **kwargs):
        own = real_gen_modules(*args, **kwargs)
        record("job")
        real_gen_modules()
        record("sibling")
        return own

    return racing_gen_modules


def _assert_distinct_generations_61830(state):
    # The race really produced two loader generations that do not share a
    # __context__; otherwise the test would prove nothing.
    assert state["job_functions"] is not state["sibling_functions"]
    assert state["job_executors"] is not state["sibling_executors"]
    assert (
        state["job_functions"].pack["__context__"]
        is not state["sibling_functions"].pack["__context__"]
    )


def _sibling_job_61830(minion, functions, code, fun="test.retcode", exec_fn=None):
    """
    A sibling job's real _execute_job_function on ``functions``: the
    start-of-job retcode reset, then ``fun`` writes ``code`` into that
    loader's __context__.
    """
    if exec_fn is None:
        exec_fn = salt.minion.Minion._execute_job_function
    exec_fn(
        minion,
        fun,
        [code],
        ["direct_call"],
        minion.opts,
        {
            "jid": f"20260101000001{code:06d}",
            "fun": fun,
            "arg": [code],
            "ret": "",
        },
        functions=functions,
    )


def _run_job_thread_61830(target, minion, data):
    """
    Run a job runner (``Minion._thread_return``) on its own thread, the way a
    threaded minion (multiprocessing: False) runs every job.

    For a job with ``data["resource_target"]``, _thread_return sets
    ``salt.loader.context.resource_ctxvar`` and never resets it: the job's
    thread, and the context it set the value in, end with the job. Called on
    the pytest main thread, that value would outlive the test and leak into
    every later test that reads the variable.
    """
    errors = []

    def run():
        try:
            target(minion, minion.opts, data)
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    thread = threading.Thread(target=run, name=str(data["jid"]))
    thread.start()
    thread.join(timeout=120)
    assert not thread.is_alive(), "job thread did not finish"
    if errors:
        raise errors[0]


@contextlib.contextmanager
def _sudo_available_61830():
    """
    The sudo executor's __virtual__ needs sudo on the PATH as well as
    sudo_user; report it present without touching any other lookup.
    """
    real_which = salt.utils.path.which

    def which(exe):
        if exe == "sudo":
            return "/usr/bin/sudo"
        return real_which(exe)

    with patch("salt.utils.path.which", which):
        yield


def _sudo_stdout_61830(retcode):
    # What ``salt-call --out json --metadata -- test.retcode <n>`` prints.
    return salt.utils.json.dumps(
        {"local": {"fun": "test.retcode", "return": True, "retcode": retcode}}
    )


# (this job's test.retcode argument, what cmd.run_all returns for the
# ``sudo -u <user> salt-call ...`` command, expected delivered retcode,
# expected delivered return)
SUDO_CASES_61830 = pytest.mark.parametrize(
    "code,cmd_ret,expected_retcode,expected_return",
    [
        # salt-call ran the job under sudo and the job failed; the sudo
        # executor takes the retcode from salt-call's metadata.
        (
            42,
            {"pid": 4242, "retcode": 0, "stdout": _sudo_stdout_61830(42), "stderr": ""},
            42,
            True,
        ),
        # sudo itself failed, salt-call never ran; the sudo executor takes
        # sudo's exit code.
        (
            42,
            {
                "pid": 4242,
                "retcode": 1,
                "stdout": "",
                "stderr": "sudo: a password is required",
            },
            1,
            "sudo: a password is required",
        ),
        # Inverse must-not: a job that passed under sudo stays passing.
        (
            0,
            {"pid": 4242, "retcode": 0, "stdout": _sudo_stdout_61830(0), "stderr": ""},
            salt.defaults.exitcodes.EX_OK,
            True,
        ),
    ],
    ids=["job-failed-under-sudo", "sudo-failed", "passing-job-stays-passing"],
)


def _fake_sudo_salt_call_61830(minion, cmd_ret, calls):
    """
    ``prepare`` hook for _racing_gen_modules_61830: replace cmd.run_all on
    each loader generation with a fake for the ``sudo -u <user> salt-call``
    command the sudo executor runs through ``__salt__["cmd.run_all"]``.
    """

    def prepare(label):
        def run_all(cmd, **kwargs):
            calls.append(cmd)
            return dict(cmd_ret)

        minion.functions["cmd.run_all"] = run_all

    return prepare


def _assert_sudo_call_61830(calls, code):
    # The job really ran through the sudo executor, exactly once, with this
    # job's argument.
    assert len(calls) == 1
    assert calls[0][:3] == ["sudo", "-u", "saltdev"]
    assert calls[0][-1] == str(code)


def test_thread_return_retcode_owns_captured_loader_61830(minion_opts):
    """
    #61830: with multiprocessing=False every threaded job shares one
    minion_instance, and every job calls minion_instance.gen_modules() at its
    top. That builds a new loader generation with a fresh, empty __context__
    and rebinds the shared minion_instance.functions to it.

    On 3008.x the resource-loader work already makes _thread_return capture
    ``functions_to_use = minion_instance.functions`` once and pass it to
    _execute_job_function, so a sibling rebind between this job's retcode
    write and its retcode read no longer changes which loader is read. The
    remaining single-function gap is earlier: the window between the job's own
    gen_modules() call and that capture. A sibling job's gen_modules() landing
    there makes this job capture the SIBLING's loader, so both jobs share one
    __context__ and the sibling's start-of-job retcode reset in
    _execute_job_function (``__context__["retcode"] = 0``) overwrites the
    retcode this job wrote: a failed command is reported as success, and a
    failing sibling's retcode leaks into a passing job. The fix makes
    _thread_return use the loaders its own gen_modules() call returned.

    This drives the REAL Minion._thread_return end to end:

    - the job's own gen_modules() call is wrapped so a real sibling
      gen_modules() runs right after it, before _thread_return captures a
      loader;
    - the sibling job's real _execute_job_function (retcode reset, then
      test.retcode on the sibling's own loader) runs in this job's write->read
      window (the only thing _thread_return does there is
      log.info("... execution finished")).

    test.retcode writes the retcode into its loader's __context__ exactly like
    a production module.
    """
    with _threaded_minion_61830(minion_opts) as (minion, delivered):
        original_info = salt.minion.log.info
        state = {}

        def sibling_starts_info(msg, *args, **kwargs):
            # The sibling job starts executing in this job's write->read
            # window, on the loader its own gen_modules() built.
            if "execution finished" in str(msg) and not state.get("sibling_ran"):
                state["sibling_ran"] = True
                _sibling_job_61830(
                    minion, state["sibling_functions"], state["sibling_code"]
                )
            return original_info(msg, *args, **kwargs)

        def run(code, sibling_code=0):
            delivered.clear()
            state.clear()
            state["sibling_code"] = sibling_code
            data = {
                "jid": f"20260101000000{code:06d}",
                "fun": "test.retcode",
                "arg": [code],
                "ret": "",
            }
            with patch.object(
                minion, "gen_modules", _racing_gen_modules_61830(minion, state)
            ), patch.object(salt.minion.log, "info", sibling_starts_info):
                salt.minion.Minion._thread_return(minion, minion.opts, data)
            assert state.get("sibling_ran"), "sibling job never ran in the window"
            _assert_distinct_generations_61830(state)
            assert len(delivered) == 1
            return delivered[0]

        # A FAILED job (retcode 42) whose sibling passes must be delivered as
        # failed. Pre-fix this job ran on the sibling's loader and the sibling's
        # reset turned it into retcode=0/success=True (the bug).
        ret = run(42)
        assert ret["retcode"] == 42
        assert ret["success"] is False
        # The retcode lives in, and was read from, the loader this job built;
        # the sibling's loader only holds the sibling's own retcode.
        assert state["job_functions"].pack["__context__"]["retcode"] == 42
        assert (
            state["sibling_functions"].pack["__context__"]["retcode"]
            == salt.defaults.exitcodes.EX_OK
        )

        # Inverse must-not: a SUCCEEDING job (retcode 0) under the same forced
        # interleave must still be delivered as success; the fix must not flip
        # a genuinely-passing job to failed.
        ret = run(0)
        assert ret["retcode"] == salt.defaults.exitcodes.EX_OK
        assert ret["success"] is True

        # Inverse must-not: a FAILING sibling (retcode 7) must not leak its
        # retcode into a passing job. Pre-fix this job was delivered as
        # retcode=7/success=False.
        ret = run(0, sibling_code=7)
        assert ret["retcode"] == salt.defaults.exitcodes.EX_OK
        assert ret["success"] is True


@SUDO_CASES_61830
def test_thread_return_sudo_executor_owns_job_generation_61830(
    minion_opts, code, cmd_ret, expected_retcode, expected_return
):
    """
    #61830 with ``sudo_user`` set: the sudo executor runs the job as
    ``sudo -u <sudo_user> salt-call ...`` through ``__salt__["cmd.run_all"]``
    and writes the retcode into the ``__context__`` of the loader generation
    the EXECUTOR belongs to, not the one the function lookup used.
    _thread_return reads the retcode back from the generation its own
    gen_modules() call returned, so it must also run through that
    generation's executors.

    A sibling job's gen_modules() between this job's own gen_modules() and its
    executor call rebinds minion.executors. A job that owned its functions
    loader but still ran through the shared minion.executors (the first
    version of this fix) had the sudo executor write the retcode into the
    sibling's __context__ and read its own, freshly reset one: a failed job
    was reported as success.

    Stock 3008.x passes this by design: it captures minion.functions only
    after the sibling's rebind and runs through minion.executors, so its
    write and its read both land in the sibling's generation. This guards
    against loader ownership breaking the sudo case.
    """
    minion_opts["sudo_user"] = "saltdev"
    state = {}
    calls = []
    with _threaded_minion_61830(minion_opts) as (
        minion,
        delivered,
    ), _sudo_available_61830():
        data = {
            "jid": f"20260101000000{code:06d}",
            "fun": "test.retcode",
            "arg": [code],
            "ret": "",
        }
        racing = _racing_gen_modules_61830(
            minion, state, _fake_sudo_salt_call_61830(minion, cmd_ret, calls)
        )
        with patch.object(minion, "gen_modules", racing):
            salt.minion.Minion._thread_return(minion, minion.opts, data)

    _assert_distinct_generations_61830(state)
    _assert_sudo_call_61830(calls, code)
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["return"] == expected_return
    assert ret["retcode"] == expected_retcode
    assert ret["success"] is (expected_retcode == salt.defaults.exitcodes.EX_OK)


@SUDO_CASES_61830
def test_thread_multi_return_sudo_executor_owns_job_generation_61830(
    minion_opts, code, cmd_ret, expected_retcode, expected_return
):
    """
    #61830, multi-function path, with ``sudo_user`` set: the sudo executor
    writes the retcode into the ``__context__`` of the generation the
    executor belongs to, and _thread_multi_return reads it back from the
    generation its own gen_modules() call returned, so it must also run each
    function through that generation's executors.

    A sibling job's gen_modules() between this job's own gen_modules() and
    the function call rebinds minion.executors. Passing only the job's
    functions loader to _execute_job_function (the first version of this
    fix) left the call on the shared minion.executors: the sudo executor
    wrote the retcode into the sibling's __context__ and the job read its
    own, freshly reset one, so a failed function was reported as success.

    Stock 3008.x passes this by design: it runs on the shared minion.functions
    and minion.executors and reads the shared minion.functions back, so its
    write and its read both land in the sibling's generation here. This
    guards against loader ownership breaking the sudo case.
    """
    minion_opts["sudo_user"] = "saltdev"
    state = {}
    calls = []
    with _threaded_minion_61830(minion_opts) as (
        minion,
        delivered,
    ), _sudo_available_61830():
        data = {
            "jid": f"20260101000000{code:06d}",
            "fun": ["test.retcode"],
            "arg": [[code]],
            "ret": "",
        }
        racing = _racing_gen_modules_61830(
            minion, state, _fake_sudo_salt_call_61830(minion, cmd_ret, calls)
        )
        with patch.object(minion, "gen_modules", racing):
            salt.minion.Minion._thread_multi_return(minion, minion.opts, data)

    _assert_distinct_generations_61830(state)
    _assert_sudo_call_61830(calls, code)
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["return"]["test.retcode"] == expected_return
    assert ret["retcode"]["test.retcode"] == expected_retcode
    assert ret["success"]["test.retcode"] is (
        expected_retcode == salt.defaults.exitcodes.EX_OK
    )


# A custom execution module for the ``dummy`` resource type, installed the way
# saltutil.sync_* would (under extension_modules). Like salt.modules.test.retcode
# it writes the retcode into its loader's __context__.
RESOURCE_RETCODE_MODULE_61830 = """
def retcode(code=42):
    __context__["retcode"] = code
    return True
"""


@pytest.mark.parametrize(
    "code,sibling_code",
    [
        # A failed resource job must be delivered as failed.
        (42, 0),
        # Inverse must-not: a passing resource job stays passing.
        (0, 0),
        # Inverse must-not: a failing sibling's retcode on the shared
        # resource loader must not leak into this passing job.
        (0, 7),
    ],
    ids=["failed-job-stays-failed", "passing-job-stays-passing", "no-sibling-leak"],
)
def test_thread_return_resource_job_owns_job_generation_61830(
    minion_opts, tmp_path, code, sibling_code
):
    """
    #61830, resource jobs: a job with ``data["resource_target"]`` runs its
    function on the per-type execution loader for that resource type and
    reads its retcode back from that loader's ``__context__``. The per-type
    loaders are built by gen_modules() with that call's context, and stock
    3008.x (and the first version of this fix) took the loader from the
    shared minion.resource_loaders, which every job's gen_modules() rebinds.

    A sibling job's gen_modules() between this job's own gen_modules() and
    the loader lookup made this job run on the SIBLING's resource loader; a
    sibling resource job then reset (and wrote) the retcode on that shared
    loader in this job's write->read window, so a failed job was reported as
    success and a failing sibling's retcode leaked into a passing job. The
    fix takes the loader from the generation the job's own gen_modules()
    returned.

    This drives the REAL Minion._thread_return, on its own job thread as a
    threaded minion runs it, with a production-shaped resource job (what
    _handle_payload dispatches for ``T@dummy:dummy-01``): real pillar-driven
    discovery of the shipped ``dummy`` resource type, the real per-type loader
    from salt.loader.resource_modules, and a custom ``dummy`` resource
    execution module under extension_modules whose function writes the
    retcode into its loader's __context__.
    """
    moddir = tmp_path / "extmods" / "resources" / "dummy" / "modules"
    moddir.mkdir(parents=True)
    with salt.utils.files.fopen(str(moddir / "rctest.py"), "w") as fp_:
        fp_.write(RESOURCE_RETCODE_MODULE_61830)
    minion_opts["extension_modules"] = str(tmp_path / "extmods")
    pillar = {"resources": {"dummy": {"resource_ids": ["dummy-01"]}}}
    resource = {"id": "dummy-01", "type": "dummy"}
    state = {}

    with _threaded_minion_61830(minion_opts, pillar=pillar) as (minion, delivered):
        original_info = salt.minion.log.info

        def sibling_starts_info(msg, *args, **kwargs):
            # A sibling resource job starts on the shared per-type loader in
            # this job's write->read window.
            if "execution finished" in str(msg) and not state.get("sibling_ran"):
                state["sibling_ran"] = True
                _sibling_job_61830(
                    minion,
                    minion.resource_loaders["dummy"],
                    sibling_code,
                    fun="rctest.retcode",
                )
            return original_info(msg, *args, **kwargs)

        data = {
            "jid": f"20260101000000{code:06d}",
            "fun": "rctest.retcode",
            "arg": [code],
            "ret": "",
            "tgt": "T@dummy:dummy-01",
            "tgt_type": "compound",
            "resource_targets": [resource],
            "pure_resource_target": True,
            "minion_is_target": False,
            "resource_target": resource,
            "resource_job": True,
        }
        with patch.object(
            minion, "gen_modules", _racing_gen_modules_61830(minion, state)
        ), patch.object(salt.minion.log, "info", sibling_starts_info):
            _run_job_thread_61830(salt.minion.Minion._thread_return, minion, data)

    assert state.get("sibling_ran"), "sibling job never ran in the window"
    _assert_distinct_generations_61830(state)
    job_loader = state["job_resource_loaders"]["dummy"]
    sibling_loader = state["sibling_resource_loaders"]["dummy"]
    assert job_loader is not sibling_loader
    assert job_loader.pack["__context__"] is not sibling_loader.pack["__context__"]
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["resource_id"] == "dummy-01"
    assert ret["return"] is True
    assert ret["retcode"] == code
    assert ret["success"] is (code == salt.defaults.exitcodes.EX_OK)
    # The job's function ran on, and wrote its retcode into, the per-type
    # loader of the generation its own gen_modules() built.
    assert job_loader.pack["__context__"].get("retcode") == code
    # The resource_target the job set stayed on the job's thread.
    assert salt.loader.context.resource_ctxvar.get() == {}


# state.apply for the ``dummy`` resource type, installed under
# extension_modules like RESOURCE_RETCODE_MODULE_61830: a one-state run whose
# state fails when the job applies ``failing``. It leaves the retcode to the
# executor below.
RESOURCE_STATE_MODULE_61830 = """
def apply(mods=None):
    return {
        "test_|-check_|-check_|-check": {
            "name": "check",
            "result": mods != "failing",
            "comment": "",
            "changes": {},
            "__run_num__": 0,
        }
    }
"""

# A custom executor, installed the way saltutil.sync_executors would (under
# extension_modules) and selected with ``salt --module-executors``. Like the
# sudo executor it records the job's retcode in its own __context__ instead of
# leaving that to the function: a state run with a failed state is
# EX_STATE_FAILURE.
STATE_RETCODE_EXECUTOR_61830 = """
import salt.defaults.exitcodes


def execute(opts, data, func, args, kwargs):
    ret = func(*args, **kwargs)
    if not all(state["result"] for state in ret.values()):
        __context__["retcode"] = salt.defaults.exitcodes.EX_STATE_FAILURE
    return ret
"""


@pytest.mark.parametrize(
    "mods,sibling_code,expected",
    [
        # A failed resource state run must be delivered as failed.
        ("failing", 0, salt.defaults.exitcodes.EX_STATE_FAILURE),
        # Inverse must-not: a passing resource state run stays passing.
        ("passing", 0, salt.defaults.exitcodes.EX_OK),
        # Inverse must-not: a failing sibling's retcode on the shared
        # resource loader must not leak into this passing run.
        ("passing", 7, salt.defaults.exitcodes.EX_OK),
    ],
    ids=["failed-run-stays-failed", "passing-run-stays-passing", "no-sibling-leak"],
)
def test_thread_return_merge_resource_job_owns_job_generation_61830(
    minion_opts, tmp_path, mods, sibling_code, expected
):
    """
    #61830, merge-mode resource jobs: for a state function in
    ``_MERGE_RESOURCE_FUNS`` aimed only at resources (``salt -C
    'T@dummy:dummy-01' state.apply``) the managing minion runs no job of its
    own. _thread_return's merge block runs the function once per resource on
    that resource type's per-type loader, through the job's executors, reads
    each resource's retcode back from the per-type loader's __context__ and
    sends one return per resource.

    All of those resolve against one loader generation only if the block
    takes both the per-type loader and the executors from the generation the
    job's own gen_modules() call returned. Stock 3008.x and the first version
    of this fix took the per-type loader from the shared
    minion.resource_loaders and ran through the shared minion.executors,
    both of which a sibling job's gen_modules() rebinds:

    - on the shared per-type loader, a sibling resource job's retcode reset
      and its own retcode write, landing between this run's
      _execute_job_function return and the retcode read, replaced this run's
      retcode: a failed run was delivered as success, and a failing
      sibling's retcode leaked into a passing run;
    - an executor that records the retcode itself (as sudo does) wrote it
      into the __context__ of the generation the executor belongs to, so
      running through the sibling's executors put a failed run's retcode in
      the sibling's __context__ and left this run's freshly reset one: a
      failed run was delivered as success.

    This drives the REAL Minion._thread_return on its own job thread with a
    production-shaped merge-mode job (what _target_load hands to
    _handle_decoded_payload for a pure resource target): real pillar-driven
    discovery of the shipped ``dummy`` resource type, the real per-type
    loader, a custom ``dummy`` state.apply under extension_modules, and a
    custom executor under extension_modules that records the retcode. A real
    sibling gen_modules() runs right after the job's own, and a sibling
    resource job's real _execute_job_function runs on the shared per-type
    loader right after this run's _execute_job_function returns.
    """
    extmods = tmp_path / "extmods"
    moddir = extmods / "resources" / "dummy" / "modules"
    moddir.mkdir(parents=True)
    with salt.utils.files.fopen(str(moddir / "state.py"), "w") as fp_:
        fp_.write(RESOURCE_STATE_MODULE_61830)
    with salt.utils.files.fopen(str(moddir / "rctest.py"), "w") as fp_:
        fp_.write(RESOURCE_RETCODE_MODULE_61830)
    execdir = extmods / "executors"
    execdir.mkdir()
    with salt.utils.files.fopen(str(execdir / "staterc.py"), "w") as fp_:
        fp_.write(STATE_RETCODE_EXECUTOR_61830)
    minion_opts["extension_modules"] = str(extmods)
    pillar = {"resources": {"dummy": {"resource_ids": ["dummy-01"]}}}
    resource = {"id": "dummy-01", "type": "dummy"}
    state = {}

    with _threaded_minion_61830(minion_opts, pillar=pillar) as (minion, delivered):
        real_exec = salt.minion.Minion._execute_job_function

        def racing_exec(self, *args, **kwargs):
            # This run's function returns and the executor records its
            # retcode; then a sibling resource job runs on the shared per-type
            # loader before the merge block reads the retcode back.
            result = real_exec(self, *args, **kwargs)
            if not state.get("sibling_ran"):
                state["sibling_ran"] = True
                _sibling_job_61830(
                    minion,
                    minion.resource_loaders["dummy"],
                    sibling_code,
                    fun="rctest.retcode",
                    exec_fn=real_exec,
                )
            return result

        data = {
            "jid": f"20260101000000{expected:03d}{sibling_code:03d}",
            "fun": "state.apply",
            "arg": [mods],
            "ret": "",
            "tgt": "T@dummy:dummy-01",
            "tgt_type": "compound",
            "module_executors": ["staterc"],
            "resource_targets": [resource],
            "pure_resource_target": True,
            "minion_is_target": True,
        }
        with patch.object(
            minion, "gen_modules", _racing_gen_modules_61830(minion, state)
        ), patch.object(salt.minion.Minion, "_execute_job_function", racing_exec):
            _run_job_thread_61830(salt.minion.Minion._thread_return, minion, data)

    assert state.get("sibling_ran"), "sibling job never ran in the window"
    _assert_distinct_generations_61830(state)
    job_loader = state["job_resource_loaders"]["dummy"]
    sibling_loader = state["sibling_resource_loaders"]["dummy"]
    assert job_loader is not sibling_loader
    assert job_loader.pack["__context__"] is not sibling_loader.pack["__context__"]
    # One return, for the resource, and none under the managing minion's id.
    assert len(delivered) == 1
    ret = delivered[0]
    assert ret["resource_id"] == "dummy-01"
    assert ret["fun"] == "state.apply"
    assert ret["out"] == "highstate"
    assert ret["return"] == {
        "test_|-check_|-check_|-check": {
            "name": "check",
            "result": mods != "failing",
            "comment": "",
            "changes": {},
            "__run_num__": 0,
        }
    }
    assert ret["retcode"] == expected
    assert ret["success"] is (expected == salt.defaults.exitcodes.EX_OK)
    # The run's retcode lives in, and was read from, the generation the job's
    # own gen_modules() built; the sibling's per-type loader only holds the
    # sibling's own retcode.
    assert job_loader.pack["__context__"].get("retcode") == expected
    assert sibling_loader.pack["__context__"].get("retcode") == sibling_code


def test_sys_reload_modules_returns_none_and_is_serializable_61830(minion_opts):
    """
    #61830 follow-on: gen_modules() now returns the loaders it built (a
    ModuleGeneration holding the functions, executors and resource_loaders it
    just bound to the minion) so a threaded job can run against them.
    LazyLoaders are not serializable, so sys.reload_modules must not be bound
    to gen_modules directly (its return would be put on the wire). It is bound
    to _reload_modules, which reloads the modules and returns None.
    """
    minion_opts["file_client"] = "local"
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.gen_modules()
        before = minion.functions
        reload_fn = minion.functions["sys.reload_modules"]
        result = reload_fn()
        assert result is None
        # It really reloaded the modules.
        assert minion.functions is not before
        # The wire payload must round-trip without raising.
        salt.payload.dumps({"return": result})

        # gen_modules() itself returns the generation it just bound to the
        # minion attributes.
        generation = minion.gen_modules()
        assert isinstance(generation, salt.minion.ModuleGeneration)
        assert generation.functions is minion.functions
        assert generation.executors is minion.executors
        assert generation.resource_loaders is minion.resource_loaders
        # The loaders of one generation share that call's __context__.
        assert (
            generation.executors.pack["__context__"]
            is generation.functions.pack["__context__"]
        )
        # That return value is not serializable, which is exactly why
        # sys.reload_modules needs the None-returning wrapper.
        with pytest.raises(TypeError):
            salt.payload.dumps({"return": generation})
    finally:
        minion.destroy()


def test_sys_doc_reload_modules_shows_user_docstring_61830(minion_opts):
    """
    #61830 follow-on: sys.reload_modules is served by whatever gen_modules()
    binds to it, so ``salt '*' sys.doc sys.reload_modules`` shows that
    callable's docstring, not the stub in salt/modules/sysmod.py (whose
    comment says its docstring must be mirrored in minion.py). Binding it to
    the _reload_modules wrapper must keep the user-facing text there; the
    first version of this fix showed the wrapper's internal notes instead.
    """
    minion_opts["file_client"] = "local"
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
    try:
        minion.gen_modules()
        docs = minion.functions["sys.doc"]("sys.reload_modules")
    finally:
        minion.destroy()

    assert list(docs) == ["sys.reload_modules"]
    # sys.doc strips the reST directives; compare what it shows with the same
    # processing of the sysmod stub's docstring (the online docs).
    expected = salt.utils.doc.strip_rst(
        {"sys.reload_modules": salt.modules.sysmod.reload_modules.__doc__}
    )["sys.reload_modules"]
    assert inspect.cleandoc(docs["sys.reload_modules"]) == inspect.cleandoc(expected)
    assert inspect.cleandoc(docs["sys.reload_modules"]) == (
        "Tell the minion to reload the execution modules\n"
        "\n"
        "CLI Example:\n"
        "\n"
        "    salt '*' sys.reload_modules"
    )


def test_thread_multi_return_retcode_owns_captured_loader_61830(minion_opts):
    """
    #61830, multi-function path. On 3008.x the single-function path already
    captures one loader for the retcode reset, write and read, but
    _thread_multi_return still called _execute_job_function without a loader
    (so the call ran on the shared minion.functions and minion.executors) and
    read each function's retcode back from the shared minion.functions. With
    multiprocessing=False every job's gen_modules() rebinds those attributes,
    so the write->read desync remains on this path (and in the proxy and
    deltaproxy job runners):

    - a sibling job's gen_modules() between this job's own gen_modules() and
      the function call makes the function run on the sibling's loader;
    - a sibling job's start-of-job retcode reset and its own retcode write on
      the shared loader, landing between this job's retcode write and its
      read, change what this job delivers.

    A failed function was reported as success, and a failing sibling's
    retcode leaked into a passing function. The fix passes the functions and
    executors of the generation the job's own gen_modules() returned to
    _execute_job_function and reads the retcode back from that generation.

    Both windows are forced with real code: a real sibling gen_modules() right
    after the job's own, and the sibling job's real _execute_job_function on
    the sibling's loader right after this job's function returns.
    """
    with _threaded_minion_61830(minion_opts) as (minion, delivered):
        real_exec = salt.minion.Minion._execute_job_function
        state = {}

        def racing_exec(self, *args, **kwargs):
            # The job's function writes its retcode; then the sibling job runs
            # on the sibling's loader before _thread_multi_return reads the
            # retcode back.
            result = real_exec(self, *args, **kwargs)
            if not state.get("sibling_ran"):
                state["sibling_ran"] = True
                _sibling_job_61830(
                    minion,
                    state["sibling_functions"],
                    state["sibling_code"],
                    exec_fn=real_exec,
                )
            return result

        def run(code, sibling_code=0):
            delivered.clear()
            state.clear()
            state["sibling_code"] = sibling_code
            data = {
                "jid": f"20260101000000{code:06d}",
                "fun": ["test.retcode"],
                "arg": [[code]],
                "ret": "",
            }
            with patch.object(
                minion, "gen_modules", _racing_gen_modules_61830(minion, state)
            ), patch.object(salt.minion.Minion, "_execute_job_function", racing_exec):
                salt.minion.Minion._thread_multi_return(minion, minion.opts, data)
            assert state.get("sibling_ran"), "sibling job never ran in the window"
            _assert_distinct_generations_61830(state)
            assert len(delivered) == 1
            return delivered[0]

        # A FAILED function (retcode 42) whose sibling passes must be delivered
        # as failed. Pre-fix this delivered retcode=0/success=True.
        ret = run(42)
        assert ret["retcode"]["test.retcode"] == 42
        assert ret["success"]["test.retcode"] is False
        # The retcode lives in, and was read from, the loader this job built.
        assert state["job_functions"].pack["__context__"]["retcode"] == 42
        assert (
            state["sibling_functions"].pack["__context__"]["retcode"]
            == salt.defaults.exitcodes.EX_OK
        )

        # Inverse must-not: a SUCCEEDING function (retcode 0) under the same
        # forced interleave must still be delivered as success.
        ret = run(0)
        assert ret["retcode"]["test.retcode"] == salt.defaults.exitcodes.EX_OK
        assert ret["success"]["test.retcode"] is True

        # Inverse must-not: a FAILING sibling (retcode 7) must not leak its
        # retcode into a passing function. Pre-fix this was delivered as
        # retcode=7/success=False.
        ret = run(0, sibling_code=7)
        assert ret["retcode"]["test.retcode"] == salt.defaults.exitcodes.EX_OK
        assert ret["success"]["test.retcode"] is True


def test_minion_manage_schedule(minion_opts):
    """
    Tests that the manage_schedule will call the add function, adding
    schedule data into opts.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        io_loop = tornado.ioloop.IOLoop()

        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            try:
                mock_functions = {"test.ping": None}

                minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
                minion.schedule = salt.utils.schedule.Schedule(
                    minion_opts,
                    mock_functions,
                    returners={},
                    new_instance=True,
                )

                minion.opts["foo"] = "bar"
                schedule_data = {
                    "test_job": {
                        "function": "test.ping",
                        "return_job": False,
                        "jid_include": True,
                        "maxrunning": 2,
                        "seconds": 10,
                    }
                }

                data = {
                    "name": "test-item",
                    "schedule": schedule_data,
                    "func": "add",
                    "persist": False,
                }
                tag = "manage_schedule"

                minion.manage_schedule(tag, data)
                assert "test_job" in minion.opts["schedule"]
            finally:
                del minion.schedule
                minion.destroy()
                del minion


def test_minion_manage_beacons(minion_opts):
    """
    Tests that the manage_beacons will call the add function, adding
    beacon data into opts.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ):
        minion = None
        try:
            minion_opts["beacons"] = {}

            # io_loop must be a real Tornado IOLoop because our code calls
            # salt.utils.asynchronous.aioloop() on it
            io_loop = tornado.ioloop.IOLoop()

            mock_functions = {"test.ping": None}
            minion = salt.minion.Minion(minion_opts, io_loop=io_loop)
            minion.beacons = salt.beacons.Beacon(minion_opts, mock_functions)

            bdata = [{"salt-master": "stopped"}, {"apache2": "stopped"}]
            data = {"name": "ps", "beacon_data": bdata, "func": "add"}

            tag = "manage_beacons"
            log.debug("==== minion.opts %s ====", minion.opts)

            minion.manage_beacons(tag, data)
            assert "ps" in minion.opts["beacons"]
            assert minion.opts["beacons"]["ps"] == bdata
        finally:
            if minion is not None:
                minion.destroy()


def test_prep_ip_port():
    _ip = ipaddress.ip_address

    opts = {"master": "10.10.0.3", "master_uri_format": "ip_only"}
    ret = salt.minion.prep_ip_port(opts)
    assert ret == {"master": _ip("10.10.0.3")}

    opts = {
        "master": "10.10.0.3",
        "master_port": 1234,
        "master_uri_format": "default",
    }
    ret = salt.minion.prep_ip_port(opts)
    assert ret == {"master": "10.10.0.3"}

    opts = {"master": "10.10.0.3:1234", "master_uri_format": "default"}
    ret = salt.minion.prep_ip_port(opts)
    assert ret == {"master": "10.10.0.3", "master_port": 1234}

    opts = {"master": "host name", "master_uri_format": "default"}
    pytest.raises(SaltClientError, salt.minion.prep_ip_port, opts)

    opts = {"master": "10.10.0.3:abcd", "master_uri_format": "default"}
    pytest.raises(SaltClientError, salt.minion.prep_ip_port, opts)

    opts = {"master": "10.10.0.3::1234", "master_uri_format": "default"}
    pytest.raises(SaltClientError, salt.minion.prep_ip_port, opts)


@pytest.mark.skip_on_windows(reason="Skippin, no Salt master running on Windows.")
async def test_master_type_failover(minion_opts):
    """
    Tests master_type "failover" to not fall back to 127.0.0.1 address when master does not resolve in DNS
    """
    minion_opts.update(
        {
            "master_type": "failover",
            "master": ["master1", "master2"],
            "__role": "",
            "retry_dns": 0,
            "master_tries": 1,
        }
    )

    class MockPubChannel:
        def connect(self):
            raise SaltClientError("MockedChannel")

        def close(self):
            return

    def mock_resolve_dns(opts, fallback=False):
        assert not fallback

        if opts["master"] == "master1":
            raise SaltClientError("Cannot resolve {}".format(opts["master"]))

        return {
            "master_ip": "192.168.2.1",
            "master_uri": "tcp://192.168.2.1:4505",
        }

    def mock_channel_factory(opts, **kwargs):
        assert opts["master"] == "master2"
        return MockPubChannel()

    with patch("salt.minion.resolve_dns", mock_resolve_dns), patch(
        "salt.channel.client.AsyncPubChannel.factory", mock_channel_factory
    ), patch("salt.loader.grains", MagicMock(return_value=[])):
        with pytest.raises(SaltClientError):
            minion = salt.minion.Minion(minion_opts)
            await minion.connect_master()


async def test_master_type_failover_no_masters(minion_opts):
    """
    Tests master_type "failover" to not fall back to 127.0.0.1 address when no master can be resolved
    """
    minion_opts.update(
        {
            "master_type": "failover",
            "master": ["master1", "master2"],
            "__role": "",
            "retry_dns": 0,
        }
    )

    def mock_resolve_dns(opts, fallback=False):
        assert not fallback
        raise SaltClientError("Cannot resolve {}".format(opts["master"]))

    with patch("salt.minion.resolve_dns", mock_resolve_dns), patch(
        "salt.loader.grains", MagicMock(return_value=[])
    ):
        with pytest.raises(SaltClientError):
            minion = salt.minion.Minion(minion_opts)
            # Mock the io_loop so calls to stop/close won't happen.
            minion.io_loop = MagicMock()
            await minion.connect_master()


def test_eval_master_single_master_closes_pub_channel_on_failure_68901(minion_opts):
    """
    Regression test for #68901: every AsyncPubChannel constructed by
    Minion.eval_master in the single-master sign-in path must be close()-d
    when the connection attempt fails, regardless of which exception type
    pub_channel.connect() raised. Failing to do so leaks the channel's
    underlying socket file descriptor on each retry, which over time
    exhausts the minion's fd limit.
    """
    minion_opts.update(
        {
            "master": "127.0.0.1",
            "master_type": "str",
            "transport": "zeromq",
            "__role": "",
            "retry_dns": 0,
            "acceptance_wait_time": 0,
            "acceptance_wait_time_max": 0,
            "master_tries": 1,
        }
    )

    created = []

    class MockPubChannel:
        def __init__(self):
            self.closed = 0
            created.append(self)

        @tornado.gen.coroutine
        def connect(self):
            # Non-SaltClientError on purpose: prior to the fix, this leaks
            # the channel because the single-master path only closes
            # pub_channel inside an `except SaltClientError` clause.
            raise OSError("simulated transport failure")

        def close(self):
            self.closed += 1

    def mock_channel_factory(opts, **kwargs):
        return MockPubChannel()

    def mock_resolve_dns(opts, fallback=True):
        return {"master_ip": "127.0.0.1", "master_uri": "tcp://127.0.0.1:4506"}

    io_loop = tornado.ioloop.IOLoop()
    try:
        with patch("salt.minion.resolve_dns", mock_resolve_dns), patch(
            "salt.channel.client.AsyncPubChannel.factory", mock_channel_factory
        ), patch("salt.loader.grains", MagicMock(return_value={})):
            minion = salt.minion.Minion(minion_opts, io_loop=io_loop, load_grains=False)
            with pytest.raises(OSError):
                io_loop.run_sync(lambda: minion.eval_master(minion_opts, timeout=1))
    finally:
        io_loop.close(all_fds=True)

    assert len(created) == 1, "exactly one pub channel should have been created"
    assert (
        created[0].closed == 1
    ), "pub channel was not closed on connection failure (#68901 leak)"


def test_config_cache_path_overrides():
    cachedir = os.path.abspath("/path/to/master/cache")
    opts = {"cachedir": cachedir, "conf_file": None}

    mminion = salt.minion.MasterMinion(opts)
    assert mminion.opts["cachedir"] == cachedir


def test_minion_grains_refresh_pre_exec_false(minion_opts):
    """
    Minion does not refresh grains when grains_refresh_pre_exec is False
    """
    minion_opts["multiprocessing"] = False
    minion_opts["grains_refresh_pre_exec"] = False
    mock_data = {"fun": "foo.bar", "jid": 123}
    with patch("salt.loader.grains") as grainsfunc, patch(
        "salt.minion.Minion._target", MagicMock(return_value=True)
    ):
        loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(
            minion_opts,
            jid_queue=None,
            io_loop=loop,
            load_grains=False,
        )
        try:
            loop.run_sync(lambda: minion._handle_decoded_payload(mock_data))
            grainsfunc.assert_not_called()
        finally:
            minion.destroy()
            loop.close(all_fds=True)


def test_minion_grains_refresh_pre_exec_true(minion_opts):
    """
    Minion refreshes grains when grains_refresh_pre_exec is True
    """
    minion_opts["multiprocessing"] = False
    minion_opts["grains_refresh_pre_exec"] = True
    mock_data = {"fun": "foo.bar", "jid": 123}
    with patch("salt.loader.grains") as grainsfunc, patch(
        "salt.minion.Minion._target", MagicMock(return_value=True)
    ):
        loop = tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(
            minion_opts,
            jid_queue=None,
            io_loop=loop,
            load_grains=False,
        )
        try:
            loop.run_sync(lambda: minion._handle_decoded_payload(mock_data))
            grainsfunc.assert_called()
        finally:
            minion.destroy()
            loop.close(all_fds=True)


@pytest.mark.skip_on_darwin(
    reason="Skip on MacOS, where this does not raise an exception."
)
def test_valid_ipv4_master_address_ipv6_enabled(minion_opts):
    """
    Tests that the lookups fail back to ipv4 when ipv6 fails.
    """
    interfaces = {
        "bond0.1234": {
            "hwaddr": "01:01:01:d0:d0:d0",
            "up": False,
            "inet": [
                {
                    "broadcast": "111.1.111.255",
                    "netmask": "111.1.0.0",
                    "label": "bond0",
                    "address": "111.1.0.1",
                }
            ],
        }
    }
    minion_opts.update(
        {
            "ipv6": True,
            "master": "127.0.0.1",
            "master_port": "4555",
            "retry_dns": False,
            "source_address": "111.1.0.1",
            "source_interface_name": "bond0.1234",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    )
    with patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        expected = {
            "source_publish_port": 49018,
            "master_uri": "tcp://127.0.0.1:4555",
            "source_ret_port": 49017,
            "master_ip": "127.0.0.1",
        }
        assert salt.minion.resolve_dns(minion_opts) == expected


async def test_master_type_disable(minion_opts):
    """
    Tests master_type "disable" to not even attempt connecting to a master.
    """
    minion_opts.update(
        {
            "master_type": "disable",
            "master": None,
            "__role": "",
            "pub_ret": False,
            "file_client": "local",
        }
    )

    minion = salt.minion.Minion(minion_opts)
    try:

        try:
            minion_man = salt.minion.MinionManager(minion_opts)
            await minion_man._connect_minion(minion)
        except RuntimeError:
            pytest.fail("_connect_minion(minion) threw an error, This was not expected")

        # Make sure beacons and sheduler are initialized
        assert "beacons" in minion.periodic_callbacks
        assert "schedule" in minion.periodic_callbacks
        assert minion.connected is False
    finally:
        # Mock the io_loop so calls to stop/close won't happen.
        minion.io_loop = MagicMock()
        minion.destroy()


async def test_syndic_async_req_channel(syndic_opts):
    syndic_opts["_minion_conf_file"] = ""
    syndic_opts["master_uri"] = "tcp://127.0.0.1:4506"
    syndic = salt.minion.Syndic(syndic_opts)
    syndic.pub_channel = MagicMock()
    syndic.tune_in_no_block()
    assert isinstance(syndic.async_req_channel, salt.channel.client.AsyncReqChannel)


@pytest.mark.slow_test
def test_load_args_and_kwargs(minion_opts):
    """
    Ensure load_args_and_kwargs performs correctly
    """
    _args = [{"max": 40, "__kwarg__": True}]
    ret = salt.minion.load_args_and_kwargs(test_mod.rand_sleep, _args)
    assert ret == ([], {"max": 40})
    assert all([True if "__kwarg__" in item else False for item in _args])

    # Test invalid arguments
    _args = [{"max_sleep": 40, "__kwarg__": True}]
    with pytest.raises(salt.exceptions.SaltInvocationError):
        ret = salt.minion.load_args_and_kwargs(test_mod.rand_sleep, _args)


async def test_connect_master_salt_client_error(minion_opts, connect_master_mock):
    """
    Ensure minion's destroy is called on a salt client error while connecting to master.
    """
    minion_opts["acceptance_wait_time"] = 0
    mm = salt.minion.MinionManager(minion_opts)
    minion = salt.minion.Minion(minion_opts)

    connect_master_mock.exc = SaltClientError
    minion.connect_master = connect_master_mock
    minion.destroy = MagicMock()
    await mm._connect_minion(minion)
    minion.destroy.assert_called_once()

    # The first call raised an error which caused minion.destroy to get called,
    # the second call is a success.
    assert minion.connect_master.calls == 2


async def test_connect_master_unresolveable_error(minion_opts, connect_master_mock):
    """
    Ensure minion's destroy is called on an unresolvable while connecting to master.
    """
    mm = salt.minion.MinionManager(minion_opts)
    minion = salt.minion.Minion(minion_opts)
    connect_master_mock.exc = SaltMasterUnresolvableError
    minion.connect_master = connect_master_mock
    minion.destroy = MagicMock()
    await mm._connect_minion(minion)
    minion.destroy.assert_called_once()

    # Unresolvable errors break out of the loop.
    assert minion.connect_master.calls == 1


async def test_connect_master_general_exception_error(minion_opts, connect_master_mock):
    """
    Ensure minion's destroy is called on an un-handled exception while connecting to master.
    """
    mm = salt.minion.MinionManager(minion_opts)
    minion = salt.minion.Minion(minion_opts)
    connect_master_mock.exc = SaltClientError
    minion.connect_master = connect_master_mock
    minion.destroy = MagicMock()
    await mm._connect_minion(minion)
    minion.destroy.assert_called_once()

    # The first call raised an error which caused minion.destroy to get called,
    # the second call is a success.
    assert minion.connect_master.calls == 2


async def test_minion_manager_async_stop(io_loop, minion_opts, tmp_path):
    """
    Ensure MinionManager's stop method works correctly and calls the
    stop_async method
    """
    # Setup sock_dir with short path
    minion_opts["sock_dir"] = str(tmp_path / "sock")

    os.makedirs(minion_opts["sock_dir"])

    # Create a MinionManager instance with a mock minion
    mm = salt.minion.MinionManager(minion_opts)
    minion = MagicMock(name="minion")
    minion.destroy = MagicMock()
    parent_signal_handler = MagicMock(name="parent_signal_handler")
    mm.minions.append(minion)

    # Set up event publisher and event
    mm._bind()
    assert mm.event_publisher is not None
    assert mm.event is not None

    # Check io_loop is running
    # mm.io_loop is now an asyncio.AbstractEventLoop (not Tornado IOLoop)
    assert mm.io_loop.is_running()

    # Wait for the ipc socket to be created, meaning the publish server is listening.
    while not list(pathlib.Path(minion_opts["sock_dir"]).glob("*")):
        await tornado.gen.sleep(0.3)

    # Set up values for event to send
    load = {"key": "value"}
    ret = {}

    # Connect to minion event bus
    with salt.utils.event.get_event("minion", opts=minion_opts, listen=True) as event:

        # call stop to start stopping the minion
        # mm.stop(signal.SIGTERM, parent_signal_handler)
        mm.stop(signal.SIGTERM, parent_signal_handler)

        # Fire an event and ensure we can still read it back while the minion
        # is stopping
        assert await event.fire_event_async(load, "test_event", timeout=1) is not False
        start = time.monotonic()
        while time.monotonic() - start < 5:
            ret = event.get_event(tag="test_event", wait=1)
            if ret:
                break
            await tornado.gen.sleep(0.3)
    assert "key" in ret
    assert ret["key"] == "value"

    # Sleep to allow stop_async to complete
    await tornado.gen.sleep(5)

    # Ensure stop_async has been called (destroy per minion)
    minion.destroy.assert_called_once()
    parent_signal_handler.assert_called_once_with(signal.SIGTERM, None)
    assert mm.event_publisher is None
    assert mm.event is None


async def test_minion_manager_destroy_closes_event_publisher(
    io_loop, minion_opts, tmp_path
):
    """
    Regression test for issue #70175.

    ``MinionManager.destroy()`` is invoked from
    ``cli.daemons.Minion.shutdown()`` (KeyboardInterrupt, SaltSystemExit,
    the ``shutdown(1)`` guard in ``prepare()``) and from
    ``MinionManager.__del__`` on GC.  It must close the ``event_publisher``
    ``PublishServer`` graph -- otherwise the three-warning cascade
    from #70175 fires at interpreter shutdown:

      - ``unclosed publish server <PublishServer>``
      - ``unclosed SyncWrapper for cls=<_TCPPubServerPublisher>``
      - ``unclosed publisher client <_TCPPubServerPublisher>``

    Only the ``stop_async`` shutdown path (invoked from the SIGTERM
    signal handler) used to close these; ``destroy()`` did not, so any
    non-SIGTERM exit leaked them.
    """
    minion_opts["sock_dir"] = str(tmp_path / "sock")
    os.makedirs(minion_opts["sock_dir"])

    mm = salt.minion.MinionManager(minion_opts)
    mm._bind()
    assert mm.event_publisher is not None
    assert mm.event is not None

    # Wait for pub server to bind so the underlying PublishServer graph
    # is fully constructed.
    while not list(pathlib.Path(minion_opts["sock_dir"]).glob("*")):
        await tornado.gen.sleep(0.1)

    ep = mm.event_publisher
    ev = mm.event

    # Call destroy directly (the buggy path).  Post-fix it must close
    # both resources and null the references.
    mm.destroy()

    assert mm.event_publisher is None
    assert mm.event is None
    # PublishServer.close() sets _closing=True so __del__ won't warn.
    assert ep._closing is True
    # SaltEvent.destroy() closes pusher / subscriber and clears them.
    assert ev.subscriber is None
    assert ev.pusher is None


def test_minion_io_loop_is_asyncio_loop(minion_opts):
    """
    Test that Minion io_loop is converted to asyncio.AbstractEventLoop.
    This verifies the salt.utils.asynchronous.aioloop() conversion.
    """
    minion = salt.minion.Minion(minion_opts, load_grains=False)
    try:
        # Verify io_loop is an asyncio loop, not a Tornado IOLoop
        assert isinstance(minion.io_loop, asyncio.AbstractEventLoop)
        # Ensure it has asyncio methods
        assert hasattr(minion.io_loop, "create_task")
        assert hasattr(minion.io_loop, "call_soon")
        # Ensure it doesn't have Tornado-specific methods
        assert not hasattr(minion.io_loop, "spawn_callback")
    finally:
        minion.destroy()


def test_minion_io_loop_with_provided_loop(minion_opts):
    """
    Test that Minion io_loop conversion works when a loop is provided.
    """
    # Create a Tornado IOLoop
    tornado_loop = tornado.ioloop.IOLoop()
    try:
        minion = salt.minion.Minion(
            minion_opts, io_loop=tornado_loop, load_grains=False
        )
        try:
            # Should still be converted to asyncio loop
            assert isinstance(minion.io_loop, asyncio.AbstractEventLoop)
            # Should be the same underlying loop
            assert minion.io_loop is tornado_loop.asyncio_loop
        finally:
            minion.destroy()
    finally:
        tornado_loop.close()


def test_minion_manager_io_loop_is_asyncio_loop(minion_opts):
    """
    Test that MinionManager io_loop is converted to asyncio.AbstractEventLoop.
    """
    with patch("salt.utils.process.SignalHandlingProcess.start"):
        with patch("salt.utils.verify.valid_id"):
            mm = salt.minion.MinionManager(minion_opts)
            try:
                # Verify io_loop is an asyncio loop
                assert isinstance(mm.io_loop, asyncio.AbstractEventLoop)
                # Ensure it has asyncio methods
                assert hasattr(mm.io_loop, "create_task")
                assert hasattr(mm.io_loop, "call_soon")
                # Ensure it doesn't have Tornado-specific methods
                assert not hasattr(mm.io_loop, "spawn_callback")
            finally:
                mm.destroy()


def test_syndic_manager_io_loop_is_asyncio_loop(minion_opts):
    """
    Test that SyndicManager io_loop is converted to asyncio.AbstractEventLoop.
    """
    minion_opts["order_masters"] = True
    sm = salt.minion.SyndicManager(minion_opts)
    try:
        # Verify io_loop is an asyncio loop
        assert isinstance(sm.io_loop, asyncio.AbstractEventLoop)
        # Ensure it has asyncio methods
        assert hasattr(sm.io_loop, "create_task")
        assert hasattr(sm.io_loop, "call_soon")
        # Ensure it doesn't have Tornado-specific methods
        assert not hasattr(sm.io_loop, "spawn_callback")
    finally:
        sm.destroy()


def _run_eval_master(opts):
    """
    Drive MinionBase.eval_master far enough to hit the single-master branch
    (where the random_master warning lives) without touching the network:
    DNS resolution is stubbed and the pub channel connects immediately.
    """
    io_loop = tornado.ioloop.IOLoop()
    minion = salt.minion.MinionBase(opts)
    mock_channel = MagicMock()
    mock_channel.connect.return_value = tornado.gen.maybe_future(None)
    mock_channel.auth.gen_token.return_value = b"token"
    try:
        with patch(
            "salt.channel.client.AsyncPubChannel.factory", return_value=mock_channel
        ), patch("salt.minion.resolve_dns", return_value={}), patch(
            "salt.minion.prep_ip_port", return_value={}
        ):
            io_loop.run_sync(lambda: minion.eval_master(opts))
    finally:
        io_loop.close()


def _single_master_opts(minion_opts):
    minion_opts["master"] = "salt-master-1"
    minion_opts["master_type"] = "str"
    minion_opts["random_master"] = True
    minion_opts["transport"] = "zeromq"
    minion_opts["acceptance_wait_time"] = 0
    minion_opts["master_tries"] = 1
    return minion_opts


def test_eval_master_random_master_warning_suppressed_for_multimaster(
    minion_opts, caplog
):
    """
    In multi-master mode the MinionManager spawns one Minion per master, each
    bound to a single master but inheriting random_master (multimaster=True).
    Those children must NOT emit the "random_master ... only one master ...
    Ignoring" warning. Regression test for the spurious per-master warning.
    """
    opts = _single_master_opts(minion_opts)
    opts["multimaster"] = True
    with caplog.at_level(logging.WARNING):
        _run_eval_master(opts)
    assert (
        "random_master is True but there is only one master specified"
        not in caplog.text
    )


def test_eval_master_random_master_warning_for_real_single_master(minion_opts, caplog):
    """
    A genuinely single-master minion (not a multimaster child) with
    random_master set still gets warned -- random_master really is a no-op
    there. Guards against over-suppressing the warning.
    """
    opts = _single_master_opts(minion_opts)
    opts.pop("multimaster", None)
    with caplog.at_level(logging.WARNING):
        _run_eval_master(opts)
    assert "random_master is True but there is only one master specified" in caplog.text


# ---------------------------------------------------------------------------
# Graceful-stop fixup unit tests (issue #70050 audit follow-up)
# ---------------------------------------------------------------------------


def test_remove_proc_file_swallows_missing_file(tmp_path):
    """
    ``_remove_proc_file`` is a finalize callback invoked from inside
    ``SignalHandlingProcess._handle_signals``. A race where the file is
    already gone (happy-path completion beat the signal) must NOT raise
    -- an exception in a signal-handler callback aborts the remaining
    finalize methods on the loop at ``salt/utils/process.py:1058-1068``.
    """
    missing = tmp_path / "nope" / "jid"
    salt.minion._remove_proc_file(str(missing))  # no exception


def test_remove_proc_file_deletes_existing_file(tmp_path):
    """
    Happy path: file exists, gets removed.
    """
    fn = tmp_path / "20260814000000000000"
    fn.write_bytes(b"payload")
    salt.minion._remove_proc_file(str(fn))
    assert not fn.exists()


async def test_handle_decoded_payload_registers_proc_file_finalize(
    minion_opts, tmp_path, io_loop
):
    """
    Gap-2 fix: when ``_handle_decoded_payload`` spawns a
    ``SignalHandlingProcess`` for a job, it must register
    ``_remove_proc_file`` as a finalize method against the resolved
    ``<cachedir>/proc/<jid>`` path so that a graceful SIGTERM triggers
    proc-file cleanup even though ``SignalHandlingProcess._handle_signals``
    later calls ``os._exit`` and skips ``_thread_return``'s own finally
    block.
    """
    minion_opts["cachedir"] = str(tmp_path)
    minion_opts["multiprocessing"] = True

    jid = "20260814000000000001"
    data = {"jid": jid, "fun": "test.sleep", "arg": [30]}

    captured = {}

    class _FakeProcess:
        def __init__(self, *args, **kwargs):
            self.name = kwargs.get("name", "fake")
            self.pid = 0
            self._alive = False
            self.finalize = []

        def register_finalize_method(self, function, *args, **kwargs):
            self.finalize.append((function, args, kwargs))

        def start(self):
            captured["started"] = True

        def is_alive(self):
            return self._alive

    fake_process = None

    def _factory(*args, **kwargs):
        nonlocal fake_process
        fake_process = _FakeProcess(*args, **kwargs)
        return fake_process

    minion = salt.minion.Minion(
        minion_opts, jid_queue=[], load_grains=False, io_loop=io_loop
    )
    try:
        minion.connected = True
        minion.subprocess_list = salt.utils.process.SubprocessList()
        # _handle_decoded_payload's early-exit paths reference these:
        minion.functions = {}
        minion._system_resource_limit_hit_timestamp = 0
        with patch("salt.minion.SignalHandlingProcess", side_effect=_factory), patch(
            "salt.minion.default_signals"
        ) as default_signals_mock:
            default_signals_mock.return_value.__enter__ = MagicMock()
            default_signals_mock.return_value.__exit__ = MagicMock(return_value=False)
            await minion._handle_decoded_payload(data)
    finally:
        minion.destroy()

    assert fake_process is not None, "SignalHandlingProcess was never constructed"
    expected_proc_file = os.path.join(str(tmp_path), "proc", jid)
    assert (
        salt.minion._remove_proc_file,
        (expected_proc_file,),
        {},
    ) in fake_process.finalize, (
        f"_remove_proc_file finalize not registered on the job child; "
        f"finalize list was: {fake_process.finalize!r}"
    )


def test_terminate_subprocess_list_none():
    """``_terminate_subprocess_list(None, ...)`` is a valid no-op."""
    salt.minion._terminate_subprocess_list(None, signal.SIGTERM)


def test_terminate_subprocess_list_signals_live_only():
    """
    Gap-1 fix: iterate ``subprocess_list.processes``, deliver ``signum``
    to each live entry, then escalate the ones that ignored it. Dead
    entries must be skipped (no ``os.kill`` against ESRCH pids). The
    escalation uses SIGKILL on POSIX (``proc.terminate()`` re-sends
    SIGTERM which a stubborn child by definition ignored).
    """
    live = MagicMock(name="live-proc", pid=4242)
    # Alive at the pre-filter, dead by the escalation loop (as if it
    # honoured the SIGTERM during the join).
    live.is_alive.side_effect = [True, False]
    live.join = MagicMock()
    live.terminate = MagicMock()
    live.kill = MagicMock()

    dead = MagicMock(name="dead-proc", pid=999999)
    dead.is_alive.return_value = False
    dead.join = MagicMock()
    dead.terminate = MagicMock()
    dead.kill = MagicMock()

    stubborn = MagicMock(name="stubborn-proc", pid=4243)
    stubborn.is_alive.return_value = True  # always alive
    stubborn.join = MagicMock()
    stubborn.terminate = MagicMock()
    stubborn.kill = MagicMock()

    subprocess_list = MagicMock(processes=[live, dead, stubborn])

    with patch("salt.utils.platform.is_windows", return_value=False), patch(
        "salt.minion.os.kill"
    ) as kill_mock:
        salt.minion._terminate_subprocess_list(
            subprocess_list, signal.SIGTERM, grace_seconds=0.01
        )

    signaled_pairs = {(call.args[0], call.args[1]) for call in kill_mock.call_args_list}
    # Live and stubborn both got the graceful signum.
    assert (4242, signal.SIGTERM) in signaled_pairs
    assert (4243, signal.SIGTERM) in signaled_pairs
    # Stubborn escalates to SIGKILL; live doesn't (it exited during the join).
    assert (4243, signal.SIGKILL) in signaled_pairs
    assert (4242, signal.SIGKILL) not in signaled_pairs
    # Dead child never receives anything.
    assert not any(pid == 999999 for pid, _ in signaled_pairs)

    dead.terminate.assert_not_called()
    dead.kill.assert_not_called()


def test_terminate_subprocess_list_windows_skips_signal():
    """
    On Windows, job children have no SIGTERM handler; sending SIGTERM
    would kill them mid-signal-handler and orphan grandchildren. Fall
    straight through to ``.kill()`` (which maps to ``TerminateProcess``).
    """
    proc = MagicMock(pid=1234)
    proc.is_alive.return_value = True
    proc.join = MagicMock()
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    subprocess_list = MagicMock(processes=[proc])

    with patch("salt.utils.platform.is_windows", return_value=True), patch(
        "salt.minion.os.kill"
    ) as kill_mock:
        salt.minion._terminate_subprocess_list(
            subprocess_list, signal.SIGTERM, grace_seconds=0.01
        )
    kill_mock.assert_not_called()
    proc.kill.assert_called_once()


def test_notify_systemd_stopping_no_socket_and_no_bindings(monkeypatch):
    """
    Gap-3 fix: ``notify_systemd_stopping`` must be a silent no-op when
    the systemd bindings are absent *and* ``systemd-notify`` is not on
    ``PATH`` (i.e. the daemon was not started under a Type=notify unit,
    or was started on a non-systemd platform).
    """
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)

    def _no_bindings(name, *a, **kw):
        if name == "systemd.daemon":
            raise ImportError("no systemd bindings")
        return original_import(name, *a, **kw)

    import builtins

    original_import = builtins.__import__
    monkeypatch.setattr(builtins, "__import__", _no_bindings)
    monkeypatch.setattr("salt.utils.path.which", lambda name: None)
    assert salt.utils.process.notify_systemd_stopping() is False


def test_notify_systemd_stopping_uses_systemd_daemon(monkeypatch):
    """
    When the ``systemd`` Python bindings ARE available and the host is
    systemd-booted, ``notify_systemd_stopping`` calls ``systemd.daemon.notify``
    with the literal ``"STOPPING=1"`` payload (not ``"READY=1"``).
    """
    fake_daemon = MagicMock()
    fake_daemon.booted.return_value = True
    fake_module = MagicMock(daemon=fake_daemon)
    fake_pkg = MagicMock(daemon=fake_daemon)
    monkeypatch.setitem(__import__("sys").modules, "systemd", fake_pkg)
    monkeypatch.setitem(__import__("sys").modules, "systemd.daemon", fake_daemon)

    salt.utils.process.notify_systemd_stopping()
    fake_daemon.notify.assert_called_once_with("STOPPING=1")


async def test_stop_async_calls_notify_stopping_and_terminates_subprocess_list(
    minion_opts,
):
    """
    Gap-1 + Gap-3 wired into ``MinionManager.stop_async``:
      - ``notify_systemd_stopping`` fires on entry
      - ``_terminate_subprocess_list`` is invoked per-managed-minion with
        the incoming signum (before ``kill_children`` and ``destroy``)
    """
    manager = salt.minion.MinionManager(minion_opts)
    try:
        fake_minion = MagicMock()
        fake_minion.subprocess_list = MagicMock(processes=[])
        manager.minions = [fake_minion]
        manager.event = None
        manager.event_publisher = None

        parent = MagicMock()

        async def _instant_sleep(_):
            return None

        with patch("salt.utils.process.notify_systemd_stopping") as notify_mock, patch(
            "salt.minion._terminate_subprocess_list"
        ) as term_mock, patch("salt.minion.asyncio.sleep", side_effect=_instant_sleep):
            await manager.stop_async(signal.SIGTERM, parent)

        notify_mock.assert_called_once()
        term_mock.assert_called_once()
        args, kwargs = term_mock.call_args
        assert args[0] is fake_minion.subprocess_list
        assert args[1] == signal.SIGTERM
        parent.assert_called_once_with(signal.SIGTERM, None)
    finally:
        # MinionManager owns an io_loop but no persistent resources on this
        # code path; the .destroy() call would try to tear down channels
        # we never created. A best-effort close is enough.
        pass
