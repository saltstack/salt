"""Failure and concurrency behavior of WebSocket publisher shutdown."""

import asyncio

import pytest

import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, Mock, patch


@pytest.fixture
def server():
    return salt.transport.ws.PublishServer(
        {"ipv6": False},
        pub_host="127.0.0.1",
        pub_port=4505,
        pull_host="127.0.0.1",
        pull_port=4506,
    )


async def test_ipc_startup_failure_releases_started_websocket_server(server):
    failure = OSError("IPC bind failed")
    runner = Mock(setup=AsyncMock(), cleanup=AsyncMock())
    site = Mock(start=AsyncMock())
    sock = Mock()
    sock.getsockname.return_value = ("127.0.0.1", 4505)
    with (
        patch("salt.transport.ws._get_socket", return_value=sock),
        patch("aiohttp.web.ServerRunner", return_value=runner),
        patch("aiohttp.web.SockSite", return_value=site),
        patch("asyncio.start_server", AsyncMock(side_effect=failure)),
    ):
        with pytest.raises(OSError) as exc:
            await server.publisher(AsyncMock())
    assert exc.value is failure
    site.start.assert_awaited_once()
    runner.cleanup.assert_awaited_once()
    assert not server.started.is_set()
    assert server.runner is None
    assert server.puller is None


@pytest.mark.parametrize("operation", ["connect", "publish"])
@pytest.mark.parametrize("in_context", [False, True])
async def test_close_cancels_and_drains_inflight_operation(
    server, operation, in_context
):
    entered = asyncio.Event()
    released = asyncio.Event()

    async def blocked(*args):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            released.set()

    writer = Mock(is_closing=Mock(return_value=False), wait_closed=AsyncMock())
    if operation == "publish":
        server.pub_writer = writer
        writer.drain = blocked

    async def call():
        operation_coro = (
            server.connect() if operation == "connect" else server.publish({"id": 1})
        )
        if in_context:
            async with server:
                await operation_coro
        else:
            await operation_coro

    with patch("asyncio.open_connection", side_effect=blocked):
        task = asyncio.create_task(call())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.wait_for(server.close_async(), 2)
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
            assert released.is_set()
            assert server.pub_writer is None
            if operation == "publish":
                writer.wait_closed.assert_awaited_once()
        finally:
            await salt.utils.asynchronous.cancel_tasks(task, server.close_task)


@pytest.mark.parametrize("fails", [False, True])
async def test_concurrent_close_waits_for_one_cleanup_and_reports_result(server, fails):
    entered = asyncio.Event()
    release = asyncio.Event()
    failure = RuntimeError("runner cleanup failed")

    async def cleanup():
        entered.set()
        await release.wait()
        if fails:
            raise failure

    runner = Mock(cleanup=AsyncMock(side_effect=cleanup))
    server.runner = runner
    server._loop = asyncio.get_running_loop()
    callers = [asyncio.create_task(server.close_async()) for _ in range(3)]
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert all(not task.done() for task in callers)
        release.set()
        results = await asyncio.wait_for(
            asyncio.gather(*callers, return_exceptions=True), 2
        )
        assert results == ([failure] * 3 if fails else [None] * 3)
        runner.cleanup.assert_awaited_once()
        assert server.runner is None
    finally:
        release.set()
        await salt.utils.asynchronous.cancel_tasks(*callers, server.close_task)


async def test_cancelling_close_waiter_does_not_cancel_cleanup(server):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def wait_closed():
        entered.set()
        await release.wait()

    writer = Mock(wait_closed=AsyncMock(side_effect=wait_closed))
    server.pub_writer = writer
    server._loop = asyncio.get_running_loop()
    caller = asyncio.create_task(server.close_async())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        caller.cancel()
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert not server.close_task.done()
        release.set()
        await asyncio.wait_for(server.close_async(), 2)
        writer.wait_closed.assert_awaited_once()
        assert server._closed
    finally:
        release.set()
        await salt.utils.asynchronous.cancel_tasks(caller, server.close_task)
