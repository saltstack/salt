"""Async IPC publishing preserves framing and the caller's loop."""

import asyncio
import socket
import struct

import pytest
import tornado.iostream

import salt.channel.server
import salt.transport.tcp
import salt.utils.event
import salt.utils.msgpack
from tests.support.mock import Mock, patch


async def test_concurrent_async_publishes_preserve_large_frames():
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
            {"master_async_mworker": True, "ipc_write_buffer": 262144},
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


@pytest.mark.parametrize("async_mworker", [False, True])
async def test_outer_wrapper_publishes_over_ipc(async_mworker):
    """
    Unmigrated sync events need only their existing outer wrapper.

    With ``master_async_mworker`` off this is the original ``pub_sock`` path.
    """
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
                args=({"master_async_mworker": async_mworker},),
                kwargs={"pull_host": host, "pull_port": port},
            ) as server:
                server.connect()
                server.publish(b"event")

        await asyncio.wait_for(asyncio.to_thread(publish), 3)
        assert await asyncio.wait_for(received, 3) == b"event"
        await asyncio.wait_for(asyncio.gather(*handlers), 3)
        # connect() and publish() share one connection.
        assert len(handlers) == 1


async def test_connection_timeout_closes_stream():
    started = asyncio.Event()

    async def connect(stream, address):
        started.set()
        await asyncio.Event().wait()

    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", 1, None)
    try:
        with patch.object(tornado.iostream.IOStream, "connect", connect):
            with pytest.raises(asyncio.TimeoutError):
                await publisher.connect(timeout=0.01)
        assert started.is_set()
        assert publisher.stream is None
    finally:
        publisher.close()


async def test_connect_waits_for_a_listener_that_starts_late():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", port, None)
    task = asyncio.create_task(publisher.connect(timeout=3))
    try:
        await asyncio.sleep(0.3)
        assert not task.done()
        async with await asyncio.start_server(
            lambda r, w: w.close(), "127.0.0.1", port
        ):
            assert await asyncio.wait_for(task, 3) is True
            assert publisher.connected()
    finally:
        publisher.close()


async def test_connect_retries_at_a_steady_pace_until_the_timeout():
    attempts = 0

    async def refuse(stream, address):
        nonlocal attempts
        attempts += 1
        raise ConnectionRefusedError()

    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", 1, None)
    loop = asyncio.get_running_loop()
    try:
        with patch.object(tornado.iostream.IOStream, "connect", refuse):
            start = loop.time()
            with pytest.raises(ConnectionRefusedError):
                await publisher.connect(timeout=0.5)
            elapsed = loop.time() - start
        assert 0.4 <= elapsed < 2
        # One attempt per retry delay, not a busy loop.
        assert 3 <= attempts <= 8
    finally:
        publisher.close()


async def test_concurrent_connects_share_one_timeout():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", port, None)
    loop = asyncio.get_running_loop()
    try:
        start = loop.time()
        results = await asyncio.gather(
            *(publisher.connect(timeout=0.5) for _ in range(3)),
            return_exceptions=True,
        )
        # Three callers wait about 0.5 s in total, not 3 x 0.5 s.
        assert loop.time() - start < 1.0
        assert all(isinstance(result, Exception) for result in results)
    finally:
        publisher.close()


async def test_concurrent_connects_open_one_connection():
    accepted = []
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", port, None)

    def accept(reader, writer):
        accepted.append(writer)

    async with await asyncio.start_server(accept, "127.0.0.1", port):
        try:
            results = await asyncio.gather(*(publisher.connect() for _ in range(3)))
            assert results == [True, True, True]
            await asyncio.sleep(0.1)
            assert len(accepted) == 1
        finally:
            # The server waits for open connections when it closes.
            publisher.close()
            for writer in accepted:
                writer.close()


async def test_publish_reconnects_once_after_the_peer_drops_the_connection():
    received = []
    writers = []

    async def consume(reader, writer):
        writers.append(writer)
        try:
            while True:
                size = struct.unpack(">I", await reader.readexactly(4))[0]
                frame = salt.utils.msgpack.loads(
                    await reader.readexactly(size), raw=False
                )
                received.append(frame["body"])
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async with await asyncio.start_server(consume, "127.0.0.1", 0) as listener:
        host, port = listener.sockets[0].getsockname()
        server = salt.transport.tcp.PublishServer(
            {"master_async_mworker": True}, pull_host=host, pull_port=port
        )
        loop = asyncio.get_running_loop()
        try:
            await server.publish(b"first")
            for _ in range(100):
                if received:
                    break
                await asyncio.sleep(0.02)
            assert received == [b"first"]
            publisher, lock = server._async_pub_by_loop[loop]
            writers[0].close()
            for _ in range(100):
                if not publisher.connected():
                    break
                await asyncio.sleep(0.02)
            assert not publisher.connected()

            payloads = [bytes([index]) * 1000 for index in range(5)]
            await asyncio.gather(*(server.publish(item) for item in payloads))
            for _ in range(100):
                if len(received) == 6:
                    break
                await asyncio.sleep(0.02)

            assert sorted(received[1:]) == sorted(payloads)
            # One reconnect, on the same publisher and the same lock.
            assert len(writers) == 2
            assert server._async_pub_by_loop[loop] == (publisher, lock)
        finally:
            server.close()
            for writer in writers:
                writer.close()


async def test_connect_timeout_says_what_timed_out():
    async def hang(stream, address):
        await asyncio.Event().wait()

    publisher = salt.transport.tcp._AsyncPubServerPublisher("127.0.0.1", 4511, None)
    try:
        with patch.object(tornado.iostream.IOStream, "connect", hang):
            with pytest.raises(
                asyncio.TimeoutError, match="Timed out connecting to 127.0.0.1:4511"
            ):
                await publisher.connect(timeout=0.2)
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

    server = salt.transport.tcp.PublishServer(
        {"master_async_mworker": True}, pull_host="127.0.0.1", pull_port=1
    )
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


@pytest.mark.parametrize("async_mworker", [False, True])
async def test_cluster_key_reannouncement_reconnects_to_recovered_tcp_peer(
    async_mworker,
):
    loop = asyncio.get_running_loop()
    reservation = socket.socket()
    reservation.bind(("127.0.0.1", 0))
    host, port = reservation.getsockname()
    pusher = salt.transport.tcp.PublishServer(
        {"master_async_mworker": async_mworker}, pull_host=host, pull_port=port
    )
    channel = object.__new__(salt.channel.server.MasterPubServerChannel)
    channel.opts = {"id": "master"}
    channel.io_loop = Mock()
    channel.pushers = [pusher]
    payload = salt.utils.event.SaltEvent.pack("cluster/peer/master", {"key": "test"})
    channel.send_aes_key_event = Mock(
        side_effect=lambda: loop.create_task(channel.publish_payload(payload))
    )
    received = loop.create_future()
    handlers = []

    async def consume(reader, writer):
        try:
            size = struct.unpack(">I", await reader.readexactly(4))[0]
            frame = salt.utils.msgpack.loads(await reader.readexactly(size), raw=False)
            received.set_result(frame["body"])
        finally:
            writer.close()
            await writer.wait_closed()

    def accept(reader, writer):
        handlers.append(loop.create_task(consume(reader, writer)))

    try:
        # A bound socket without listen() refuses connections while reserving
        # the address for the peer that starts after the failed announcement.
        await channel.publish_payload(payload)
        channel.io_loop.call_later.assert_called_once_with(
            2.0, channel.send_aes_key_event
        )
        channel.send_aes_key_event.assert_not_called()
        reservation.close()
        async with await asyncio.start_server(accept, host, port):
            await channel.io_loop.call_later.call_args.args[1]()
            assert await asyncio.wait_for(received, 2) == payload
            await asyncio.wait_for(asyncio.gather(*handlers), 2)
        assert not pusher._closing
    finally:
        reservation.close()
        pusher.close()
        for task in handlers:
            task.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)
