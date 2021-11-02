import copy
import logging
import os

import pytest
import salt.ext.tornado
import salt.ext.tornado.gen
import salt.ext.tornado.testing
import salt.minion
import salt.syspaths
import salt.utils.crypt
import salt.utils.event as event
import salt.utils.platform
import salt.utils.process
from salt._compat import ipaddress
from salt.exceptions import SaltClientError, SaltMasterUnresolvableError, SaltSystemExit
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def test_minion_load_grains_false():
    """
    Minion does not generate grains when load_grains is False
    """
    opts = {"random_startup_delay": 0, "grains": {"foo": "bar"}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=False)
        assert minion.opts["grains"] == opts["grains"]
        grainsfunc.assert_not_called()


def test_minion_load_grains_true():
    """
    Minion generates grains when load_grains is True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=True)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()


def test_minion_load_grains_default():
    """
    Minion load_grains defaults to True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()


@pytest.mark.parametrize(
    "req_channel",
    [
        (
            "salt.transport.client.AsyncReqChannel.factory",
            lambda load, timeout, tries: salt.ext.tornado.gen.maybe_future(tries),
        ),
        (
            "salt.transport.client.ReqChannel.factory",
            lambda load, timeout, tries: tries,
        ),
    ],
)
def test_send_req_tries(req_channel):
    channel_enter = MagicMock()
    channel_enter.send.side_effect = req_channel[1]
    channel = MagicMock()
    channel.__enter__.return_value = channel_enter

    with patch(req_channel[0], return_value=channel):
        opts = {
            "random_startup_delay": 0,
            "grains": {},
            "return_retry_tries": 30,
            "minion_sign_messages": False,
        }
        with patch("salt.loader.grains"):
            minion = salt.minion.Minion(opts)

            load = {"load": "value"}
            timeout = 60

            if "Async" in req_channel[0]:
                rtn = minion._send_req_async(load, timeout).result()
            else:
                rtn = minion._send_req_sync(load, timeout)

            assert rtn == 30


@patch("salt.transport.client.ReqChannel.factory")
def test_mine_send_tries(req_channel_factory):
    channel_enter = MagicMock()
    channel_enter.send.side_effect = lambda load, timeout, tries: tries
    channel = MagicMock()
    channel.__enter__.return_value = channel_enter
    req_channel_factory.return_value = channel

    opts = {
        "random_startup_delay": 0,
        "grains": {},
        "return_retry_tries": 20,
        "minion_sign_messages": False,
    }
    with patch("salt.loader.grains"):
        minion = salt.minion.Minion(opts)
        minion.tok = "token"

        data = {}
        tag = "tag"

        rtn = minion._mine_send(tag, data)
        assert rtn == 20


def test_invalid_master_address():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(
        opts,
        {
            "ipv6": False,
            "master": float("127.0"),
            "master_port": "4555",
            "retry_dns": False,
        },
    ):
        pytest.raises(SaltSystemExit, salt.minion.resolve_dns, opts)


def test_source_int_name_local():
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
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(
        opts,
        {
            "ipv6": False,
            "master": "127.0.0.1",
            "master_port": "4555",
            "file_client": "local",
            "source_interface_name": "bond0.1234",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    ), patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(opts) == {
            "master_ip": "127.0.0.1",
            "source_ip": "111.1.0.1",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
            "master_uri": "tcp://127.0.0.1:4555",
        }


@pytest.mark.slow_test
def test_source_int_name_remote():
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
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(
        opts,
        {
            "ipv6": False,
            "master": "127.0.0.1",
            "master_port": "4555",
            "file_client": "remote",
            "source_interface_name": "bond0.1234",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
        },
    ), patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(opts) == {
            "master_ip": "127.0.0.1",
            "source_ret_port": 49017,
            "source_publish_port": 49018,
            "master_uri": "tcp://127.0.0.1:4555",
        }


@pytest.mark.slow_test
def test_source_address():
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
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(
        opts,
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
    ), patch("salt.utils.network.interfaces", MagicMock(return_value=interfaces)):
        assert salt.minion.resolve_dns(opts) == {
            "source_publish_port": 49018,
            "source_ret_port": 49017,
            "master_uri": "tcp://127.0.0.1:4555",
            "source_ip": "111.1.0.1",
            "master_ip": "127.0.0.1",
        }


# Tests for _handle_decoded_payload in the salt.minion.Minion() class: 3
@pytest.mark.slow_test
def test_handle_decoded_payload_jid_match_in_jid_queue():
    """
    Tests that the _handle_decoded_payload function returns when a jid is given that is already present
    in the jid_queue.

    Note: This test doesn't contain all of the patch decorators above the function like the other tests
    for _handle_decoded_payload below. This is essential to this test as the call to the function must
    return None BEFORE any of the processes are spun up because we should be avoiding firing duplicate
    jobs.
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_data = {"fun": "foo.bar", "jid": 123}
    mock_jid_queue = [123]
    minion = salt.minion.Minion(
        mock_opts,
        jid_queue=copy.copy(mock_jid_queue),
        io_loop=salt.ext.tornado.ioloop.IOLoop(),
    )
    try:
        ret = minion._handle_decoded_payload(mock_data).result()
        assert minion.jid_queue == mock_jid_queue
        assert ret is None
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_handle_decoded_payload_jid_queue_addition():
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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_data = {"fun": "foo.bar", "jid": mock_jid}
        mock_jid_queue = [123, 456]
        minion = salt.minion.Minion(
            mock_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=salt.ext.tornado.ioloop.IOLoop(),
        )
        try:

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            assert minion.jid_queue == mock_jid_queue

            # Call the _handle_decoded_payload function and update the mock_jid_queue to include the new
            # mock_jid. The mock_jid should have been added to the jid_queue since the mock_jid wasn't
            # previously included. The minion's jid_queue attribute and the mock_jid_queue should be equal.
            minion._handle_decoded_payload(mock_data).result()
            mock_jid_queue.append(mock_jid)
            assert minion.jid_queue == mock_jid_queue
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_handle_decoded_payload_jid_queue_reduced_minion_jid_queue_hwm():
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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["minion_jid_queue_hwm"] = 2
        mock_data = {"fun": "foo.bar", "jid": 789}
        mock_jid_queue = [123, 456]
        minion = salt.minion.Minion(
            mock_opts,
            jid_queue=copy.copy(mock_jid_queue),
            io_loop=salt.ext.tornado.ioloop.IOLoop(),
        )
        try:

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            assert minion.jid_queue == mock_jid_queue

            # Call the _handle_decoded_payload function and check that the queue is smaller by one item
            # and contains the new jid
            minion._handle_decoded_payload(mock_data).result()
            assert len(minion.jid_queue) == 2
            assert minion.jid_queue == [456, 789]
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_process_count_max():
    """
    Tests that the _handle_decoded_payload function does not spawn more than the configured amount of processes,
    as per process_count_max.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.utils.process.SignalHandlingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingProcess.join",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.minion.running", MagicMock(return_value=[])
    ), patch(
        "salt.ext.tornado.gen.sleep",
        MagicMock(return_value=salt.ext.tornado.concurrent.Future()),
    ):
        process_count_max = 10
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["__role"] = "minion"
        mock_opts["minion_jid_queue_hwm"] = 100
        mock_opts["process_count_max"] = process_count_max

        io_loop = salt.ext.tornado.ioloop.IOLoop()
        minion = salt.minion.Minion(mock_opts, jid_queue=[], io_loop=io_loop)
        try:

            # mock gen.sleep to throw a special Exception when called, so that we detect it
            class SleepCalledException(Exception):
                """Thrown when sleep is called"""

            salt.ext.tornado.gen.sleep.return_value.set_exception(
                SleepCalledException()
            )

            # up until process_count_max: gen.sleep does not get called, processes are started normally
            for i in range(process_count_max):
                mock_data = {"fun": "foo.bar", "jid": i}
                io_loop.run_sync(
                    lambda data=mock_data: minion._handle_decoded_payload(data)
                )
                assert (
                    salt.utils.process.SignalHandlingProcess.start.call_count == i + 1
                )
                assert len(minion.jid_queue) == i + 1
                salt.utils.minion.running.return_value += [i]

            # above process_count_max: gen.sleep does get called, JIDs are created but no new processes are started
            mock_data = {"fun": "foo.bar", "jid": process_count_max + 1}

            pytest.raises(
                SleepCalledException,
                lambda: io_loop.run_sync(
                    lambda: minion._handle_decoded_payload(mock_data)
                ),
            )
            assert (
                salt.utils.process.SignalHandlingProcess.start.call_count
                == process_count_max
            )
            assert len(minion.jid_queue) == process_count_max + 1
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_beacons_before_connect():
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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["beacons_before_connect"] = True
        io_loop = salt.ext.tornado.ioloop.IOLoop()
        io_loop.make_current()
        minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
        try:

            try:
                minion.tune_in(start=True)
            except RuntimeError:
                pass

            # Make sure beacons are initialized but the sheduler is not
            assert "beacons" in minion.periodic_callbacks
            assert "schedule" not in minion.periodic_callbacks
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_scheduler_before_connect():
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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["scheduler_before_connect"] = True
        io_loop = salt.ext.tornado.ioloop.IOLoop()
        io_loop.make_current()
        minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
        try:
            try:
                minion.tune_in(start=True)
            except RuntimeError:
                pass

            # Make sure the scheduler is initialized but the beacons are not
            assert "schedule" in minion.periodic_callbacks
            assert "beacons" not in minion.periodic_callbacks
        finally:
            minion.destroy()


def test_minion_module_refresh():
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
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
            minion = salt.minion.Minion(
                mock_opts,
                io_loop=salt.ext.tornado.ioloop.IOLoop(),
            )
            minion.schedule = salt.utils.schedule.Schedule(mock_opts, {}, returners={})
            assert hasattr(minion, "schedule")
            minion.destroy()
            assert not hasattr(minion, "schedule")
            assert not minion.module_refresh()
        finally:
            minion.destroy()


def test_minion_module_refresh_beacons_refresh():
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
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
            minion = salt.minion.Minion(
                mock_opts,
                io_loop=salt.ext.tornado.ioloop.IOLoop(),
            )
            minion.schedule = salt.utils.schedule.Schedule(mock_opts, {}, returners={})
            assert not hasattr(minion, "beacons")
            minion.module_refresh()
            assert hasattr(minion, "beacons")
            assert hasattr(minion.beacons, "beacons")
            assert "service.beacon" in minion.beacons.beacons
            minion.destroy()
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_when_ping_interval_is_set_the_callback_should_be_added_to_periodic_callbacks():
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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts["ping_interval"] = 10
        io_loop = salt.ext.tornado.ioloop.IOLoop()
        io_loop.make_current()
        minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
        try:
            try:
                minion.connected = MagicMock(side_effect=(False, True))
                minion._fire_master_minion_start = MagicMock()
                minion.tune_in(start=False)
            except RuntimeError:
                pass

            # Make sure the scheduler is initialized but the beacons are not
            assert "ping" in minion.periodic_callbacks
        finally:
            minion.destroy()


@pytest.mark.slow_test
def test_when_passed_start_event_grains():
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    # provide mock opts an os grain since we'll look for it later.
    mock_opts["grains"]["os"] = "linux"
    mock_opts["start_event_grains"] = ["os"]
    io_loop = salt.ext.tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
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
def test_when_not_passed_start_event_grains():
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    io_loop = salt.ext.tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._send_req_sync = MagicMock()
        minion._fire_master("Minion has started", "minion_start")
        load = minion._send_req_sync.call_args[0][0]

        assert "grains" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_when_other_events_fired_and_start_event_grains_are_set():
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts["start_event_grains"] = ["os"]
    io_loop = salt.ext.tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
    try:
        minion.tok = MagicMock()
        minion._send_req_sync = MagicMock()
        minion._fire_master("Custm_event_fired", "custom_event")
        load = minion._send_req_sync.call_args[0][0]

        assert "grains" not in load
    finally:
        minion.destroy()


@pytest.mark.slow_test
def test_minion_retry_dns_count():
    """
    Tests that the resolve_dns will retry dns look ups for a maximum of
    3 times before raising a SaltMasterUnresolvableError exception.
    """
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(
        opts,
        {
            "ipv6": False,
            "master": "dummy",
            "master_port": "4555",
            "retry_dns": 1,
            "retry_dns_count": 3,
        },
    ):
        pytest.raises(SaltMasterUnresolvableError, salt.minion.resolve_dns, opts)


@pytest.mark.slow_test
def test_gen_modules_executors():
    """
    Ensure gen_modules is called with the correct arguments #54429
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    io_loop = salt.ext.tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(mock_opts, io_loop=io_loop)

    class MockPillarCompiler:
        def compile_pillar(self):
            return {}

    try:
        with patch("salt.pillar.get_pillar", return_value=MockPillarCompiler()):
            with patch("salt.loader.executors") as execmock:
                minion.gen_modules()
        assert execmock.called_with(minion.opts, minion.functions)
    finally:
        minion.destroy()


@patch("salt.utils.process.default_signals")
@pytest.mark.slow_test
def test_reinit_crypto_on_fork(def_mock):
    """
    Ensure salt.utils.crypt.reinit_crypto() is executed when forking for new job
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts["multiprocessing"] = True

    io_loop = salt.ext.tornado.ioloop.IOLoop()
    io_loop.make_current()
    minion = salt.minion.Minion(mock_opts, io_loop=io_loop)

    job_data = {"jid": "test-jid", "fun": "test.ping"}

    def mock_start(self):
        # pylint: disable=comparison-with-callable
        assert (
            len(
                [
                    x
                    for x in self._after_fork_methods
                    if x[0] == salt.utils.crypt.reinit_crypto
                ]
            )
            == 1
        )
        # pylint: enable=comparison-with-callable

    with patch.object(salt.utils.process.SignalHandlingProcess, "start", mock_start):
        io_loop.run_sync(lambda: minion._handle_decoded_payload(job_data))


def test_minion_manage_schedule():
    """
    Tests that the manage_schedule will call the add function, adding
    schedule data into opts.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingMultiprocessingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingMultiprocessingProcess.join",
        MagicMock(return_value=True),
    ):
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        io_loop = salt.ext.tornado.ioloop.IOLoop()
        io_loop.make_current()

        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            try:
                mock_functions = {"test.ping": None}

                minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
                minion.schedule = salt.utils.schedule.Schedule(
                    mock_opts,
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


def test_minion_manage_beacons():
    """
    Tests that the manage_beacons will call the add function, adding
    beacon data into opts.
    """
    with patch("salt.minion.Minion.ctx", MagicMock(return_value={})), patch(
        "salt.minion.Minion.sync_connect_master",
        MagicMock(side_effect=RuntimeError("stop execution")),
    ), patch(
        "salt.utils.process.SignalHandlingMultiprocessingProcess.start",
        MagicMock(return_value=True),
    ), patch(
        "salt.utils.process.SignalHandlingMultiprocessingProcess.join",
        MagicMock(return_value=True),
    ):
        try:
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
            mock_opts["beacons"] = {}

            io_loop = salt.ext.tornado.ioloop.IOLoop()
            io_loop.make_current()

            mock_functions = {"test.ping": None}
            minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
            minion.beacons = salt.beacons.Beacon(mock_opts, mock_functions)

            bdata = [{"salt-master": "stopped"}, {"apache2": "stopped"}]
            data = {"name": "ps", "beacon_data": bdata, "func": "add"}

            tag = "manage_beacons"
            log.debug("==== minion.opts %s ====", minion.opts)

            minion.manage_beacons(tag, data)
            assert "ps" in minion.opts["beacons"]
            assert minion.opts["beacons"]["ps"] == bdata
        finally:
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


@pytest.mark.skip_if_not_root
def test_sock_path_len():
    """
    This tests whether or not a larger hash causes the sock path to exceed
    the system's max sock path length. See the below link for more
    information.

    https://github.com/saltstack/salt/issues/12172#issuecomment-43903643
    """
    opts = {
        "id": "salt-testing",
        "hash_type": "sha512",
        "sock_dir": os.path.join(salt.syspaths.SOCK_DIR, "minion"),
        "extension_modules": "",
    }
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    with patch.dict(opts, opts):
        try:
            event_publisher = event.AsyncEventPublisher(opts)
            result = True
        except ValueError:
            #  There are rare cases where we operate a closed socket, especially in containers.
            # In this case, don't fail the test because we'll catch it down the road.
            result = True
        except SaltSystemExit:
            result = False
    assert result


@pytest.mark.skip_on_windows(reason="Skippin, no Salt master running on Windows.")
def test_master_type_failover():
    """
    Tests master_type "failover" to not fall back to 127.0.0.1 address when master does not resolve in DNS
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts.update(
        {
            "master_type": "failover",
            "master": ["master1", "master2"],
            "__role": "",
            "retry_dns": 0,
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

    def mock_transport_factory(opts, **kwargs):
        assert opts["master"] == "master2"
        return MockPubChannel()

    with patch("salt.minion.resolve_dns", mock_resolve_dns), patch(
        "salt.transport.client.AsyncPubChannel.factory", mock_transport_factory
    ), patch("salt.loader.grains", MagicMock(return_value=[])):
        with pytest.raises(SaltClientError):
            minion = salt.minion.Minion(mock_opts)
            yield minion.connect_master()


def test_master_type_failover_no_masters():
    """
    Tests master_type "failover" to not fall back to 127.0.0.1 address when no master can be resolved
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts.update(
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
            minion = salt.minion.Minion(mock_opts)
            yield minion.connect_master()


def test_config_cache_path_overrides():
    cachedir = os.path.abspath("/path/to/master/cache")
    opts = {"cachedir": cachedir, "conf_file": None}

    mminion = salt.minion.MasterMinion(opts)
    assert mminion.opts["cachedir"] == cachedir
