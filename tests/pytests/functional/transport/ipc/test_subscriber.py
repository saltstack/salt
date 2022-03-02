import asyncio
import logging
import pathlib
import sys

import attr
import pytest
import salt.channel.server
import salt.transport.ipc
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    # Windows does not support POSIX IPC
    pytest.mark.skip_on_windows,
    pytest.mark.skipif(
        sys.version_info < (3, 6), reason="The IOLoop blocks under Py3.5 on these tests"
    ),
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
    payload_ack = attr.ib(default=attr.Factory(asyncio.Condition))
    start_tasks = attr.ib(default=attr.Factory(list))

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

    #    def __enter__(self):
    #        self.publisher.start()
    #        self.io_loop.create_task(self.subscriber.connect())
    #        return self
    #
    #    def __exit__(self, *args):
    #        self.subscriber.close()
    #        self.publisher.close()

    async def __aenter__(self):
        await self.publisher.start()
        await asyncio.sleep(0.01)
        await self.subscriber.connect()
        while not self.publisher.streams:
            await asyncio.sleep(0.01)
        return self

    async def __aexit__(self, *args):
        self.subscriber.close()
        self.publisher.close()

    def __await__(self):
        return self.__aenter__().__await__()

    # def __enter__(self):
    #    self.start_tasks.append(self.io_loop.create_task(self.publisher.start()))
    #    self.start_tasks.append(self.io_loop.create_task(self.subscriber.connect()))
    #    return self

    # def __exit__(self, *args):
    #    self.publisher.close()
    #    self.subscriber.close()


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
def channel(event_loop, ipc_socket_path):
    _ipc_tester = IPCTester(io_loop=event_loop, socket_path=str(ipc_socket_path))
    yield _ipc_tester


async def test_basic_send(channel):
    msg = {"foo": "bar", "stop": True}
    log.error("MEH1")
    async with channel as ch:
        # await asyncio.gather(ch.start_tasks)
        log.error("MEH2")
        assert ch.subscriber.connected()
        await ch.publish(msg)
        ret = await ch.read()
        assert ret == msg
