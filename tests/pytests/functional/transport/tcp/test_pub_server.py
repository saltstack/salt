import asyncio
import os
import time

import pytest
import tornado.gen
import tornado.iostream

import salt.transport.frame
import salt.transport.tcp
import salt.utils.msgpack
from tests.support.mock import patch


async def test_publisher_close_during_connect_no_attribute_error_69187(
    io_loop, monkeypatch
):
    started = asyncio.Event()
    release = asyncio.Event()
    real_connect = tornado.iostream.IOStream.connect

    async def slow_connect(self, address, *args, **kwargs):
        started.set()
        await release.wait()
        return await real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(tornado.iostream.IOStream, "connect", slow_connect)
    async with await asyncio.start_server(
        lambda reader, writer: writer.close(), "127.0.0.1", 0
    ) as server:
        host, port = server.sockets[0].getsockname()
        publisher = salt.transport.tcp._TCPPubServerPublisher(
            host, port, None, io_loop=io_loop
        )
        task = asyncio.create_task(publisher.connect())
        await asyncio.wait_for(started.wait(), 2)
        publisher.close()
        release.set()
        with pytest.raises(salt.transport.tcp.ClosingError):
            await asyncio.wait_for(task, 2)


async def test_pub_channel(master_opts, minion_opts, io_loop):
    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts["transport"] = "tcp"
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=master_opts["publish_port"],
        pull_path=os.path.join(master_opts["sock_dir"], "publish_pull.ipc"),
    )

    client = salt.transport.tcp.PublishClient(
        minion_opts,
        io_loop,
        host="127.0.0.1",
        port=master_opts["publish_port"],
    )

    payloads = []

    publishes = []

    async def publish_payload(payload):
        await server.publish_payload(payload)
        payloads.append(payload)

    async def on_recv(message):
        publishes.append(message)

    io_loop.add_callback(
        server.publisher, publish_payload, presence_callback, remove_presence_callback
    )

    # Wait for socket to bind.
    await asyncio.sleep(3)

    await client.connect(master_opts["publish_port"])
    client.on_recv(on_recv)

    await server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not publishes:
            await tornado.gen.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "Message not published after 30 seconds"
    finally:
        server.close()
        client.close()


async def test_pub_channel_raw_payload_passthrough(master_opts, minion_opts, io_loop):
    """
    PR #70052 regression: end-to-end pack -> pull -> raw_payload
    passthrough -> subscriber round-trip.

    ``TCPPuller.handle_stream`` hands the pull-side wire bytes to the
    ``payload_handler`` as ``raw_payload=<bytes>``.  When the handler
    calls ``PublishServer.publish_payload(package, raw_payload=raw)``
    the wire bytes are written to subscribers verbatim, skipping the
    ``frame_msg`` step in ``PubServer.publish_payload``.  This test
    exercises the whole loop against a real TCP transport and asserts
    the message decodes correctly on the client side -- proving the
    passthrough bytes are still a valid framed msgpack payload.
    """

    def presence_callback(client):
        pass

    def remove_presence_callback(client):
        pass

    master_opts["transport"] = "tcp"
    minion_opts.update(master_ip="127.0.0.1", transport="tcp")

    server = salt.transport.tcp.PublishServer(
        master_opts,
        pub_host="127.0.0.1",
        pub_port=master_opts["publish_port"],
        pull_path=os.path.join(master_opts["sock_dir"], "publish_pull_raw.ipc"),
    )

    client = salt.transport.tcp.PublishClient(
        minion_opts,
        io_loop,
        host="127.0.0.1",
        port=master_opts["publish_port"],
    )

    frame_calls = []
    publishes = []
    handler_calls = []

    async def publish_payload(payload, raw_payload=None):
        # ``TCPPuller.handle_stream`` calls the handler with
        # ``raw_payload=<pull-side wire bytes>``.  Forward those bytes
        # into the pub_server so the passthrough path is taken.
        handler_calls.append(raw_payload)
        await server.publish_payload(payload, raw_payload=raw_payload)

    async def on_recv(message):
        publishes.append(message)

    real_frame_msg = salt.transport.frame.frame_msg

    def counting_frame_msg(*args, **kwargs):
        frame_calls.append(args)
        return real_frame_msg(*args, **kwargs)

    io_loop.add_callback(
        server.publisher, publish_payload, presence_callback, remove_presence_callback
    )

    # Wait for socket to bind.
    await asyncio.sleep(3)

    await client.connect(master_opts["publish_port"])
    client.on_recv(on_recv)

    payload = {"meh": "bah", "nested": {"a": 1, "b": [1, 2, 3]}}

    # Patch frame_msg for the duration of the publish so we can assert
    # the passthrough branch (raw_payload provided) does NOT re-frame.
    with patch(
        "salt.transport.tcp.salt.transport.frame.frame_msg",
        side_effect=counting_frame_msg,
    ):
        await server.publish(payload)

        start = time.monotonic()
        try:
            while not publishes:
                await tornado.gen.sleep(0.3)
                if time.monotonic() - start > 30:
                    assert False, "Message not published after 30 seconds"
        finally:
            server.close()
            client.close()

    # The handler saw the raw wire bytes from the pull side.
    assert handler_calls, "handle_stream must forward raw_payload to handler"
    assert handler_calls[0] is not None, (
        "raw_payload should be the framed msgpack bytes read from the "
        "pull socket, not None"
    )
    assert isinstance(handler_calls[0], (bytes, bytearray))

    # And the subscriber received a body that decodes back to the
    # original dict -- the wire bytes weren't corrupted by the
    # passthrough.  ``PublishClient`` unpacks with default ``raw=True``
    # semantics so top-level dict keys/values arrive as bytes; walk
    # the structure to normalize before comparing.
    assert publishes, "subscriber must have received the passthrough payload"

    def _normalize(obj):
        if isinstance(obj, dict):
            return {_normalize(k): _normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_normalize(x) for x in obj]
        if isinstance(obj, bytes):
            try:
                return obj.decode()
            except UnicodeDecodeError:
                return obj
        return obj

    assert _normalize(publishes[0]) == payload

    # PubServer.publish_payload's re-framing branch was NOT hit for
    # our publish (raw_payload was supplied).  frame_msg IS still
    # called elsewhere in the pipeline (e.g. IPC-side send), so we
    # can't assert zero calls -- but we assert the pub_server did not
    # reframe our payload dict.
    for call_args in frame_calls:
        assert call_args and call_args[0] != payload, (
            "pub_server.publish_payload must not re-frame the payload dict "
            "when raw_payload is supplied"
        )


class _FakeStream:
    """Minimal ``IOStream`` stand-in for ``PubServer.publish_payload``.

    ``mode='ok'`` records writes and returns a resolved Future.
    ``mode='full'`` raises ``StreamBufferFullError`` synchronously from
    ``write``, mirroring the tornado behavior when a stream's
    ``max_write_buffer_size`` cap is exceeded.
    ``mode='closed'`` raises ``StreamClosedError`` synchronously.
    """

    def __init__(self, mode="ok"):
        self.mode = mode
        self.writes = []
        self._closed = False

    def write(self, payload):
        if self.mode == "full":
            raise tornado.iostream.StreamBufferFullError(
                "Reached maximum write buffer size"
            )
        if self.mode == "closed":
            raise tornado.iostream.StreamClosedError()
        self.writes.append(payload)
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut

    def close(self):
        self._closed = True


def _minimal_pub_opts(tmp_path):
    """Minimal opts dict that satisfies ``PubServer.__init__``/``publish_payload``
    without pulling in the full ``master_opts`` fixture (which requires
    saltfactories + pytest-system-statistics)."""
    return {
        "id": "regression-master",
        "sock_dir": str(tmp_path),
        "publish_drain_timeout": 5.0,
    }


async def test_publish_payload_buffer_full_does_not_abort_broadcast(io_loop, tmp_path):
    """
    Regression: ``PubServer.publish_payload`` must not let a synchronous
    ``StreamBufferFullError`` from one subscriber abort the broadcast to
    the rest.

    Before the fix only ``StreamClosedError`` was caught, so when a
    subscriber's tornado write buffer overflowed (which happens once
    ``ipc_write_buffer`` is set and a peer stops draining), the
    exception propagated out of the loop and every subscriber after the
    offender silently missed the payload.
    """
    server = salt.transport.tcp.PubServer(
        _minimal_pub_opts(tmp_path),
        io_loop=io_loop,
        presence_callback=None,
        remove_presence_callback=lambda client: None,
    )

    class _FakeClient:
        def __init__(self, mode):
            self.stream = _FakeStream(mode=mode)
            self.address = f"fake-{mode}"
            self.id_ = None
            self._closed = False

        def close(self):
            self._closed = True

    fast_a = _FakeClient("ok")
    slow_full = _FakeClient("full")
    fast_b = _FakeClient("ok")

    server.clients.add(fast_a)
    server.clients.add(slow_full)
    server.clients.add(fast_b)

    await server.publish_payload({"marker": "regression-broadcast"})

    try:
        # Fast subscribers each got exactly one write despite the
        # buffer-full peer in the middle of the loop.  Before the fix,
        # the offending peer's StreamBufferFullError propagated out and
        # every subscriber after it in the iteration order silently
        # missed the payload.
        assert len(fast_a.stream.writes) == 1, (
            "fast subscriber A should have received exactly one write "
            "even though another subscriber's write raised StreamBufferFullError"
        )
        assert len(fast_b.stream.writes) == 1, (
            "fast subscriber B should have received exactly one write "
            "even though another subscriber's write raised StreamBufferFullError"
        )
        # The buffer-full subscriber was discarded and never held a write.
        assert slow_full.stream.writes == []
        assert slow_full not in server.clients
        assert slow_full._closed
        # Fast subscribers stayed subscribed.
        assert fast_a in server.clients
        assert fast_b in server.clients
    finally:
        server.close()


async def test_publish_payload_buffer_full_with_topic_list(io_loop, tmp_path):
    """
    Same regression but exercising the ``topic_list`` code path in
    ``publish_payload``.  A topic-matched subscriber whose write raises
    ``StreamBufferFullError`` must not abort the fan-out to other
    matching subscribers.
    """
    server = salt.transport.tcp.PubServer(
        _minimal_pub_opts(tmp_path),
        io_loop=io_loop,
        presence_callback=None,
        remove_presence_callback=lambda client: None,
    )

    class _FakeClient:
        def __init__(self, id_, mode):
            self.stream = _FakeStream(mode=mode)
            self.address = f"fake-{id_}"
            self.id_ = id_
            self._closed = False

        def close(self):
            self._closed = True

    matched_full = _FakeClient("minion-A", "full")
    matched_ok = _FakeClient("minion-A", "ok")
    other = _FakeClient("minion-B", "ok")

    server.clients.add(matched_full)
    server.clients.add(matched_ok)
    server.clients.add(other)

    await server.publish_payload(
        {"marker": "regression-topic"}, topic_list=["minion-A"]
    )

    try:
        assert len(matched_ok.stream.writes) == 1
        assert matched_full.stream.writes == []
        assert other.stream.writes == []  # topic-filtered out, as expected
        assert matched_full not in server.clients
        assert matched_ok in server.clients
        assert other in server.clients
    finally:
        server.close()
