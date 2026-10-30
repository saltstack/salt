"""WebSocket subscribers await connection, callbacks and resource cleanup."""

import asyncio

import aiohttp.web
import pytest

import salt.payload
import salt.transport.frame
import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def websocket_publisher(io_loop):
    sockets = asyncio.Queue()
    received = asyncio.Queue()
    active = set()

    async def handle(request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        active.add(ws)
        sockets.put_nowait(ws)
        try:
            async for message in ws:
                if message.type == aiohttp.WSMsgType.BINARY:
                    received.put_nowait(message.data)
        finally:
            active.discard(ws)
        return ws

    app = aiohttp.web.Application()
    app.router.add_get("/ws", handle)
    runner = aiohttp.web.AppRunner(app)

    async def start():
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        return runner.addresses[0]

    loop = salt.utils.asynchronous.aioloop(io_loop)
    host, port = loop.run_until_complete(start())
    yield host, port, sockets, received
    loop.run_until_complete(runner.cleanup())


@pytest.fixture
def client(websocket_publisher, io_loop):
    host, port, _, _ = websocket_publisher
    instance = salt.transport.ws.PublishClient(
        {"tcp_reconnect_backoff": 0.01}, io_loop, host=host, port=port
    )
    yield instance
    salt.utils.asynchronous.aioloop(io_loop).run_until_complete(instance.close_async())


async def test_concurrent_connects_share_a_connection(client, websocket_publisher):
    await asyncio.gather(*(client.connect() for _ in range(10)))
    assert websocket_publisher[2].qsize() == 1
    assert client.connected


async def test_connection_callback_can_send_on_same_client(client, websocket_publisher):
    frame = salt.transport.frame.frame_msg({"id": "minion"})

    async def connected(result):
        assert result is True
        await client.send(frame)

    await asyncio.wait_for(client.connect(connect_callback=connected), 2)
    assert await websocket_publisher[3].get() == frame


async def test_sync_connection_callback(client):
    callback = MagicMock()
    await client.connect(connect_callback=callback)
    callback.assert_called_once_with(True)


async def test_receive_after_timeout_keeps_connection(client, websocket_publisher):
    await client.connect()
    ws = await websocket_publisher[2].get()
    assert await client.recv(timeout=0.01) is None
    await ws.send_bytes(salt.payload.dumps({b"id": b"minion"}))
    assert await client.recv(timeout=1) == {b"id": b"minion"}
    assert websocket_publisher[2].empty()


async def test_receive_reconnects_after_peer_close(client, websocket_publisher):
    disconnected = AsyncMock()
    await client.connect(disconnect_callback=disconnected)
    first = await websocket_publisher[2].get()
    read = asyncio.create_task(client.recv())
    await first.close()
    second = await asyncio.wait_for(websocket_publisher[2].get(), 2)
    await second.send_bytes(salt.payload.dumps({b"sequence": 2}))
    assert await asyncio.wait_for(read, 2) == {b"sequence": 2}
    disconnected.assert_awaited_once()


async def test_close_drains_direct_receive(client):
    await client.connect()
    session = client._session
    read = asyncio.create_task(client.recv())
    await asyncio.sleep(0)
    await client.close_async()
    with pytest.raises(asyncio.CancelledError):
        await read
    assert session.closed
    assert client._closed
    assert not client.connected
    assert not client._io_tasks


async def test_close_does_not_wait_for_receivers_context_exit(client):
    """Closing I/O must finish while its caller exits the same client context."""
    waiting = asyncio.Event()
    exited = asyncio.Event()

    async def receive():
        try:
            async with client:
                await client.connect()
                waiting.set()
                await client.recv()
        finally:
            exited.set()

    read = asyncio.create_task(receive())
    closing = None
    try:
        await asyncio.wait_for(waiting.wait(), 2)
        # Let recv() reach its first wait before shutdown takes its task snapshot.
        await asyncio.sleep(0)
        closing = asyncio.create_task(client.close_async())
        await asyncio.wait_for(asyncio.shield(closing), 1)
        with pytest.raises(asyncio.CancelledError):
            await read
        assert exited.is_set()
        assert client._closed
    finally:
        await salt.utils.asynchronous.cancel_tasks(read, closing)


async def test_close_drains_replaced_receive_callbacks(client):
    await client.connect()
    first = AsyncMock()
    client.on_recv(first)
    old = client.on_recv_task
    await asyncio.sleep(0)
    client.on_recv(AsyncMock())
    current = client.on_recv_task
    await asyncio.sleep(0)
    await client.close_async()
    assert old.done()
    assert current.done()
    assert not client._recv_tasks


async def test_close_drains_pending_connect(client):
    started = asyncio.Event()
    sessions = []

    async def connect(session, *args, **kwargs):
        sessions.append(session)
        started.set()
        await asyncio.Event().wait()

    with patch.object(aiohttp.ClientSession, "ws_connect", connect):
        task = asyncio.create_task(client.connect())
        await started.wait()
        await client.close_async()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert sessions[0].closed
    assert client._closed


async def test_receive_callback_and_context_cleanup(client, websocket_publisher):
    delivered = asyncio.Event()
    messages = []

    async def receive(message):
        messages.append(message)
        delivered.set()

    async with client:
        await client.connect()
        session = client._session
        client.on_recv(receive)
        ws = await websocket_publisher[2].get()
        await ws.send_bytes(salt.payload.dumps({b"result": True}))
        await asyncio.wait_for(delivered.wait(), 2)
    assert messages == [{b"result": True}]
    assert session.closed
    assert client.on_recv_task is None
    assert not asyncio.get_running_loop().is_closed()


async def test_sync_close_can_be_awaited(client):
    await client.connect()
    session = client._session
    client.close()
    await client.close_async()
    assert client.close_task.done()
    assert session.closed


async def test_legacy_wrapper_drives_async_subscriber_cleanup(websocket_publisher):
    host, port, _, received = websocket_publisher
    frame = salt.transport.frame.frame_msg({"id": "minion"})

    def send():
        with salt.utils.asynchronous.SyncWrapper(
            salt.transport.ws.PublishClient,
            args=({},),
            kwargs={"host": host, "port": port},
            loop_kwarg="io_loop",
        ) as wrapped:
            wrapped.connect()
            session = wrapped.obj._session
            wrapped.send(frame)
        assert session.closed

    await asyncio.wait_for(asyncio.to_thread(send), 3)
    assert await received.get() == frame
