import asyncio
import types

from salt.channel.client import AsyncReqChannel
from salt.exceptions import SaltReqTimeoutError
from salt.transport.zeromq import RequestClient


def test_request_client_close_async_drains_queue():
    async def run():
        client = RequestClient.__new__(RequestClient)
        loop = asyncio.get_running_loop()

        client._closing = False
        client._connect_called = False
        client.socket = types.SimpleNamespace(close=lambda: None)
        client.context = types.SimpleNamespace(closed=False, term=lambda: None)
        client._queue = asyncio.Queue()
        client.send_recv_task = asyncio.create_task(asyncio.sleep(3600))
        client.io_loop = types.SimpleNamespace(asyncio_loop=loop)

        future = loop.create_future()
        client._queue.put_nowait((future, b"payload"))

        await client.close_async()

        assert client._closing is True
        assert client.socket is None
        assert client.context is None
        assert client.send_recv_task is None
        assert client._queue.empty()
        assert future.done()
        assert isinstance(future.exception(), SaltReqTimeoutError)

    asyncio.run(run())


def test_async_req_channel_close_schedules_async_close_when_loop_running():
    async def run():
        loop = asyncio.get_running_loop()

        class DummyTransport:
            def __init__(self):
                self.closed = False
                self.io_loop = types.SimpleNamespace(asyncio_loop=loop)

            async def close_async(self):
                self.closed = True

        transport = DummyTransport()
        channel = AsyncReqChannel.__new__(AsyncReqChannel)
        channel._closing = False
        channel.transport = transport

        channel.close()
        await asyncio.sleep(0)

        assert channel._closing is True
        assert transport.closed is True

    asyncio.run(run())


class DummyAdapter:
    def __init__(self):
        self.asyncio_loop = asyncio.new_event_loop()
        self.closed = False

    def run_sync(self, func):
        try:
            self.asyncio_loop.run_until_complete(func())
        finally:
            self.closed = True


class DummyTransportSync:
    def __init__(self):
        self.closed = False
        self.io_loop = DummyAdapter()

    async def close_async(self):
        self.closed = True


def test_async_req_channel_close_runs_when_no_loop():
    transport = DummyTransportSync()
    channel = AsyncReqChannel.__new__(AsyncReqChannel)
    channel._closing = False
    channel.transport = transport

    try:
        channel.close()
        assert channel._closing is True
        assert transport.closed is True
        assert transport.io_loop.closed is True
    finally:
        transport.io_loop.asyncio_loop.close()


def test_request_client_close_schedules_when_loop_running():
    async def run():
        loop = asyncio.get_running_loop()

        invoked = asyncio.Event()

        async def dummy_close_async(self):
            invoked.set()

        client = RequestClient.__new__(RequestClient)
        client._closing = False
        client._connect_called = False
        client.close_async = types.MethodType(dummy_close_async, client)
        client.io_loop = types.SimpleNamespace(asyncio_loop=loop)

        client.close()

        await asyncio.wait_for(invoked.wait(), timeout=1)

    asyncio.run(run())


def test_request_client_close_runs_when_loop_not_running():
    loop = asyncio.new_event_loop()

    invoked = False

    async def dummy_close_async(self):
        nonlocal invoked
        invoked = True

    try:
        client = RequestClient.__new__(RequestClient)
        client._closing = False
        client._connect_called = False
        client.close_async = types.MethodType(dummy_close_async, client)
        client.io_loop = types.SimpleNamespace(asyncio_loop=loop)

        client.close()
        assert invoked is True
    finally:
        loop.close()


def test_async_req_channel_close_without_close_async_uses_transport_close():
    class DummyTransport:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    transport = DummyTransport()
    channel = AsyncReqChannel.__new__(AsyncReqChannel)
    channel._closing = False
    channel.transport = transport

    channel.close()

    assert channel._closing is True
    assert transport.closed is True
