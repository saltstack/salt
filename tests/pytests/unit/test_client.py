import asyncio
import copy
import logging
import os

import pytest
import tornado.gen
import tornado.ioloop

import salt.client as client
import salt.config
from salt.exceptions import SaltClientError, SaltInvocationError, SaltReqTimeoutError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def master_opts(tmp_path):
    opts = salt.config.master_config(
        os.path.join(os.path.dirname(client.__file__), "master")
    )
    opts["cachedir"] = str(tmp_path / "cache")
    opts["pki_dir"] = str(tmp_path / "pki")
    opts["sock_dir"] = str(tmp_path / "sock")
    opts["token_dir"] = str(tmp_path / "tokens")
    opts["token_file"] = str(tmp_path / "token")
    opts["syndic_dir"] = str(tmp_path / "syndics")
    opts["sqlite_queue_dir"] = str(tmp_path / "queue")
    return opts


def test_cmd_subset_not_cli(master_opts):
    """
    Test LocalClient.cmd_subset when cli=False (default)
    """
    salt_local_client = client.LocalClient(mopts=master_opts)

    # cmd_subset first calls self.cmd(..., "sys.list_functions", ...)
    # Then it calls self.cmd with the chosen subset.
    def mock_cmd(tgt, fun, *args, **kwargs):
        if fun == "sys.list_functions":
            return {
                "minion1": ["first.func", "second.func"],
                "minion2": ["first.func", "second.func"],
            }
        return {tgt[0]: True}  # Return for the actual subset call

    with patch.object(client.LocalClient, "cmd", side_effect=mock_cmd) as cmd_mock:
        # subset=1, so it should pick one minion.
        ret = salt_local_client.cmd_subset("*", "first.func", subset=1, cli=False)

        # Verify the second call (the actual execution) targeted either minion1 or minion2
        assert cmd_mock.call_count == 2
        # Check if either minion1 or minion2 was targeted in the final call
        target_called = cmd_mock.call_args[0][0]
        assert target_called in (["minion1"], ["minion2"])


def test_job_result_return_success(master_opts):
    """
    Should return the `expected_return`, since there is a job with the right jid.
    """
    minions = ()
    jid = "0815"
    raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
    expected_return = {"fake-id": {"ret": "fake-return"}}
    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.event.get_event = MagicMock(return_value=raw_return)
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        val = next(ret)
        assert val == expected_return


def test_job_result_return_uses_resource_id_key(master_opts):
    """
    Resource returns carry ``resource_id`` while ``id`` stays the managing minion;
    the client must key CLI output by resource id.
    """
    minions = ()
    jid = "0815"
    raw_return = {
        "id": "minion-1",
        "resource_id": "m1-dummy1",
        "jid": jid,
        "return": True,
    }
    expected_return = {"m1-dummy1": {"ret": True}}
    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.event.get_event = MagicMock(return_value=raw_return)
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        val = next(ret)
        assert val == expected_return


def test_get_iter_returns_resource_id_display_key(master_opts):
    jid = "20260101000000000001"

    def returns_iter():
        yield {
            "tag": f"salt/job/{jid}/ret/m1-dummy1",
            "data": {
                "return": True,
                "id": "minion-1",
                "resource_id": "m1-dummy1",
                "jid": jid,
            },
        }

    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.returns_for_job = MagicMock(return_value=True)
        local_client.get_returns_no_block = MagicMock(return_value=returns_iter())
        out = list(
            local_client.get_iter_returns(
                jid, {"minion-1", "m1-dummy1"}, gather_job_timeout=1
            )
        )
    assert out == [{"m1-dummy1": {"ret": True, "jid": jid}}]


def test_iter_failed_missing_returns_expands_managed_resources(master_opts):
    from salt.client import _iter_failed_missing_returns

    class _FakeReg:
        def get_resources_for_minion(self, mid):
            if mid == "minion-1":
                return {"dummy": ["r1", "r2"]}
            return {}

    class _FakeCk:
        registry = _FakeReg()

    with patch("salt.utils.minions.CkMinions", return_value=_FakeCk()):
        keys = [
            next(iter(chunk))
            for chunk in _iter_failed_missing_returns(master_opts, set(), {"minion-1"})
        ]
    assert keys == ["minion-1", "r1", "r2"]


def test_iter_failed_missing_returns_uses_grains_when_registry_empty(master_opts):
    """
    Offline minions may disappear from the mmap registry before the CLI runs;
    ``salt_resources`` in minion_data_cache must still drive expansion.
    """
    from salt.client import _iter_failed_missing_returns

    class _FakeReg:
        def get_resources_for_minion(self, mid):
            return {}

    class _FakeCk:
        registry = _FakeReg()

    class _FakeCache:
        def contains(self, bank, key):
            return bank == "grains" and key == "minion-3"

        def fetch(self, bank, key):
            return {
                "salt_resources": {
                    "dummy": ["m3-dummy1", "m3-dummy2", "m3-dummy3"],
                }
            }

    mopts = dict(master_opts)
    mopts["minion_data_cache"] = True

    with patch("salt.utils.minions.CkMinions", return_value=_FakeCk()):
        with patch("salt.cache.factory", return_value=_FakeCache()):
            keys = [
                next(iter(chunk))
                for chunk in _iter_failed_missing_returns(mopts, set(), {"minion-3"})
            ]
    assert keys == ["minion-3", "m3-dummy1", "m3-dummy2", "m3-dummy3"]


def test_iter_failed_missing_returns_uses_pillar_when_registry_and_grains_empty(
    master_opts,
):
    from salt.client import _iter_failed_missing_returns

    class _FakeReg:
        def get_resources_for_minion(self, mid):
            return {}

    class _FakeCk:
        registry = _FakeReg()

    class _FakeCache:
        def __init__(self):
            self._grains = {}
            self._pillar = {
                "minion-3": {
                    "resources": {
                        "dummy": {
                            "resource_ids": [
                                "m3-dummy1",
                                "m3-dummy2",
                                "m3-dummy3",
                            ],
                        },
                    },
                }
            }

        def contains(self, bank, key):
            if bank == "grains":
                return key in self._grains
            if bank == "pillar":
                return key in self._pillar
            return False

        def fetch(self, bank, key):
            if bank == "grains":
                return self._grains.get(key, {})
            if bank == "pillar":
                return self._pillar.get(key, {})
            return {}

    mopts = dict(master_opts)
    mopts["minion_data_cache"] = True

    with patch("salt.utils.minions.CkMinions", return_value=_FakeCk()):
        with patch("salt.cache.factory", return_value=_FakeCache()):
            keys = [
                next(iter(chunk))
                for chunk in _iter_failed_missing_returns(mopts, set(), {"minion-3"})
            ]
    assert keys == ["minion-3", "m3-dummy1", "m3-dummy2", "m3-dummy3"]


def test_iter_failed_missing_returns_skips_resources_already_found(master_opts):
    from salt.client import _iter_failed_missing_returns

    class _FakeReg:
        def get_resources_for_minion(self, mid):
            if mid == "minion-1":
                return {"dummy": ["r1", "r2"]}
            return {}

    class _FakeCk:
        registry = _FakeReg()

    with patch("salt.utils.minions.CkMinions", return_value=_FakeCk()):
        keys = [
            next(iter(chunk))
            for chunk in _iter_failed_missing_returns(master_opts, {"r1"}, {"minion-1"})
        ]
    assert keys == ["minion-1", "r2"]


def test_iter_failed_missing_returns_pki_minions_before_bare_resource_ids(master_opts):
    """
    Glob wait-lists sort bare resource IDs before managing minions; PKI minions
    must still be expanded first so pillar/registry rows are not skipped.
    """
    from salt.client import _iter_failed_missing_returns

    class _FakeReg:
        def get_resources_for_minion(self, mid):
            return {}

    class _FakeCk:
        registry = _FakeReg()

        def _pki_minions(self):
            return {"z-minion"}

    class _FakeCache:
        def contains(self, bank, key):
            return bank == "pillar" and key == "z-minion"

        def fetch(self, bank, key):
            if bank == "pillar" and key == "z-minion":
                return {
                    "resources": {
                        "dummy": {"resource_ids": ["a-res", "b-res"]},
                    },
                }
            return {}

    mopts = dict(master_opts)
    mopts["minion_data_cache"] = True

    with patch("salt.utils.minions.CkMinions", return_value=_FakeCk()):
        with patch("salt.cache.factory", return_value=_FakeCache()):
            keys = [
                next(iter(chunk))
                for chunk in _iter_failed_missing_returns(
                    mopts,
                    set(),
                    {"a-res", "z-minion", "b-res"},
                )
            ]
    assert keys == ["z-minion", "a-res", "b-res"]


def test_get_iter_returns_dedupes_replayed_resource_return(master_opts):
    jid = "20260101000000000002"

    def returns_iter():
        ev = {
            "tag": f"salt/job/{jid}/ret/m1-dummy1",
            "data": {
                "return": True,
                "id": "minion-1",
                "resource_id": "m1-dummy1",
                "jid": jid,
            },
        }
        yield ev
        yield ev

    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.returns_for_job = MagicMock(return_value=True)
        local_client.get_returns_no_block = MagicMock(return_value=returns_iter())
        out = list(
            local_client.get_iter_returns(jid, {"m1-dummy1"}, gather_job_timeout=1)
        )
    assert out == [{"m1-dummy1": {"ret": True, "jid": jid}}]


def test_job_result_return_failure(master_opts):
    """
    We are _not_ getting a job return, because the jid is different. Instead we should
    get a StopIteration exception.
    """
    minions = ()
    jid = "0815"
    raw_return = {
        "id": "fake-id",
        "jid": "0816",
        "data": "",
        "return": "fake-return",
    }
    with client.LocalClient(mopts=master_opts) as local_client:
        local_client.event.get_event = MagicMock()
        local_client.event.get_event.side_effect = [raw_return, None]
        local_client.returners = MagicMock()
        ret = local_client.get_event_iter_returns(jid, minions)
        with pytest.raises(StopIteration):
            next(ret)


def test_cmd_subset_cli(master_opts):
    """
    Test LocalClient.cmd_subset when cli=True
    """
    salt_local_client = client.LocalClient(mopts=master_opts)

    def mock_cmd(tgt, fun, *args, **kwargs):
        if fun == "sys.list_functions":
            return {
                "minion1": ["first.func", "second.func"],
                "minion2": ["first.func", "second.func"],
            }
        return {}

    with patch.object(client.LocalClient, "cmd", side_effect=mock_cmd):
        with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
            salt_local_client.cmd_subset("*", "first.func", subset=1, cli=True)
            # Verify either minion1 or minion2 was targeted
            target_called = cmd_cli_mock.call_args[0][0]
            assert target_called in (["minion1"], ["minion2"])


def test_cmd_subset_skips_failed_minions_68103(salt_master_factory):
    """
    Regression test for #68103.

    When ``LocalClient.cmd`` cannot reach a minion it returns ``False`` for
    that minion's entry in the result dict. ``cmd_subset`` previously did
    ``if fun in minion_ret[minion]`` without checking the value type and
    raised ``TypeError: argument of type 'bool' is not iterable``. The
    failed minion(s) should simply be skipped.
    """
    salt_local_client = salt.client.get_local_client(mopts=salt_master_factory.config)

    # ``cmd_subset`` calls ``random.shuffle`` on the minion list before
    # iterating it. Replace shuffle with a no-op so the iteration order is
    # deterministic and the failed minion is encountered first.
    with patch("salt.client.random.shuffle", lambda x: None), patch(
        "salt.client.LocalClient.cmd",
        return_value={
            # A minion that did not respond to ``sys.list_functions`` shows
            # up in the return as ``False`` (see LocalClient.cmd's failed
            # minion handling).
            "minion1": False,
            "minion2": ["first.func", "second.func"],
        },
    ):
        with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
            # Should not raise TypeError; failed minion must be skipped.
            salt_local_client.cmd_subset("*", "first.func", subset=1, cli=True)
            cmd_cli_mock.assert_called_with(
                ["minion2"],
                "first.func",
                (),
                progress=False,
                kwarg=None,
                tgt_type="list",
                full_return=False,
                ret="",
            )


def test_pub_async_no_timeout(master_opts, salt_master_factory):
    """
    Tests that the client cleanly returns when the publisher is not running

    Note: Requires ZeroMQ's IPC transport which is not supported on windows.
    """
    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    if salt_local_client.opts.get("transport") != "zeromq":
        pytest.skip("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(SaltClientError, lambda: salt_local_client.pub("*", "test.ping"))

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            salt_local_client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                salt_local_client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )


@pytest.mark.skip_unless_on_windows(reason="Windows only test")
@pytest.mark.slow_test
def test_pub_win32(salt_master_factory):
    """
    Tests that the client raises a timeout error when using ZeroMQ's TCP
    transport and publisher is not running.

    Note: Requires ZeroMQ's TCP transport, this is only the default on Windows.
    """
    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    if salt_local_client.opts.get("transport") != "zeromq":
        pytest.skip("This test only works with ZeroMQ")
    # Make sure we cleanly return if the publisher isn't running
    with patch("os.path.exists", return_value=False):
        pytest.raises(
            SaltReqTimeoutError, lambda: salt_local_client.pub("*", "test.ping")
        )

    # Check nodegroups behavior
    with patch("os.path.exists", return_value=True):
        with patch.dict(
            salt_local_client.opts,
            {
                "nodegroups": {
                    "group1": "L@foo.domain.com,bar.domain.com,baz.domain.com or bl*.domain.com"
                }
            },
        ):
            # Do we raise an exception if the nodegroup can't be matched?
            pytest.raises(
                SaltInvocationError,
                salt_local_client.pub,
                "non_existent_group",
                "test.ping",
                tgt_type="nodegroup",
            )


def test_invalid_event_tag_65727(master_opts, caplog):
    """
    LocalClient.get_iter_returns handles non return event tags.
    """
    minions = ()
    jid = "0815"
    raw_return = {"id": "fake-id", "jid": jid, "data": "", "return": "fake-return"}
    expected_return = {"fake-id": {"ret": "fake-return"}}

    def returns_iter():
        # Invalid return
        yield {
            "tag": "salt/job/0815/return/",
            "data": {
                "return": "fpp",
                "id": "fake-id",
            },
        }
        # Valid return
        yield {
            "tag": "salt/job/0815/ret/",
            "data": {
                "return": "fpp",
                "id": "fake-id",
            },
        }

    with client.LocalClient(mopts=master_opts) as local_client:
        # Returning a truthy value, the real method returns a salt returner but it's not used.
        local_client.returns_for_job = MagicMock(return_value=True)
        # Mock iter returns, we'll return one invalid and one valid return event.
        local_client.get_returns_no_block = MagicMock(return_value=returns_iter())
        with caplog.at_level(logging.DEBUG):
            # Validate we don't choke on the bad return, the method returns a
            # valid respons and the invalid event tag is getting logged to
            # debug.
            for ret in local_client.get_iter_returns(jid, {"fake-id"}):
                assert ret == {"fake-id": {"ret": "fpp"}}
            assert "Skipping non return event: salt/job/0815/return/" in caplog.text


def test_publish_timeout_in_default_master_opts():
    """
    publish_timeout must be present in DEFAULT_MASTER_OPTS with a value of 30
    so that any LocalClient not given explicit opts still gets a sane pub timeout.
    """
    assert "publish_timeout" in salt.config.DEFAULT_MASTER_OPTS
    assert salt.config.DEFAULT_MASTER_OPTS["publish_timeout"] == 30


def test_pub_default_timeout(master_opts):
    """
    Test that LocalClient.pub uses a default timeout of 30 seconds.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.ReqChannel.factory"
            ) as mock_channel_factory:
                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)
                mock_channel.send = MagicMock(
                    return_value={"load": {"jid": "test_jid", "minions": ["minion1"]}}
                )
                mock_channel_factory.return_value = mock_channel

                # Mock the event system
                local_client.event.connect_pub = MagicMock(return_value=True)

                # Call pub without specifying timeout
                result = local_client.pub("*", "test.ping")

                # Verify the channel.send was called with timeout=30
                assert mock_channel.send.called
                call_kwargs = mock_channel.send.call_args
                # The timeout is passed to channel.send in the first call
                assert call_kwargs[1]["timeout"] == 30


def test_pub_explicit_timeout(master_opts):
    """
    Test that LocalClient.pub respects explicit timeout values.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.ReqChannel.factory"
            ) as mock_channel_factory:
                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)
                mock_channel.send = MagicMock(
                    return_value={"load": {"jid": "test_jid", "minions": ["minion1"]}}
                )
                mock_channel_factory.return_value = mock_channel

                # Mock the event system
                local_client.event.connect_pub = MagicMock(return_value=True)

                # Call pub with explicit timeout=30
                result = local_client.pub("*", "test.ping", timeout=30)

                # Verify the channel.send was called with timeout=30
                assert mock_channel.send.called
                call_kwargs = mock_channel.send.call_args
                assert call_kwargs[1]["timeout"] == 30


@pytest.mark.asyncio
async def test_pub_async_default_timeout(master_opts):
    """
    Test that LocalClient.pub_async forwards the documented 30s default
    publish_timeout to _prep_pub when no timeout is supplied.
    """
    # tornado.gen.maybe_future and connect_pub create Futures that need an
    # event loop. On Py 3.10+ get_event_loop() does not create one implicitly
    # when called from MainThread, so set one up before any Future is built.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.AsyncReqChannel.factory"
            ) as mock_channel_factory:
                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)

                # Mock the async send to return a coroutine that resolves to the payload
                async def mock_send(*args, **kwargs):
                    return {"load": {"jid": "test_jid", "minions": ["minion1"]}}

                mock_channel.send = MagicMock(side_effect=mock_send)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system - connect_pub should return True (not awaitable)
                local_client.event.connect_pub = MagicMock(return_value=True)

                original_prep_pub = local_client._prep_pub
                prep_pub_calls = []

                def mock_prep_pub(*args, **kwargs):
                    prep_pub_calls.append((args, kwargs))
                    return original_prep_pub(*args, **kwargs)

                with patch.object(local_client, "_prep_pub", side_effect=mock_prep_pub):
                    # Call pub_async without specifying timeout
                    await local_client.pub_async("*", "test.ping")

                    assert len(prep_pub_calls) == 1
                    # _prep_pub signature: (tgt, fun, arg, tgt_type, ret, jid, timeout, ...)
                    assert prep_pub_calls[0][0][6] == 30


@pytest.mark.asyncio
async def test_pub_async_explicit_timeout(master_opts):
    """
    Test that LocalClient.pub_async respects explicit timeout values.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.AsyncReqChannel.factory"
            ) as mock_channel_factory:
                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)

                # Mock the async send to return a coroutine that resolves to the payload
                async def mock_send(*args, **kwargs):
                    return {"load": {"jid": "test_jid", "minions": ["minion1"]}}

                mock_channel.send = MagicMock(side_effect=mock_send)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system - connect_pub should return True (not awaitable)
                local_client.event.connect_pub = MagicMock(return_value=True)

                # Mock _prep_pub to capture the timeout value
                original_prep_pub = local_client._prep_pub
                prep_pub_calls = []

                def mock_prep_pub(*args, **kwargs):
                    prep_pub_calls.append((args, kwargs))
                    return original_prep_pub(*args, **kwargs)

                with patch.object(local_client, "_prep_pub", side_effect=mock_prep_pub):
                    # Call pub_async with explicit timeout=30
                    await local_client.pub_async("*", "test.ping", timeout=30)

                    # Verify _prep_pub was called with timeout=30
                    assert len(prep_pub_calls) == 1
                    # _prep_pub signature: (tgt, fun, arg, tgt_type, ret, jid, timeout, **kwargs)
                    assert (
                        prep_pub_calls[0][0][6] == 30
                    )  # timeout is the 7th positional arg


def _make_channel_mock(return_payload):
    """
    Build a ReqChannel context-manager mock whose .send() returns return_payload.
    """
    mock_channel = MagicMock()
    mock_channel.__enter__ = MagicMock(return_value=mock_channel)
    mock_channel.__exit__ = MagicMock(return_value=False)
    mock_channel.send = MagicMock(return_value=return_payload)
    return mock_channel


def test_pub_uses_publish_timeout_from_config(master_opts):
    """
    pub() must honor a custom publish_timeout set in opts, overriding the 30s default.
    """
    master_opts = dict(master_opts, publish_timeout=30)
    with client.LocalClient(mopts=master_opts) as local_client:
        mock_channel = _make_channel_mock(
            {"load": {"jid": "test_jid", "minions": ["m1"]}}
        )
        with patch("os.path.exists", return_value=True), patch(
            "salt.channel.client.ReqChannel.factory", return_value=mock_channel
        ):
            local_client.event.connect_pub = MagicMock(return_value=True)
            local_client.pub("*", "test.ping")
            assert mock_channel.send.call_args[1]["timeout"] == 30


def test_pub_async_uses_publish_timeout_from_config(master_opts):
    """
    pub_async() must honor a custom publish_timeout set in opts.
    """
    master_opts = dict(master_opts, publish_timeout=30)
    with client.LocalClient(mopts=master_opts) as local_client:
        captured = {}

        @tornado.gen.coroutine
        def mock_send(payload, timeout=None):
            captured["timeout"] = timeout
            raise tornado.gen.Return({"load": {"jid": "test_jid", "minions": ["m1"]}})

        mock_channel = MagicMock()
        mock_channel.__enter__ = MagicMock(return_value=mock_channel)
        mock_channel.__exit__ = MagicMock(return_value=False)
        mock_channel.send = mock_send

        with patch("os.path.exists", return_value=True), patch(
            "salt.channel.client.AsyncReqChannel.factory", return_value=mock_channel
        ):
            local_client.event.connect_pub = MagicMock(return_value=True)
            io_loop = tornado.ioloop.IOLoop()
            io_loop.run_sync(lambda: local_client.pub_async("*", "test.ping"))

        assert captured["timeout"] == 30


# ---------------------------------------------------------------------------
# run_job / run_job_async – timeout propagation to pub / pub_async
# ---------------------------------------------------------------------------


def test_run_job_passes_none_to_pub_when_no_timeout(master_opts):
    """
    run_job() called without an explicit timeout must pass timeout=None to pub()
    so that pub() resolves the value via publish_timeout (30 by default) rather
    than the 5-second salt command timeout.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(
            local_client,
            "pub",
            return_value={"jid": "1234", "minions": ["m1"]},
        ) as mock_pub:
            local_client.run_job("*", "test.ping")
            assert mock_pub.call_args[1]["timeout"] is None


def test_run_job_passes_explicit_timeout_to_pub(master_opts):
    """
    run_job() called with an explicit timeout must forward that value to pub()
    unchanged so caller-controlled timeouts are honored (e.g. CLI -t flag).
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(
            local_client,
            "pub",
            return_value={"jid": "1234", "minions": ["m1"]},
        ) as mock_pub:
            local_client.run_job("*", "test.ping", timeout=30)
            assert mock_pub.call_args[1]["timeout"] == 30


def test_run_job_async_passes_none_to_pub_async_when_no_timeout(master_opts):
    """
    run_job_async() called without an explicit timeout must pass timeout=None
    to pub_async() so that pub_async() uses publish_timeout (30 by default).
    """
    captured = {}

    @tornado.gen.coroutine
    def fake_pub_async(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise tornado.gen.Return({"jid": "1234", "minions": ["m1"]})

    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(local_client, "pub_async", side_effect=fake_pub_async):
            io_loop = tornado.ioloop.IOLoop()
            io_loop.run_sync(lambda: local_client.run_job_async("*", "test.ping"))

    assert captured["timeout"] is None


def test_run_job_async_passes_explicit_timeout_to_pub_async(master_opts):
    """
    run_job_async() called with an explicit timeout must forward that value to
    pub_async() unchanged.
    """
    captured = {}

    @tornado.gen.coroutine
    def fake_pub_async(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise tornado.gen.Return({"jid": "1234", "minions": ["m1"]})

    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(local_client, "pub_async", side_effect=fake_pub_async):
            io_loop = tornado.ioloop.IOLoop()
            io_loop.run_sync(
                lambda: local_client.run_job_async("*", "test.ping", timeout=30)
            )

    assert captured["timeout"] == 30
