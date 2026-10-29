"""Native IPC publishing preserves framing and the caller's loop."""

import asyncio
import struct

import pytest
import tornado.iostream

import salt.transport.tcp
import salt.utils.msgpack
from tests.support.mock import patch


@pytest.mark.parametrize("async_mworker", [False, True])
async def test_concurrent_native_publishes_preserve_large_frames(async_mworker):
    received = []
    readers = []
    complete = asyncio.Event()
    payloads = [bytes([index]) * 90000 for index in range(24)]

    async def consume(reader, writer):
        try:
            while True:
                size = struct.unpack(">I", await reader.readexactly(4))[0]
                frame = salt.utils.msgpack.loads(
                    await reader.readexactly(size), raw=False
                )
                received.append(frame["body"])
                if len(received) == len(payloads):
                    complete.set()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    def accept(reader, writer):
        readers.append(asyncio.create_task(consume(reader, writer)))

    async with await asyncio.start_server(accept, "127.0.0.1", 0) as listener:
        host, port = listener.sockets[0].getsockname()
        server = salt.transport.tcp.PublishServer(
            {"master_async_mworker": async_mworker, "ipc_write_buffer": 262144},
            pull_host=host,
            pull_port=port,
        )
        try:
            with patch(
                "salt.utils.asynchronous.SyncWrapper",
                side_effect=AssertionError("unexpected wrapper"),
            ):
                await asyncio.gather(*(server.publish(payload) for payload in payloads))
            await asyncio.wait_for(complete.wait(), 3)
            assert received == payloads
            assert len(server._async_pub_by_loop) == 1
        finally:
            server.close()
            await asyncio.wait_for(asyncio.gather(*readers), 3)
    assert not asyncio.get_running_loop().is_closed()


async def test_legacy_outer_wrapper_uses_native_ipc_connection():
    """Unmigrated sync events need only their existing outer wrapper."""
    received = asyncio.get_running_loop().create_future()
    handlers = []

    async def consume(reader, writer):
        try:
            size = struct.unpack(">I", await reader.readexactly(4))[0]
            frame = salt.utils.msgpack.loads(await reader.readexactly(size), raw=False)
            received.set_result(frame["body"])
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    def accept(reader, writer):
        handlers.append(asyncio.create_task(consume(reader, writer)))

    async with await asyncio.start_server(accept, "127.0.0.1", 0) as listener:
        host, port = listener.sockets[0].getsockname()

        def publish():
            with salt.utils.asynchronous.SyncWrapper(
                salt.transport.tcp.PublishServer,
                args=({},),
                kwargs={"pull_host": host, "pull_port": port},
            ) as server:
                server.connect()
                server.publish(b"event")

        await asyncio.wait_for(asyncio.to_thread(publish), 3)
        assert await asyncio.wait_for(received, 3) == b"event"
        await asyncio.wait_for(asyncio.gather(*handlers), 3)


async def test_connection_timeout_closes_stream():
    started = asyncio.Event()

    async def connect(stream, address):
        started.set()
        await asyncio.Event().wait()

    publisher = salt.transport.tcp._TCPPubServerPublisher("127.0.0.1", 1, None)
    try:
        with patch.object(tornado.iostream.IOStream, "connect", connect):
            with pytest.raises(asyncio.TimeoutError):
                await publisher.connect(timeout=0.01)
        assert started.is_set()
        assert publisher.stream is None
    finally:
        publisher.close()


async def test_cancelled_publish_drains_connect():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def connect(stream, address):
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            stopped.set()

    server = salt.transport.tcp.PublishServer({}, pull_host="127.0.0.1", pull_port=1)
    try:
        with patch.object(tornado.iostream.IOStream, "connect", connect):
            task = asyncio.create_task(server.publish(b"event"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert stopped.is_set()
        publisher, _ = server._async_pub_by_loop[asyncio.get_running_loop()]
        assert publisher.stream is None
    finally:
        server.close()
    assert not asyncio.get_running_loop().is_closed()
