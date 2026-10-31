"""Request workers await their aiohttp runner and active handler cleanup."""

import asyncio
import socket
from types import SimpleNamespace

import aiohttp
import pytest

import salt.channel.server
import salt.master
import salt.payload
import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, MagicMock, patch


def make_server():
    instance = salt.transport.ws.RequestServer({})
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.setblocking(False)
    instance._socket = sock
    instance.port = sock.getsockname()[1]
    return instance


@pytest.fixture
def server(io_loop):
    instance = make_server()
    yield instance
    loop = salt.utils.asynchronous.aioloop(io_loop)
    loop.run_until_complete(instance.close_async())


async def start(server, io_loop, handler):
    server.post_fork(handler, io_loop)
    await asyncio.wait_for(server._started.wait(), 2)


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_server_handles_sync_and_async_handlers(server, io_loop, asynchronous):
    def echo(load):
        return {"reply": load}

    async def async_echo(load):
        await asyncio.sleep(0)
        return echo(load)

    await start(server, io_loop, async_echo if asynchronous else echo)
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:{server.port}/ws") as ws:
            for payload in [None, False, 0, "", [], {}, {"nested": [False, 0]}]:
                await ws.send_bytes(salt.payload.dumps(payload))
                response = await ws.receive()
                assert salt.payload.loads(response.data) == {"reply": payload}
    await server.close_async()
    assert server._server_task.done()
    assert server._runner is None
    assert server._socket is None
    assert not asyncio.get_running_loop().is_closed()


async def test_shutdown_drains_active_handler_cleanup(server, io_loop):
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def handler(load):
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    await start(server, io_loop, handler)
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:{server.port}/ws") as ws:
            await ws.send_bytes(salt.payload.dumps("request"))
            await started.wait()
            await asyncio.wait_for(server.close_async(), 2)
            assert cleaned.is_set()
    assert not server._request_tasks


async def test_sync_close_is_drained_before_channel_exit(server, io_loop):
    await start(server, io_loop, lambda load: load)
    channel = object.__new__(salt.channel.server.ReqServerChannel)
    channel.transport = server
    channel.event = MagicMock()
    server.close()
    await channel.close_async()
    assert server._server_task.done()
    assert server._closed
    channel.event.destroy.assert_called_once()


async def test_startup_failure_closes_bound_socket(io_loop):
    server = make_server()
    sock = server._socket
    with patch.object(
        aiohttp.web.SockSite, "start", AsyncMock(side_effect=OSError("listen failed"))
    ):
        server.post_fork(lambda load: load, io_loop)
        done, _ = await asyncio.wait([server._server_task], timeout=2)
        assert server._server_task in done
        for _ in range(2):
            with pytest.raises(OSError, match="listen failed"):
                await server.close_async()
    assert sock.fileno() == -1
    assert server._closed
    assert server._runner is None


async def test_close_before_start_releases_socket(server, io_loop):
    sock = server._socket
    server.post_fork(lambda load: load, io_loop)
    server.close()
    await server.close_async()
    assert sock.fileno() == -1
    assert server._closed


async def test_request_channel_close_awaits_transport():
    order = []

    async def close():
        await asyncio.sleep(0)
        order.append("transport")

    channel = object.__new__(salt.channel.server.ReqServerChannel)
    channel.transport = SimpleNamespace(close_async=close)
    channel.event = MagicMock()
    channel.event.destroy.side_effect = lambda: order.append("event")
    await channel.close_async()
    assert order == ["transport", "event"]


@pytest.mark.parametrize("error", [OSError, asyncio.CancelledError])
@pytest.mark.parametrize("native", [False, True])
async def test_request_channel_releases_resources_after_transport_failure(
    error, native
):
    failure = error("transport cleanup failed")
    close = AsyncMock(side_effect=failure) if native else MagicMock(side_effect=failure)
    channel = object.__new__(salt.channel.server.ReqServerChannel)
    channel.transport = SimpleNamespace(**{"close_async" if native else "close": close})
    event, cache = MagicMock(), MagicMock()
    channel.event = event
    channel.ckminions = SimpleNamespace(cache=cache)
    with pytest.raises(error) as exc:
        await channel.close_async()
    assert exc.value is failure
    event.destroy.assert_called_once_with()
    cache.destroy.assert_called_once_with()
    assert channel.ckminions is None


async def test_worker_cleanup_awaits_native_and_closes_legacy_channels():
    order = []

    async def close():
        await asyncio.sleep(0)
        order.append("native")

    worker = object.__new__(salt.master.MWorker)
    worker.req_channels = [
        SimpleNamespace(close_async=close),
        SimpleNamespace(close=lambda: order.append("legacy")),
    ]
    await worker._close_channels()
    assert order == ["native", "legacy"]


@pytest.mark.parametrize("error", [OSError, asyncio.CancelledError])
async def test_worker_cleanup_continues_after_channel_error(error):
    closed = []
    worker = object.__new__(salt.master.MWorker)
    worker.req_channels = [
        SimpleNamespace(close_async=AsyncMock(side_effect=error("close failed"))),
        SimpleNamespace(close=lambda: closed.append(True)),
    ]
    if error is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            await worker._close_channels()
    else:
        await worker._close_channels()
    assert closed == [True]


async def test_pool_channel_retains_server_until_async_cleanup():
    state = []

    async def finish():
        await asyncio.sleep(0)
        state.append("drained")

    server = SimpleNamespace(close=lambda: state.append("stop"), close_async=finish)
    channel = object.__new__(salt.channel.server.PoolRoutingChannel)
    channel.pool_clients = {}
    channel.pool_client_next = {}
    channel.pool_servers = {"default": server}
    channel.event = None
    channel.transport = SimpleNamespace(close=lambda: None)
    channel.close()
    assert not channel.pool_servers
    assert state == ["stop"]
    await channel.close_async()
    assert state == ["stop", "drained"]
    assert not channel._closing_transports


async def test_pool_cleanup_finishes_other_transports_before_propagating_cancellation():
    healthy = AsyncMock()
    channel = object.__new__(salt.channel.server.PoolRoutingChannel)
    channel.pool_clients = {}
    channel.pool_client_next = {}
    channel.pool_servers = {
        "cancelled": SimpleNamespace(
            close=lambda: None,
            close_async=AsyncMock(side_effect=asyncio.CancelledError),
        ),
        "healthy": SimpleNamespace(close=lambda: None, close_async=healthy),
    }
    channel.event = None
    channel.transport = SimpleNamespace(close=lambda: None)
    with pytest.raises(asyncio.CancelledError):
        await channel.close_async()
    healthy.assert_awaited_once()
    assert not channel._closing_transports
