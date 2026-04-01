"""
    :codeauthor: Mike Place <mp@saltstack.com>
"""

import copy
import logging

import pytest

import salt.client
import salt.config
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.utils.platform
from salt import client
from salt.exceptions import (
    EauthAuthenticationError,
    SaltClientError,
    SaltInvocationError,
    SaltReqTimeoutError,
)
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


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


def test_create_local_client(master_opts):
    with client.LocalClient(mopts=master_opts) as local_client:
        assert isinstance(
            local_client, client.LocalClient
        ), "LocalClient did not create a LocalClient instance"


def test_check_pub_data(salt_master_factory):
    just_minions = {"minions": ["m1", "m2"]}
    jid_no_minions = {"jid": "1234", "minions": []}
    valid_pub_data = {"minions": ["m1", "m2"], "jid": "1234"}

    config = copy.deepcopy(salt_master_factory.config)
    salt_local_client = salt.client.get_local_client(mopts=config)

    pytest.raises(EauthAuthenticationError, salt_local_client._check_pub_data, "")
    assert {} == salt_local_client._check_pub_data(
        just_minions
    ), "Did not handle lack of jid correctly"

    assert {} == salt_local_client._check_pub_data(
        {"jid": "0"}
    ), "Passing JID of zero is not handled gracefully"

    with patch.dict(salt_local_client.opts, {}):
        salt_local_client._check_pub_data(jid_no_minions)

    assert valid_pub_data == salt_local_client._check_pub_data(valid_pub_data)


def test_cmd_subset(salt_master_factory):
    salt_local_client = salt.client.get_local_client(mopts=salt_master_factory.config)

    with patch(
        "salt.client.LocalClient.cmd",
        return_value={
            "minion1": ["first.func", "second.func"],
            "minion2": ["first.func", "second.func"],
        },
    ):
        with patch("salt.client.LocalClient.cmd_cli") as cmd_cli_mock:
            salt_local_client.cmd_subset("*", "first.func", subset=1, cli=True)
            try:
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
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )
            salt_local_client.cmd_subset("*", "first.func", subset=10, cli=True)
            try:
                cmd_cli_mock.assert_called_with(
                    ["minion2", "minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1", "minion2"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=False,
                    ret="",
                )

            ret = salt_local_client.cmd_subset(
                "*", "first.func", subset=1, cli=True, full_return=True
            )
            try:
                cmd_cli_mock.assert_called_with(
                    ["minion2"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=True,
                    ret="",
                )
            except AssertionError:
                cmd_cli_mock.assert_called_with(
                    ["minion1"],
                    "first.func",
                    (),
                    progress=False,
                    kwarg=None,
                    tgt_type="list",
                    full_return=True,
                    ret="",
                )


@pytest.mark.skip_on_windows(reason="Not supported on Windows")
def test_pub(salt_master_factory):
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
    publish_timeout must be present in DEFAULT_MASTER_OPTS with a value of 15
    so that any LocalClient not given explicit opts still gets a sane pub timeout.
    """
    assert "publish_timeout" in salt.config.DEFAULT_MASTER_OPTS
    assert salt.config.DEFAULT_MASTER_OPTS["publish_timeout"] == 15


def test_pub_default_timeout(master_opts):
    """
    Test that LocalClient.pub uses a default timeout of 15 seconds.
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

                # Verify the channel.send was called with timeout=15
                assert mock_channel.send.called
                call_kwargs = mock_channel.send.call_args
                # The timeout is passed to channel.send in the first call
                assert call_kwargs[1]["timeout"] == 15


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


def test_pub_async_default_timeout(master_opts):
    """
    Test that LocalClient.pub_async uses a default timeout of 15 seconds.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.AsyncReqChannel.factory"
            ) as mock_channel_factory:
                import salt.ext.tornado.gen

                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)

                # Mock the async send to return a completed Future
                future = salt.ext.tornado.gen.maybe_future(
                    {"load": {"jid": "test_jid", "minions": ["minion1"]}}
                )
                mock_channel.send = MagicMock(return_value=future)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system
                local_client.event.connect_pub = MagicMock(
                    return_value=salt.ext.tornado.gen.maybe_future(True)
                )

                # Mock _prep_pub to capture the timeout value
                original_prep_pub = local_client._prep_pub
                prep_pub_calls = []

                def mock_prep_pub(*args, **kwargs):
                    prep_pub_calls.append((args, kwargs))
                    return original_prep_pub(*args, **kwargs)

                with patch.object(local_client, "_prep_pub", side_effect=mock_prep_pub):
                    # Call pub_async without specifying timeout
                    local_client.pub_async("*", "test.ping")

                    # Verify _prep_pub was called with timeout=15
                    assert len(prep_pub_calls) == 1
                    # _prep_pub signature: (tgt, fun, arg, tgt_type, ret, jid, timeout, **kwargs)
                    assert (
                        prep_pub_calls[0][0][6] == 15
                    )  # timeout is the 7th positional arg


def test_pub_async_explicit_timeout(master_opts):
    """
    Test that LocalClient.pub_async respects explicit timeout values.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.AsyncReqChannel.factory"
            ) as mock_channel_factory:
                import salt.ext.tornado.gen

                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)

                # Mock the async send to return a completed Future
                future = salt.ext.tornado.gen.maybe_future(
                    {"load": {"jid": "test_jid", "minions": ["minion1"]}}
                )
                mock_channel.send = MagicMock(return_value=future)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system
                local_client.event.connect_pub = MagicMock(
                    return_value=salt.ext.tornado.gen.maybe_future(True)
                )

                # Mock _prep_pub to capture the timeout value
                original_prep_pub = local_client._prep_pub
                prep_pub_calls = []

                def mock_prep_pub(*args, **kwargs):
                    prep_pub_calls.append((args, kwargs))
                    return original_prep_pub(*args, **kwargs)

                with patch.object(local_client, "_prep_pub", side_effect=mock_prep_pub):
                    # Call pub_async with explicit timeout=30
                    local_client.pub_async("*", "test.ping", timeout=30)

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
    pub() must honour a custom publish_timeout set in opts, overriding the 15s default.
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
    pub_async() must honour a custom publish_timeout set in opts.
    """
    master_opts = dict(master_opts, publish_timeout=30)
    with client.LocalClient(mopts=master_opts) as local_client:
        captured = {}

        @salt.ext.tornado.gen.coroutine
        def mock_send(payload, timeout=None):
            captured["timeout"] = timeout
            raise salt.ext.tornado.gen.Return(
                {"load": {"jid": "test_jid", "minions": ["m1"]}}
            )

        mock_channel = MagicMock()
        mock_channel.__enter__ = MagicMock(return_value=mock_channel)
        mock_channel.__exit__ = MagicMock(return_value=False)
        mock_channel.send = mock_send

        with patch("os.path.exists", return_value=True), patch(
            "salt.channel.client.AsyncReqChannel.factory", return_value=mock_channel
        ):
            local_client.event.connect_pub = MagicMock(return_value=True)
            io_loop = salt.ext.tornado.ioloop.IOLoop()
            io_loop.run_sync(lambda: local_client.pub_async("*", "test.ping"))

        assert captured["timeout"] == 30


# ---------------------------------------------------------------------------
# run_job / run_job_async – timeout propagation to pub / pub_async
# ---------------------------------------------------------------------------


def test_run_job_passes_none_to_pub_when_no_timeout(master_opts):
    """
    run_job() called without an explicit timeout must pass timeout=None to pub()
    so that pub() resolves the value via publish_timeout (15 by default) rather
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
    unchanged so caller-controlled timeouts are honoured (e.g. CLI -t flag).
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
    to pub_async() so that pub_async() uses publish_timeout (15 by default).
    """
    captured = {}

    @salt.ext.tornado.gen.coroutine
    def fake_pub_async(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise salt.ext.tornado.gen.Return({"jid": "1234", "minions": ["m1"]})

    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(local_client, "pub_async", side_effect=fake_pub_async):
            io_loop = salt.ext.tornado.ioloop.IOLoop()
            io_loop.run_sync(lambda: local_client.run_job_async("*", "test.ping"))

    assert captured["timeout"] is None


def test_run_job_async_passes_explicit_timeout_to_pub_async(master_opts):
    """
    run_job_async() called with an explicit timeout must forward that value to
    pub_async() unchanged.
    """
    captured = {}

    @salt.ext.tornado.gen.coroutine
    def fake_pub_async(*args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise salt.ext.tornado.gen.Return({"jid": "1234", "minions": ["m1"]})

    with client.LocalClient(mopts=master_opts) as local_client:
        with patch.object(local_client, "pub_async", side_effect=fake_pub_async):
            io_loop = salt.ext.tornado.ioloop.IOLoop()
            io_loop.run_sync(
                lambda: local_client.run_job_async("*", "test.ping", timeout=30)
            )

    assert captured["timeout"] == 30
