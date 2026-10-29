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


async def test_timeout_discards_connection_and_allows_retry(client, websocket_server):
    with pytest.raises(SaltReqTimeoutError):
        await client.send("wait", timeout=0.02)
    assert client.ws is None
    assert client.session is None
    assert await client.send("next") == "next"
    assert websocket_server["connections"] == 2


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


async def test_close_async_drains_active_request(client, websocket_server):
    active = asyncio.create_task(client.send("wait"))
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
    assert transport.close_task is None


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
