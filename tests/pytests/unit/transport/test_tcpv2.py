import asyncio
import inspect

from salt.transport.tcpv2 import RequestClient
from salt.utils.asynchronous import AsyncLoopAdapter


def test_request_client_methods_are_async():
    assert inspect.iscoroutinefunction(RequestClient.connect)
    assert inspect.iscoroutinefunction(RequestClient.send)


class DummyWriter:
    def __init__(self):
        self._closing = False
        self.closed = False
        self.data = []

    def is_closing(self):
        return self._closing

    def write(self, data):
        self.data.append(data)

    async def drain(self):
        return None

    def close(self):
        self._closing = True

    async def wait_closed(self):
        self.closed = True


class DummyReader(asyncio.StreamReader):
    pass


def test_request_client_connect_establishes_connection(monkeypatch):
    async def run():
        loop = asyncio.get_running_loop()
        reader = DummyReader()
        writer = DummyWriter()
        called = []

        async def fake_open_connection(host, port):
            called.append((host, port))
            return reader, writer

        monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

        async def connect_callback(success):
            called.append(success)

        opts = {"master_uri": "tcp://127.0.0.1:4506"}
        client = RequestClient(opts, io_loop=loop, connect_callback=connect_callback)

        await client.connect()

        assert client.writer is writer
        assert client.reader is reader
        assert called == [("127.0.0.1", 4506), True]

    asyncio.run(run())


def test_request_client_close_in_running_loop():
    async def run():
        loop = asyncio.get_running_loop()
        client = RequestClient({"master_uri": "tcp://127.0.0.1:4506"}, io_loop=loop)
        writer = DummyWriter()
        client.writer = writer

        client.close()
        await asyncio.sleep(0)

        assert writer._closing is True
        assert client.writer is None

    asyncio.run(run())


def test_request_client_close_runs_without_running_loop():
    loop = asyncio.new_event_loop()
    try:
        client = RequestClient({"master_uri": "tcp://127.0.0.1:4506"}, io_loop=loop)
        writer = DummyWriter()
        client.writer = writer

        client.close()
        assert writer._closing is True
        assert client.writer is None
    finally:
        loop.close()


def test_request_client_connect_callback_sync(monkeypatch):
    loop = asyncio.new_event_loop()
    adapter = AsyncLoopAdapter(loop)
    called = []

    def sync_callback(_):
        called.append(True)

    async def fake_open_connection(host, port):
        reader = DummyReader()
        writer = DummyWriter()
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    try:
        old_loop = None
        try:
            old_loop = asyncio.get_event_loop()
        except RuntimeError:
            pass
        asyncio.set_event_loop(loop)

        client = RequestClient(
            {"master_uri": "tcp://127.0.0.1:4506"},
            io_loop=adapter.asyncio_loop,
            connect_callback=sync_callback,
        )
        client.loop_adapter = adapter

        adapter.run_sync(client.connect)
        assert called == [True]
    finally:
        asyncio.set_event_loop(old_loop)
        loop.close()
