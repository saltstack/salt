import pathlib

import attr
import pytest

import salt.channel.server
import salt.ext.tornado.gen
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
    publisher = attr.ib()
    subscriber = attr.ib()
    payloads = attr.ib(default=attr.Factory(list))
    payload_ack = attr.ib(default=attr.Factory(locks.Condition))

    @subscriber.default
    def _subscriber_default(self):
        return salt.transport.ipc.IPCMessageSubscriber(
            self.socket_path,
            io_loop=self.io_loop,
        )

    @publisher.default
    def _publisher_default(self):
        return salt.transport.ipc.IPCMessagePublisher(
            {"ipc_write_buffer": 0},
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

    async def publish(self, payload, timeout=60):
        self.publisher.publish(payload)

    async def read(self, timeout=60):
        ret = await self.subscriber.read(timeout)
        return ret

    def __enter__(self):
        self.publisher.start()
        self.io_loop.add_callback(self.subscriber.connect)
        return self

    def __exit__(self, *args):
        self.subscriber.close()
        self.publisher.close()


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
    # XXX: IPCClient connect and connected methods need to be cleaned up as
    # this should not be needed.
    while not channel.subscriber._connecting_future.done():
        await salt.ext.tornado.gen.sleep(0.01)
    while not channel.subscriber.connected():
        await salt.ext.tornado.gen.sleep(0.01)
    assert channel.subscriber.connected()
    await channel.publish(msg)
    ret = await channel.read()
    assert ret == msg
