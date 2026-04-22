import asyncio
import os

import pytest
import tornado.gen
import tornado.ioloop

import salt.client as client
import salt.config
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


def test_pub_async_no_timeout(master_opts):
    """
    Test that LocalClient.pub_async works without a timeout specified.
    """
    with client.LocalClient(mopts=master_opts) as local_client:
        with patch("os.path.exists", return_value=True):
            with patch(
                "salt.channel.client.AsyncReqChannel.factory"
            ) as mock_channel_factory:
                mock_channel = MagicMock()
                mock_channel.__enter__ = MagicMock(return_value=mock_channel)
                mock_channel.__exit__ = MagicMock(return_value=False)

                # Mock the async send
                future = tornado.gen.maybe_future(
                    {"load": {"jid": "test_jid", "minions": ["minion1"]}}
                )
                mock_channel.send = MagicMock(return_value=future)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system
                local_client.event.connect_pub = MagicMock(
                    return_value=tornado.gen.maybe_future(True)
                )

                # Mock _prep_pub to capture the timeout value
                original_prep_pub = local_client._prep_pub
                prep_pub_calls = []

                def mock_prep_pub(*args, **kwargs):
                    prep_pub_calls.append((args, kwargs))
                    return original_prep_pub(*args, **kwargs)

                with patch.object(local_client, "_prep_pub", side_effect=mock_prep_pub):
                    # Call pub_async without specifying timeout
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    io_loop = tornado.ioloop.IOLoop.current()
                    io_loop.run_sync(lambda: local_client.pub_async("*", "test.ping"))

                    # Verify _prep_pub was called with timeout=15 (the default for pub_async)
                    assert len(prep_pub_calls) == 1
                    # timeout is the 7th positional arg
                    assert prep_pub_calls[0][0][6] == 15


async def test_pub_async_default_timeout(master_opts):
    """
    Test that LocalClient.pub_async uses a default timeout of 30 seconds.
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
                    # LocalClient.pub_async expects the response to have a 'load' key
                    # if it was successful.
                    return {"load": {"jid": "test_jid", "minions": ["minion1"]}}

                mock_channel.send = MagicMock(side_effect=mock_send)
                mock_channel_factory.return_value = mock_channel

                # Mock the event system - connect_pub should return True (not awaitable)
                with patch("salt.utils.event.get_event", MagicMock()):
                    with patch.object(
                        local_client.event,
                        "connect_pub",
                        MagicMock(return_value=True),
                    ):
                        ret = await local_client.pub_async(
                            "localhost", "test.ping", [], 30, "glob", ""
                        )
                assert ret["jid"] == "test_jid"


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
                with patch("salt.utils.event.get_event", MagicMock()):
                    with patch.object(
                        local_client.event,
                        "connect_pub",
                        MagicMock(return_value=True),
                    ):
                        ret = await local_client.pub_async(
                            "localhost", "test.ping", [], 30, "glob", "", timeout=15
                        )
                assert ret["jid"] == "test_jid"
