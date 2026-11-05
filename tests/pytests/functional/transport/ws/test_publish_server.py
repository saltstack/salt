"""WebSocket publication owns its IPC handlers and leaves the caller loop running."""

import asyncio
import tempfile

import aiohttp
import pytest

import salt.payload
import salt.transport.ws
import salt.utils.asynchronous
from tests.support.mock import AsyncMock, Mock, patch


def pusher_options(publisher):
    if publisher.pull_path:
        return {"pull_path": publisher.pull_path}
    return {"pull_host": "127.0.0.1", "pull_port": publisher.pull_port}


@pytest.fixture(params=["tcp", "unix"])
def publisher(io_loop, request):
    if request.param == "unix":
        directory = tempfile.TemporaryDirectory(prefix="salt-ws-pub-", dir="/tmp")
        request.addfinalizer(directory.cleanup)
        pull_opts = {"pull_path": f"{directory.name}/pull"}
    else:
        pull_opts = {"pull_host": "127.0.0.1", "pull_port": 0}
    server = salt.transport.ws.PublishServer(
        {"ipv6": False},
        pub_host="127.0.0.1",
        pub_port=0,
        **pull_opts,
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
    server = salt.transport.ws.PublishServer({}, **pusher_options(publisher))
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
    if publisher.pull_path:
        _, writer = await asyncio.open_unix_connection(publisher.pull_path)
    else:
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


@pytest.mark.parametrize("running_publisher", [False, True])
@pytest.mark.parametrize(
    "error", [ConnectionResetError, RuntimeError, asyncio.CancelledError]
)
async def test_close_reports_stream_error_after_releasing_resources(
    running_publisher, error
):
    server = salt.transport.ws.PublishServer(
        {"ipv6": False},
        pub_host="127.0.0.1",
        pub_port=0,
        pull_host="127.0.0.1",
        pull_port=0,
    )
    publisher_task = None
    if running_publisher:
        publisher_task = asyncio.create_task(server.publisher(server.publish_payload))
        assert await asyncio.to_thread(server.started.wait, 2)
    else:
        server._loop = asyncio.get_running_loop()
        server.runner = Mock(cleanup=AsyncMock())

    failure = error("stream closure failed")
    broken = Mock(wait_closed=AsyncMock(side_effect=failure))
    healthy = Mock(wait_closed=AsyncMock())
    handlers = [asyncio.create_task(asyncio.Event().wait()) for _ in range(2)]
    server._ipc_connections.update(zip(handlers, (broken, healthy)))
    pusher = Mock(wait_closed=AsyncMock())
    server.pub_writer = pusher
    runner = server.runner
    try:
        target = aiohttp.web.ServerRunner if running_publisher else runner
        with patch.object(target, "cleanup", wraps=runner.cleanup) as cleanup:
            with pytest.raises(error) as exc:
                await asyncio.wait_for(server.close_async(), 2)
            if error is not asyncio.CancelledError:
                assert exc.value is failure
            cleanup.assert_awaited_once()
        healthy.wait_closed.assert_awaited_once()
        pusher.wait_closed.assert_awaited_once()
        assert all(task.done() for task in handlers)
        assert server.runner is None
        assert server.puller is None
        assert server.pub_writer is None
        assert server._closed
        if running_publisher:
            assert server._monitor_task.done()
            assert server._publisher_done.is_set()
        with pytest.raises(error):
            await server.close_async()
    finally:
        if publisher_task is not None:
            publisher_task.cancel()
            await asyncio.gather(publisher_task, return_exceptions=True)
        await salt.utils.asynchronous.cancel_tasks(*handlers)


async def test_legacy_wrapper_awaits_pusher_cleanup(publisher):
    received = asyncio.Queue()
    publisher._pub_payload = received.put_nowait

    def publish():
        with salt.utils.asynchronous.SyncWrapper(
            salt.transport.ws.PublishServer,
            args=({},),
            kwargs=pusher_options(publisher),
        ) as wrapped:
            wrapped.connect()
            native = wrapped.obj
            writer = native.pub_writer
            wrapped.publish({b"value": b"event"})
        assert writer.is_closing()
        assert native._closed

    await asyncio.wait_for(asyncio.to_thread(publish), 3)
    assert await asyncio.wait_for(received.get(), 2) == {b"value": b"event"}
