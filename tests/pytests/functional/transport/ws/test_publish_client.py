"""WebSocket subscribers await connection, callbacks and resource cleanup."""

import asyncio
import tempfile

import aiohttp.web
import pytest

import salt.payload
import salt.transport.frame
import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def websocket_publisher(io_loop, request):
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
    mode = getattr(request, "param", "tcp")
    client_options = {}
    ssl_context = None
    if mode == "tls":
        ssl_context = salt.transport.base.ssl_context(
            request.getfixturevalue("ssl_master_config"), server_side=True
        )
        client_options["ssl"] = request.getfixturevalue("ssl_minion_config")
    if mode == "unix":
        directory = tempfile.TemporaryDirectory(prefix="salt-ws-sub-", dir="/tmp")
        request.addfinalizer(directory.cleanup)
        client_options["path"] = f"{directory.name}/pub"

    async def start():
        await runner.setup()
        if mode == "unix":
            site = aiohttp.web.UnixSite(runner, client_options["path"])
        else:
            site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0, ssl_context=ssl_context)
        await site.start()
        if mode == "unix":
            return None, None
        return runner.addresses[0]

    loop = salt.utils.asynchronous.aioloop(io_loop)
    host, port = loop.run_until_complete(start())
    if host is not None:
        client_options.update(host=host, port=port)
    yield host, port, sockets, received, client_options
    loop.run_until_complete(runner.cleanup())


@pytest.fixture
def client(websocket_publisher, io_loop):
    instance = salt.transport.ws.PublishClient(
        {"tcp_reconnect_backoff": 0.01}, io_loop, **websocket_publisher[4]
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


async def test_empty_ssl_options_preserve_plaintext_connection(
    client, websocket_publisher
):
    client.ssl = {}
    await client.connect(timeout=1)
    ws = await websocket_publisher[2].get()
    await ws.send_bytes(salt.payload.dumps({b"plaintext": True}))
    assert await client.recv(timeout=1) == {b"plaintext": True}


@pytest.mark.parametrize("websocket_publisher", ["tcp", "tls", "unix"], indirect=True)
async def test_receive_after_timeout_keeps_connection(client, websocket_publisher):
    await client.connect()
    ws = await websocket_publisher[2].get()
    with pytest.raises(asyncio.TimeoutError):
        await client.recv(timeout=0.01)
    await ws.send_bytes(salt.payload.dumps({b"id": b"minion"}))
    assert await client.recv(timeout=1) == {b"id": b"minion"}
    assert websocket_publisher[2].empty()


@pytest.mark.parametrize("timeout", [0, 0.01])
@pytest.mark.parametrize("websocket_publisher", ["tcp", "tls", "unix"], indirect=True)
async def test_queued_receive_honors_timeout_without_cancelling_reader(
    client, websocket_publisher, timeout
):
    await client.connect()
    ws = await websocket_publisher[2].get()
    entered = asyncio.Event()
    receive = client._recv

    async def reading():
        entered.set()
        return await receive()

    with patch.object(client, "_recv", side_effect=reading):
        active = asyncio.create_task(client.recv())
        queued = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            queued = asyncio.create_task(client.recv(timeout=timeout))
            done, _ = await asyncio.wait([queued], timeout=1)
            assert queued in done, "receive deadline must include the lock wait"
            if timeout == 0:
                assert await queued is None
            else:
                with pytest.raises(asyncio.TimeoutError):
                    await queued
            assert not active.done()
            await ws.send_bytes(salt.payload.dumps({b"active": True}))
            assert await asyncio.wait_for(active, 1) == {b"active": True}
        finally:
            await salt.utils.asynchronous.cancel_tasks(active, queued)


async def test_nonblocking_receive_without_data_returns_none(client):
    await client.connect()
    assert await client.recv(timeout=0) is None


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


@pytest.mark.parametrize("websocket_publisher", ["tcp", "tls", "unix"], indirect=True)
async def test_legacy_wrapper_drives_async_subscriber_cleanup(websocket_publisher):
    _, _, _, received, client_options = websocket_publisher
    frame = salt.transport.frame.frame_msg({"id": "minion"})

    def send():
        with salt.utils.asynchronous.SyncWrapper(
            salt.transport.ws.PublishClient,
            args=({},),
            kwargs=client_options,
            loop_kwarg="io_loop",
        ) as wrapped:
            wrapped.connect()
            session = wrapped.obj._session
            wrapped.send(frame)
        assert session.closed

    await asyncio.wait_for(asyncio.to_thread(send), 3)
    assert await received.get() == frame
