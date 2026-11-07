"""WebSocket requests serialize replies and close on the caller's loop."""

import asyncio
import tempfile

import aiohttp.web
import pytest

import salt.channel.client
import salt.payload
import salt.transport.ws
import salt.utils.asynchronous
from salt.exceptions import SaltClientError, SaltReqTimeoutError
from salt.transport.tcp import ClosingError
from tests.support.mock import AsyncMock, patch


@pytest.fixture
def websocket_server(io_loop, request):
    state = {
        "connections": 0,
        "received": [],
        "waiting": asyncio.Event(),
        "release": asyncio.Event(),
    }

    async def handle(request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        state["connections"] += 1
        async for message in ws:
            load = salt.payload.loads(message.data)
            state["received"].append(load)
            if load == "wait":
                state["waiting"].set()
                await state["release"].wait()
            if load == "close":
                await ws.close()
                break
            if ws.closed:
                break
            try:
                await ws.send_bytes(salt.payload.dumps(load))
            except ConnectionResetError:
                break
        return ws

    app = aiohttp.web.Application()
    app.router.add_get("/ws", handle)
    runner = aiohttp.web.AppRunner(app)

    mode = getattr(request, "param", "tcp")
    ssl_context = None
    if mode == "tls":
        ssl_context = salt.transport.base.ssl_context(
            request.getfixturevalue("ssl_master_config"), server_side=True
        )
        state["ssl"] = request.getfixturevalue("ssl_minion_config")
    socket_path = None
    if mode == "unix":
        directory = tempfile.TemporaryDirectory(prefix="salt-ws-", dir="/tmp")
        request.addfinalizer(directory.cleanup)
        socket_path = f"{directory.name}/request"

    async def start():
        await runner.setup()
        if socket_path is not None:
            site = aiohttp.web.UnixSite(runner, socket_path)
        else:
            site = aiohttp.web.TCPSite(runner, "127.0.0.1", 0, ssl_context=ssl_context)
        await site.start()
        if socket_path is not None:
            state["uri"] = f"ipc://{socket_path}"
        else:
            host, port = runner.addresses[0]
            scheme = "https" if ssl_context is not None else "http"
            state["uri"] = f"{scheme}://{host}:{port}/ws"

    loop = salt.utils.asynchronous.aioloop(io_loop)
    loop.run_until_complete(start())
    yield state
    state["release"].set()
    loop.run_until_complete(runner.cleanup())


@pytest.fixture
def client(websocket_server, io_loop):
    opts = {"master_uri": websocket_server["uri"]}
    if "ssl" in websocket_server:
        opts["ssl"] = websocket_server["ssl"]
    instance = salt.transport.ws.RequestClient(opts, io_loop)
    yield instance
    salt.utils.asynchronous.aioloop(io_loop).run_until_complete(instance.close_async())


async def test_repeated_requests_reuse_connection(client, websocket_server):
    assert await client.send({"request": 1}) == {"request": 1}
    session = client.session
    assert await client.send({"request": 2}) == {"request": 2}
    assert client.session is session
    assert websocket_server["connections"] == 1


async def test_concurrent_requests_keep_their_own_replies(client, websocket_server):
    loads = [{"request": index} for index in range(20)]
    assert await asyncio.gather(*(client.send(load) for load in loads)) == loads
    assert websocket_server["received"] == loads
    assert websocket_server["connections"] == 1


async def test_connect_and_send_share_one_connection(client, websocket_server):
    loads = [{"request": index} for index in range(10)]
    results = await asyncio.gather(
        *(client.connect() for _ in range(10)),
        *(client.send(load) for load in loads),
    )
    assert all(ws is client.ws for ws in results[:10])
    assert results[10:] == loads
    assert websocket_server["connections"] == 1


async def test_connect_reuses_healthy_connection_during_active_request(
    client, websocket_server
):
    active = asyncio.create_task(client.send("wait"))
    await websocket_server["waiting"].wait()
    ws = client.ws
    try:
        assert await asyncio.wait_for(client.connect(), 1) is ws
        assert not active.done()
        assert websocket_server["connections"] == 1
    finally:
        websocket_server["release"].set()
        assert await active == "wait"


@pytest.mark.parametrize("websocket_server", ["tcp", "tls", "unix"], indirect=True)
async def test_timeout_discards_connection_and_allows_retry(client, websocket_server):
    with pytest.raises(SaltReqTimeoutError):
        await client.send("wait", timeout=0.02)
    assert client.ws is None
    assert client.session is None
    assert await client.send("next") == "next"
    assert websocket_server["connections"] == 2


@pytest.mark.parametrize("websocket_server", ["tcp", "tls", "unix"], indirect=True)
async def test_queued_timeout_does_not_close_active_request(client, websocket_server):
    active = asyncio.create_task(client.send("wait"))
    await websocket_server["waiting"].wait()
    with pytest.raises(SaltReqTimeoutError):
        await client.send("queued", timeout=0.01)
    websocket_server["release"].set()
    assert await active == "wait"
    assert websocket_server["received"] == ["wait"]
    assert await client.send("next") == "next"
    assert websocket_server["connections"] == 1


@pytest.mark.parametrize("websocket_server", ["tcp", "tls", "unix"], indirect=True)
async def test_cancelled_request_cannot_leave_a_reply_for_next_request(
    client, websocket_server
):
    active = asyncio.create_task(client.send("wait"))
    await websocket_server["waiting"].wait()
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active
    assert client.session is None
    assert await client.send("next") == "next"
    assert websocket_server["connections"] == 2


async def test_peer_close_is_an_error_and_allows_reconnect(client):
    with pytest.raises(SaltClientError, match="closed"):
        await client.send("close")
    assert await client.send("next") == "next"


@pytest.mark.parametrize("timeout", [60, None])
async def test_close_async_drains_active_request(client, websocket_server, timeout):
    active = asyncio.create_task(client.send("wait", timeout=timeout))
    await websocket_server["waiting"].wait()
    session = client.session
    await client.close_async()
    with pytest.raises(asyncio.CancelledError):
        await active
    assert session.closed
    assert client.ws is None
    assert client._closed
    with pytest.raises(ClosingError):
        await client.send("after close")
    assert not asyncio.get_running_loop().is_closed()


async def test_async_channel_exit_awaits_websocket_cleanup(websocket_server):
    opts = {"transport": "ws", "master_uri": websocket_server["uri"]}
    async with salt.channel.client.AsyncReqChannel.factory(
        opts, crypt="clear"
    ) as channel:
        assert (await channel.send({"cmd": "ping"}))["load"] == {"cmd": "ping"}
        transport = channel.transport
        session = transport.session
    assert session.closed
    assert transport._closed
    assert transport.ws is None
    assert transport.close_task.done()


async def test_sync_close_is_awaitable_through_close_async(client):
    await client.send("ping")
    session = client.session
    client.close()
    await client.close_async()
    assert session.closed
    assert client.close_task.done()


async def test_failed_connect_closes_new_session(client):
    session = aiohttp.ClientSession()
    with patch("aiohttp.ClientSession", return_value=session), patch.object(
        session, "ws_connect", AsyncMock(side_effect=OSError("connect failed"))
    ):
        with pytest.raises(OSError, match="connect failed"):
            await client.connect()
    assert session.closed
    assert client.session is None
    assert client.ws is None


async def test_close_drains_active_and_queued_requests(client, websocket_server):
    active = asyncio.create_task(client.send("wait"))
    await websocket_server["waiting"].wait()
    queued = [asyncio.create_task(client.send(index)) for index in range(5)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.wait_for(client.close_async(), 1)
    results = await asyncio.gather(active, *queued, return_exceptions=True)
    assert all(isinstance(result, asyncio.CancelledError) for result in results)
    assert websocket_server["received"] == ["wait"]
    assert not client._operation_tasks
    assert client._closed


async def test_close_during_connect_drains_child_before_channel_exit(client):
    started, finalized = asyncio.Event(), asyncio.Event()
    session = aiohttp.ClientSession()

    async def handshake(*args, **kwargs):
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            finalized.set()

    async def caller():
        with patch("salt.transport.request_client", return_value=client):
            async with salt.channel.client.AsyncReqChannel.factory(
                {"transport": "ws"}, crypt="clear"
            ) as channel:
                await channel.connect()

    with patch("aiohttp.ClientSession", return_value=session), patch.object(
        session, "ws_connect", handshake
    ):
        task = asyncio.create_task(caller())
        await started.wait()
        queued = [
            asyncio.create_task(client.connect()),
            asyncio.create_task(client.send("queued")),
        ]
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.wait_for(client.close_async(), 1)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        results = await asyncio.gather(*queued, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
    assert finalized.is_set()
    assert session.closed
    assert not client._operation_tasks


async def test_close_waiters_share_cleanup_when_one_is_cancelled(client):
    await client.send("ping")
    started, release = asyncio.Event(), asyncio.Event()
    close_connection = client._close_connection

    async def cleanup():
        started.set()
        await release.wait()
        await close_connection()

    with patch.object(
        client, "_close_connection", AsyncMock(side_effect=cleanup)
    ) as close:
        first = asyncio.create_task(client.close_async())
        await started.wait()
        second = asyncio.create_task(client.close_async())
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert not client.close_task.cancelled()
        release.set()
        await asyncio.wait_for(second, 1)
        close.assert_awaited_once_with()
    assert client._closed


@pytest.mark.parametrize("websocket_server", ["tls"], indirect=True)
async def test_mutual_tls_requests_reuse_connection(client, websocket_server):
    assert await client.send("first") == "first"
    assert await client.send("second") == "second"
    assert websocket_server["connections"] == 1


@pytest.mark.skip_on_windows
@pytest.mark.parametrize("websocket_server", ["unix"], indirect=True)
async def test_unix_socket_requests_reuse_connection(client, websocket_server):
    assert await client.send("first") == "first"
    assert await client.send("second") == "second"
    assert websocket_server["connections"] == 1
