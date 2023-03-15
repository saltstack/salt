import pathlib

import attr
import pytest

import salt.transport.ipc
import salt.utils.platform
from salt.ext.tornado import locks

pytestmark = [
    # Windows does not support POSIX IPC
    pytest.mark.skip_on_windows,
]


@attr.s(frozen=True, slots=True)
class PayloadHandler:
    payloads = attr.ib(init=False, default=attr.Factory(list))

    async def handle_payload(self, payload, reply_func):
        self.payloads.append(payload)
        await reply_func(payload)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.payloads.clear()


@attr.s(frozen=True, slots=True)
class IPCTester:
    io_loop = attr.ib()
    socket_path = attr.ib()
    server = attr.ib()
    client = attr.ib()
    payloads = attr.ib(default=attr.Factory(list))
    payload_ack = attr.ib(default=attr.Factory(locks.Condition))

    @server.default
    def _server_default(self):
        return salt.transport.ipc.IPCMessageServer(
            self.socket_path,
            io_loop=self.io_loop,
            payload_handler=self.handle_payload,
        )

    @client.default
    def _client_default(self):
        return salt.transport.ipc.IPCMessageClient(
            self.socket_path,
            io_loop=self.io_loop,
        )

    async def handle_payload(self, payload, reply_func):
        self.payloads.append(payload)
        await reply_func(payload)
        self.payload_ack.notify()

    def new_client(self):
        return IPCTester(
            io_loop=self.io_loop,
            socket_path=self.socket_path,
            server=self.server,
            payloads=self.payloads,
            payload_ack=self.payload_ack,
        )

    async def send(self, payload, timeout=60):
        ret = await self.client.send(payload)
        await self.payload_ack.wait(self.io_loop.time() + timeout)
        return ret

    def __enter__(self):
        self.io_loop.add_callback(self.server.start)
        self.io_loop.add_callback(self.client.connect)
        return self

    def __exit__(self, *args):
        self.client.close()
        self.server.close()


@pytest.fixture
def ipc_socket_path(tmp_path):
    if salt.utils.platform.is_darwin():
        # A shorter path so that we don't hit the AF_UNIX path too long
        tmp_path = pathlib.Path("/tmp").resolve()
    _socket_path = tmp_path / "ipc-test.ipc"
    try:
        yield _socket_path
    finally:
        if _socket_path.exists():
            _socket_path.unlink()


@pytest.fixture
def channel(io_loop, ipc_socket_path):
    _ipc_tester = IPCTester(io_loop=io_loop, socket_path=str(ipc_socket_path))
    with _ipc_tester:
        yield _ipc_tester


async def test_basic_send(channel):
    msg = {"foo": "bar", "stop": True}
    await channel.send(msg)
    assert channel.payloads[0] == msg


async def test_send_many(channel):
    msgs = []
    for i in range(0, 1000):
        msgs.append("test_many_send_{}".format(i))

    for msg in msgs:
        await channel.send(msg)
    assert channel.payloads == msgs


async def test_very_big_message(channel):
    long_str = "".join([str(num) for num in range(10**5)])
    msg = {"long_str": long_str, "stop": True}
    await channel.send(msg)
    assert channel.payloads[0] == msg


async def test_multistream_sends(channel):
    new_channel = channel.new_client()
    with new_channel:
        assert channel.client is not new_channel.client
        await new_channel.send("foo")
        await channel.send("foo")
    assert channel.payloads == ["foo", "foo"]


async def test_multistream_error_sends(channel):
    new_channel = channel.new_client()
    with new_channel:
        assert channel.client is not new_channel.client
        await new_channel.send(None)
        await channel.send(None)
        await new_channel.send("foo")
        await channel.send("foo")
    assert channel.payloads == [None, None, "foo", "foo"]
