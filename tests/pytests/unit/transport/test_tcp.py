import socket

import attr
import pytest
import salt.exceptions
import salt.transport.tcp
from salt.ext.tornado import concurrent, gen, ioloop
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.mock import MagicMock, patch


@pytest.fixture
def message_client_pool():
    sock_pool_size = 5
    opts = {"sock_pool_size": sock_pool_size}
    message_client_args = (
        {},  # opts,
        "",  # host
        0,  # port
    )
    with patch(
        "salt.transport.tcp.SaltMessageClient.__init__", MagicMock(return_value=None),
    ):
        message_client_pool = salt.transport.tcp.SaltMessageClientPool(
            opts, args=message_client_args
        )
    original_message_clients = message_client_pool.message_clients[:]
    message_client_pool.message_clients = [MagicMock() for _ in range(sock_pool_size)]
    try:
        yield message_client_pool
    finally:
        with patch(
            "salt.transport.tcp.SaltMessageClient.close", MagicMock(return_value=None)
        ):
            del original_message_clients


class TestSaltMessageClientPool:
    def test_send(self, message_client_pool):
        for message_client_mock in message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock.send.return_value = []
        assert message_client_pool.send() == []
        message_client_pool.message_clients[2].send_queue = [0]
        message_client_pool.message_clients[2].send.return_value = [1]
        assert message_client_pool.send() == [1]

    def test_write_to_stream(self, message_client_pool):
        for message_client_mock in message_client_pool.message_clients:
            message_client_mock.send_queue = [0, 0, 0]
            message_client_mock._stream.write.return_value = []
        assert message_client_pool.write_to_stream("") == []
        message_client_pool.message_clients[2].send_queue = [0]
        message_client_pool.message_clients[2]._stream.write.return_value = [1]
        assert message_client_pool.write_to_stream("") == [1]

    def test_close(self, message_client_pool):
        message_client_pool.close()
        assert message_client_pool.message_clients == []

    def test_on_recv(self, message_client_pool):
        for message_client_mock in message_client_pool.message_clients:
            message_client_mock.on_recv.return_value = None
        message_client_pool.on_recv()
        for message_client_mock in message_client_pool.message_clients:
            assert message_client_mock.on_recv.called

    async def test_connect_all(self, message_client_pool):

        for message_client_mock in message_client_pool.message_clients:
            future = concurrent.Future()
            future.set_result("foo")
            message_client_mock.connect.return_value = future

        connected = await message_client_pool.connect()
        assert connected is None

    async def test_connect_partial(self, io_loop, message_client_pool):
        for idx, message_client_mock in enumerate(message_client_pool.message_clients):
            future = concurrent.Future()
            if idx % 2 == 0:
                future.set_result("foo")
            message_client_mock.connect.return_value = future

        with pytest.raises(gen.TimeoutError):
            future = message_client_pool.connect()
            await gen.with_timeout(io_loop.time() + 0.1, future)


@attr.s(frozen=True, slots=True)
class ClientSocket:
    listen_on = attr.ib(init=False, default="127.0.0.1")
    port = attr.ib(init=False, default=attr.Factory(get_unused_localhost_port))
    sock = attr.ib(init=False, repr=False)

    @sock.default
    def _sock_default(self):
        return socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def __enter__(self):
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.listen_on, self.port))
        self.sock.listen(1)
        return self

    def __exit__(self, *args):
        self.sock.close()


@pytest.fixture
def client_socket():
    with ClientSocket() as _client_socket:
        yield _client_socket


def test_message_client_cleanup_on_close(client_socket, temp_salt_master):
    """
    test message client cleanup on close
    """
    orig_loop = ioloop.IOLoop()
    orig_loop.make_current()

    opts = temp_salt_master.config.copy()
    client = salt.transport.tcp.SaltMessageClient(
        opts, client_socket.listen_on, client_socket.port
    )

    # Mock the io_loop's stop method so we know when it has been called.
    orig_loop.real_stop = orig_loop.stop
    orig_loop.stop_called = False

    def stop(*args, **kwargs):
        orig_loop.stop_called = True
        orig_loop.real_stop()

    orig_loop.stop = stop
    try:
        assert client.io_loop == orig_loop
        client.io_loop.run_sync(client.connect)

        # Ensure we are testing the _read_until_future and io_loop teardown
        assert client._stream is not None
        assert client._read_until_future is not None
        assert orig_loop.stop_called is True

        # The run_sync call will set stop_called, reset it
        orig_loop.stop_called = False
        client.close()

        # Stop should be called again, client's io_loop should be None
        assert orig_loop.stop_called is True
        assert client.io_loop is None
    finally:
        orig_loop.stop = orig_loop.real_stop
        del orig_loop.real_stop
        del orig_loop.stop_called
        orig_loop.clear_current()
        orig_loop.close(all_fds=True)


async def test_async_tcp_pub_channel_connect_publish_port(
    temp_salt_master, client_socket
):
    """
    test when publish_port is not 4506
    """
    opts = dict(
        temp_salt_master.config.copy(),
        master_uri="",
        master_ip="127.0.0.1",
        publish_port=1234,
    )
    channel = salt.transport.tcp.AsyncTCPPubChannel(opts)
    patch_auth = MagicMock(return_value=True)
    patch_client_pool = MagicMock(spec=salt.transport.tcp.SaltMessageClientPool)
    with patch("salt.crypt.AsyncAuth.gen_token", patch_auth), patch(
        "salt.crypt.AsyncAuth.authenticated", patch_auth
    ), patch("salt.transport.tcp.SaltMessageClientPool", patch_client_pool):
        with channel:
            # We won't be able to succeed the connection because we're not mocking the tornado coroutine
            with pytest.raises(salt.exceptions.SaltClientError):
                await channel.connect()
    # The first call to the mock is the instance's __init__, and the first argument to those calls is the opts dict
    assert patch_client_pool.call_args[0][0]["publish_port"] == opts["publish_port"]


def test_tcp_pub_server_channel_publish_filtering(temp_salt_master):
    opts = dict(temp_salt_master.config.copy(), sign_pub_messages=False)
    with patch("salt.master.SMaster.secrets") as secrets, patch(
        "salt.crypt.Crypticle"
    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper:
        channel = salt.transport.tcp.TCPPubServerChannel(opts)
        wrap = MagicMock()
        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt
        SyncWrapper.return_value = wrap

        # try simple publish with glob tgt_type
        channel.publish({"test": "value", "tgt_type": "glob", "tgt": "*"})
        payload = wrap.send.call_args[0][0]

        # verify we send it without any specific topic
        assert "topic_lst" not in payload

        # try simple publish with list tgt_type
        channel.publish({"test": "value", "tgt_type": "list", "tgt": ["minion01"]})
        payload = wrap.send.call_args[0][0]

        # verify we send it with correct topic
        assert "topic_lst" in payload
        assert payload["topic_lst"] == ["minion01"]

        # try with syndic settings
        opts["order_masters"] = True
        channel.publish({"test": "value", "tgt_type": "list", "tgt": ["minion01"]})
        payload = wrap.send.call_args[0][0]

        # verify we send it without topic for syndics
        assert "topic_lst" not in payload


def test_tcp_pub_server_channel_publish_filtering_str_list(temp_salt_master):
    opts = dict(temp_salt_master.config.copy(), sign_pub_messages=False)
    with patch("salt.master.SMaster.secrets") as secrets, patch(
        "salt.crypt.Crypticle"
    ) as crypticle, patch("salt.utils.asynchronous.SyncWrapper") as SyncWrapper, patch(
        "salt.utils.minions.CkMinions.check_minions"
    ) as check_minions:
        channel = salt.transport.tcp.TCPPubServerChannel(opts)
        wrap = MagicMock()
        crypt = MagicMock()
        crypt.dumps.return_value = {"test": "value"}

        secrets.return_value = {"aes": {"secret": None}}
        crypticle.return_value = crypt
        SyncWrapper.return_value = wrap
        check_minions.return_value = {"minions": ["minion02"]}

        # try simple publish with list tgt_type
        channel.publish({"test": "value", "tgt_type": "list", "tgt": "minion02"})
        payload = wrap.send.call_args[0][0]

        # verify we send it with correct topic
        assert "topic_lst" in payload
        assert payload["topic_lst"] == ["minion02"]

        # verify it was correctly calling check_minions
        check_minions.assert_called_with("minion02", tgt_type="list")
