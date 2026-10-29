"""WebSocket request failures and cancellation preserve operation ownership."""

import asyncio
from types import SimpleNamespace

import aiohttp
import pytest

import salt.channel.client
import salt.payload
import salt.transport.ws
import salt.utils.asynchronous
from salt.exceptions import (
    SaltClientError,
    SaltDeserializationError,
    SaltReqTimeoutError,
)
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def connection():
    ws = MagicMock()
    ws.closed = False
    ws.send_bytes = AsyncMock()
    ws.receive = AsyncMock(
        return_value=SimpleNamespace(
            type=aiohttp.WSMsgType.BINARY, data=salt.payload.dumps({"reply": True})
        )
    )

    async def close_ws():
        ws.closed = True

    ws.close = AsyncMock(side_effect=close_ws)
    session = MagicMock()
    session.closed = False
    session.ws_connect = AsyncMock(return_value=ws)

    async def close_session():
        session.closed = True

    session.close = AsyncMock(side_effect=close_session)
    return session, ws


@pytest.fixture
def client(io_loop, connection):
    instance = salt.transport.ws.RequestClient(
        {"master_uri": "http://127.0.0.1:4506/ws"}, io_loop
    )
    with patch("aiohttp.ClientSession", return_value=connection[0]):
        yield instance
    salt.utils.asynchronous.aioloop(io_loop).run_until_complete(instance.close_async())


@pytest.mark.parametrize(
    "message_type",
    [aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR],
)
async def test_non_binary_reply_releases_connection(client, connection, message_type):
    session, ws = connection
    ws.receive.return_value = SimpleNamespace(type=message_type, data="invalid")
    with pytest.raises(SaltClientError, match="non-binary reply"):
        await client.send("request")
    assert session.closed
    ws.close.assert_awaited_once_with()
    assert client.ws is client.session is None
    assert not client._operation_tasks


@pytest.mark.parametrize("operation", ["send", object(), AsyncMock()])
async def test_unknown_operation_is_rejected_before_starting_io(
    client, connection, operation
):
    with pytest.raises(TypeError, match="Expected a WebSocket request operation"):
        client._start_operation(operation)
    connection[0].ws_connect.assert_not_awaited()
    assert not client._operation_tasks
    if isinstance(operation, AsyncMock):
        operation.assert_not_called()


async def test_malformed_binary_reply_releases_connection(client, connection):
    session, ws = connection
    ws.receive.return_value.data = b"\x81"
    with pytest.raises(SaltDeserializationError):
        await client.send("request")
    assert session.closed
    assert ws.closed
    assert client.ws is client.session is None


@pytest.mark.parametrize("stage", ["send_bytes", "receive"])
async def test_io_failure_releases_connection(client, connection, stage):
    session, ws = connection
    getattr(ws, stage).side_effect = OSError("network failed")
    with pytest.raises(OSError, match="network failed"):
        await client.send("request")
    assert session.closed
    assert ws.closed
    assert client.ws is client.session is None


async def test_timeout_includes_connection_handshake(client, connection):
    session, ws = connection
    finalized = asyncio.Event()

    async def handshake(*args, **kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    session.ws_connect.side_effect = handshake
    with pytest.raises(SaltReqTimeoutError):
        await client.send("request", timeout=0.01)
    assert finalized.is_set()
    assert session.closed
    ws.send_bytes.assert_not_awaited()
    assert client.ws is client.session is None


@pytest.mark.parametrize("timeout", [60, None])
async def test_cancelling_queued_request_preserves_active_exchange(
    client, connection, timeout
):
    session, ws = connection
    started, release = asyncio.Event(), asyncio.Event()

    async def receive():
        started.set()
        await release.wait()
        return SimpleNamespace(
            type=aiohttp.WSMsgType.BINARY, data=salt.payload.dumps("ok")
        )

    ws.receive.side_effect = receive
    active = asyncio.create_task(client.send("active"))
    await started.wait()
    queued = asyncio.create_task(client.send("queued", timeout=timeout))
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert not active.done()
        session.close.assert_not_awaited()
        ws.send_bytes.assert_awaited_once_with(salt.payload.dumps("active"))
    finally:
        release.set()
        await asyncio.gather(active, queued, return_exceptions=True)
    assert await active == "ok"
    assert await client.send("next") == "ok"
    session.ws_connect.assert_awaited_once()


async def test_channel_async_close_waits_for_prior_sync_close(client):
    with patch("salt.transport.request_client", return_value=client):
        channel = salt.channel.client.AsyncReqChannel.factory(
            {"transport": "ws"}, crypt="clear"
        )
    await channel.send({"request": 1})
    channel.close()
    await channel.close_async()
    assert client._closed
    assert client.close_task.done()


@pytest.mark.no_blocking(
    reason="The synchronous ReqChannel API intentionally drives its private event loop."
)
def test_sync_channel_close_awaits_websocket_cleanup(connection):
    session, _ = connection
    with patch("aiohttp.ClientSession", return_value=session):
        channel = salt.channel.client.ReqChannel.factory(
            {"transport": "ws", "master_uri": "http://127.0.0.1:4506/ws"},
            crypt="clear",
        )
        transport = channel.obj.transport
        try:
            assert channel.send({"request": 1}) == {"reply": True}
        finally:
            channel.close()
    assert transport._closed
    assert session.closed
    assert transport.close_task.done()
    assert not transport.close_task.cancelled()
