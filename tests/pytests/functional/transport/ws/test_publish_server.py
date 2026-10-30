"""WebSocket publication owns its IPC handlers and leaves the caller loop running."""

import asyncio

import aiohttp
import pytest

import salt.payload
import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, Mock, patch


@pytest.fixture
def publisher(io_loop):
    server = salt.transport.ws.PublishServer(
        {"ipv6": False},
        pub_host="127.0.0.1",
        pub_port=0,
        pull_host="127.0.0.1",
        pull_port=0,
    )
    loop = salt.utils.asynchronous.aioloop(io_loop)

    async def start():
        task = asyncio.create_task(server.publisher(server.publish_payload))
        assert await asyncio.to_thread(server.started.wait, 2)
        return task

    task = loop.run_until_complete(start())
    yield server
    loop.run_until_complete(server.close_async())
    loop.run_until_complete(asyncio.gather(task, return_exceptions=True))


@pytest.fixture
def pusher(publisher, io_loop):
    server = salt.transport.ws.PublishServer(
        {}, pull_host="127.0.0.1", pull_port=publisher.pull_port
    )
    yield server
    salt.utils.asynchronous.aioloop(io_loop).run_until_complete(server.close_async())


async def test_native_ipc_publication_reaches_subscriber(publisher, pusher):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            f"http://127.0.0.1:{publisher.pub_port}/ws"
        ) as ws:
            await pusher.publish({b"result": b"ok"})
            reply = await asyncio.wait_for(ws.receive(), 2)
            assert salt.payload.loads(reply.data, raw=True) == {b"result": b"ok"}


async def test_concurrent_publications_keep_large_messages_intact(publisher, pusher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait
    payloads = [{b"sequence": index, b"body": b"x" * 90000} for index in range(20)]
    await asyncio.gather(*(pusher.publish(payload) for payload in payloads))
    actual = [await asyncio.wait_for(received.get(), 2) for _ in payloads]
    assert actual == payloads
    assert len(publisher._ipc_connections) == 1


async def test_concurrent_connects_reuse_pusher(pusher):
    await asyncio.gather(*(pusher.connect() for _ in range(10)))
    writer = pusher.pub_writer
    await pusher.connect()
    assert pusher.pub_writer is writer


async def test_ipc_eof_finishes_handler(publisher, pusher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait
    await pusher.publish({b"id": b"minion"})
    await received.get()
    handlers = tuple(publisher._ipc_connections)
    await pusher.close_async()
    await asyncio.wait_for(asyncio.gather(*handlers), 2)
    assert not publisher._ipc_connections


@pytest.mark.parametrize(
    "error", [ConnectionResetError, RuntimeError, asyncio.CancelledError]
)
async def test_disconnect_pusher_handles_only_connection_errors(pusher, error):
    failure = error("stream closure failed")
    writer = Mock(wait_closed=AsyncMock(side_effect=failure))
    pusher.pub_reader = object()
    pusher.pub_writer = writer

    if issubclass(error, ConnectionError):
        await pusher._disconnect_pusher()
    else:
        with pytest.raises(error) as exc:
            await pusher._disconnect_pusher()
        assert exc.value is failure

    assert pusher.pub_reader is None
    assert pusher.pub_writer is None


async def test_partial_ipc_frames_are_reassembled(publisher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait
    _, writer = await asyncio.open_connection("127.0.0.1", publisher.pull_port)
    try:
        payload = salt.payload.dumps({b"data": b"payload"}, use_bin_type=True)
        writer.write(payload[:3])
        await writer.drain()
        writer.write(payload[3:])
        await writer.drain()
        assert await asyncio.wait_for(received.get(), 2) == {b"data": b"payload"}
    finally:
        writer.close()
        await writer.wait_closed()


async def test_close_drains_handlers_and_shutdown_watcher(publisher, pusher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait
    await pusher.publish({b"request": True})
    await received.get()
    handlers = tuple(publisher._ipc_connections)
    watcher = publisher._monitor_task
    await publisher.close_async()
    assert publisher._closed
    assert watcher.done()
    assert all(task.done() for task in handlers)
    assert publisher.runner is None
    assert publisher.puller is None
    assert not asyncio.get_running_loop().is_closed()


async def test_startup_error_releases_runner_and_own_loop_survives():
    server = salt.transport.ws.PublishServer(
        {"ipv6": False},
        pub_host="127.0.0.1",
        pub_port=0,
        pull_host="127.0.0.1",
        pull_port=0,
    )
    with patch.object(
        aiohttp.web.SockSite, "start", AsyncMock(side_effect=OSError("bind failed"))
    ):
        with pytest.raises(OSError, match="bind failed"):
            await server.publisher(server.publish_payload)
    assert server._closed
    assert server.runner is None
    assert server._publisher_done.is_set()
    assert not asyncio.get_running_loop().is_closed()


async def test_cancelling_publisher_releases_resources(publisher):
    task = publisher._publisher_task
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert publisher._closed
    assert publisher._monitor_task.done()


async def test_legacy_wrapper_awaits_pusher_cleanup(publisher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait

    def publish():
        with salt.utils.asynchronous.SyncWrapper(
            salt.transport.ws.PublishServer,
            args=({},),
            kwargs={"pull_host": "127.0.0.1", "pull_port": publisher.pull_port},
        ) as wrapped:
            wrapped.connect()
            native = wrapped.obj
            writer = native.pub_writer
            wrapped.publish({b"value": b"event"})
        assert writer.is_closing()
        assert native._closed

    await asyncio.wait_for(asyncio.to_thread(publish), 3)
    assert await asyncio.wait_for(received.get(), 2) == {b"value": b"event"}
