"""
Regression tests for the tcp transport clients under concurrent use and
across fork.

Observed on an 11-minion fleet running ``transport: tcp`` with mutual TLS:

* concurrent sends that each found ``_stream is None`` all called
  ``getstream()``: duplicate TLS handshakes, "IOStream is not idle; cannot
  convert to SSL", and replies written to orphaned streams;
* a send that landed while the reader loop was reconnecting
  (``_stream`` momentarily ``None``) was dropped on the floor, so its
  future only ever resolved by timeout ("File client timed out after 180
  seconds" in the middle of a highstate); a write that failed left the
  caller hanging the same way;
* a forked job child kept the request stream -- and the reader task
  scheduled on the inherited event loop -- it got from the minion parent,
  so two processes drove one TLS record sequence.
"""

import asyncio
import os
import ssl

import pytest
import tornado.concurrent
import tornado.iostream

import salt.exceptions
import salt.transport.frame
import salt.transport.tcp
import salt.utils.msgpack
from tests.support.mock import AsyncMock, MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]


class _CountingGetstream:
    """
    Stand-in for ``getstream``: yields to the loop (so concurrent callers can
    interleave) and counts how many times a connection was actually made.
    """

    def __init__(self, stream):
        self.stream = stream
        self.calls = 0

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        await asyncio.sleep(0.01)
        return self.stream


@pytest.fixture
def request_client(minion_opts, io_loop):
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    client = salt.transport.tcp.RequestClient(minion_opts, io_loop)
    # Keep the real reader task out of these tests; each test installs the
    # stream it needs.
    client._stream_return_running = True
    try:
        yield client
    finally:
        client._stream_return_running = False
        client.close()


@pytest.fixture
def publish_client(minion_opts, io_loop):
    client = salt.transport.tcp.PublishClient(
        minion_opts, io_loop, host="127.0.0.1", port=4505
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def message_client(minion_opts, io_loop):
    # MessageClient is deprecated (warn_until 3009), which raises under
    # RAISE_DEPRECATIONS_RUNTIME_ERRORS once the version reaches 3009; these
    # tests cover its behaviour, not the deprecation.
    with patch("salt.utils.versions.warn_until"):
        client = salt.transport.tcp.MessageClient(
            minion_opts, "127.0.0.1", 4506, io_loop=io_loop
        )
    client._stream_return_running = True
    try:
        yield client
    finally:
        client._stream_return_running = False
        client.close()


# --- connect() races ---------------------------------------------------------


async def test_request_client_connect_serializes_concurrent_callers(request_client):
    stream = MagicMock()
    getstream = _CountingGetstream(stream)
    request_client.getstream = getstream

    await asyncio.gather(*(request_client.connect() for _ in range(5)))

    assert getstream.calls == 1
    assert request_client._stream is stream


async def test_publish_client_connect_serializes_concurrent_callers(publish_client):
    stream = MagicMock()
    getstream = _CountingGetstream(stream)
    publish_client.getstream = getstream

    await asyncio.gather(*(publish_client.connect() for _ in range(5)))

    assert getstream.calls == 1
    assert publish_client._stream is stream
    assert publish_client.connected is True


async def test_message_client_connect_serializes_concurrent_callers(message_client):
    stream = MagicMock()
    getstream = _CountingGetstream(stream)
    message_client.getstream = getstream

    await asyncio.gather(*(message_client.connect() for _ in range(5)))

    assert getstream.calls == 1
    assert message_client._stream is stream


# --- sends during a reconnect -------------------------------------------------


def _reply_to(client, item, body):
    """
    Resolve the future ``client.send`` is waiting on for the framed ``item``,
    the way ``_stream_return`` would when the reply arrives.
    """
    framed = salt.utils.msgpack.loads(item, raw=False)
    client.send_future_map.pop(framed["head"]["mid"]).set_result(body)


@pytest.mark.parametrize(
    "error",
    [tornado.iostream.StreamClosedError(), ssl.SSLError(1, "[CRYPTO] unknown error")],
    ids=["stream-closed", "ssl-error"],
)
async def test_request_client_send_fails_fast_when_write_fails(request_client, error):
    """
    A write that fails is reported to the caller, promptly, and the frame is
    NOT re-sent (it may already have been flushed: a re-send would deliver
    the request twice).
    """
    stream = MagicMock()
    stream.write = AsyncMock(side_effect=error)
    request_client._stream = stream
    request_client.connect = AsyncMock()

    with pytest.raises(type(error)):
        await request_client.send({"cmd": "_file_hash"}, timeout=5)

    assert stream.write.await_count == 1
    assert request_client.send_future_map == {}


async def test_request_client_send_waits_for_reconnect(request_client):
    """
    The reader loop drops ``_stream`` (reconnecting) after ``send`` has
    already queued the message: ``_do_send`` must wait for the new stream
    and write to it instead of returning without writing.
    """
    stream = MagicMock()
    writes = []

    async def write(item):
        writes.append(item)
        _reply_to(request_client, item, {"ok": True})

    stream.write = write
    request_client._stream = stream

    connects = 0

    async def connect():
        nonlocal connects
        connects += 1
        if connects == 2:
            # ``send`` has passed its own check; the reader loop now drops
            # the stream while it reconnects ...
            request_client._stream = None
        elif connects == 4:
            # ... and lands the new one a couple of retries later.
            request_client._stream = stream

    request_client.connect = connect

    ret = await request_client.send({"cmd": "_serve_file"}, timeout=5)

    assert ret == {"ok": True}
    assert len(writes) == 1
    assert connects >= 4


async def test_message_client_send_fails_fast_when_write_fails(message_client):
    stream = MagicMock()
    stream.write = AsyncMock(side_effect=tornado.iostream.StreamClosedError())
    message_client._stream = stream
    message_client.connect = AsyncMock()

    with pytest.raises(tornado.iostream.StreamClosedError):
        await message_client.send({"cmd": "_file_hash"}, timeout=5)

    assert stream.write.await_count == 1


async def test_request_client_send_fails_when_no_stream_after_retries(
    request_client,
):
    """
    No stream ever comes back: the caller gets an error even with no timeout
    set, instead of waiting forever.
    """
    request_client._stream = MagicMock()
    request_client.connect = AsyncMock()

    async def send_then_lose_stream():
        # Let ``send`` pass its own stream check, then take the stream away
        # for good (the reconnect never lands).
        task = asyncio.ensure_future(
            request_client.send({"cmd": "_serve_file"}, timeout=None)
        )
        await asyncio.sleep(0)
        request_client._stream = None
        return await task

    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        await send_then_lose_stream()

    assert request_client.send_future_map == {}


async def test_request_client_send_fails_when_closed(request_client):
    request_client._stream = MagicMock()
    request_client.connect = AsyncMock()
    request_client._closed = True

    with pytest.raises(salt.transport.tcp.ClosingError):
        await request_client.send({"cmd": "_file_hash"}, timeout=5)


# --- fork safety --------------------------------------------------------------


def test_request_client_keeps_stream_in_creating_process(request_client):
    stream = MagicMock()
    request_client._stream = stream

    request_client._drop_inherited_stream()

    assert request_client._stream is stream
    stream.close.assert_not_called()


def test_request_client_forgets_inherited_stream_on_pid_change(request_client):
    stream = MagicMock()
    task = MagicMock()
    request_client._stream = stream
    request_client.task = task
    request_client.send_future_map = {"mid": MagicMock()}
    child_pid = request_client._creator_pid + 1

    with patch("salt.transport.tcp.os.getpid", return_value=child_pid):
        request_client._drop_inherited_stream()

    # Forgotten, never closed: the socket belongs to the parent.
    assert request_client._stream is None
    stream.close.assert_not_called()
    task.cancel.assert_not_called()
    assert request_client.task is None
    assert request_client.send_future_map == {}
    assert request_client._stream_return_running is False
    assert request_client._creator_pid == child_pid


async def test_request_client_connect_in_child_opens_its_own_stream(request_client):
    inherited = MagicMock()
    fresh = MagicMock()
    request_client._stream = inherited
    getstream = _CountingGetstream(fresh)
    request_client.getstream = getstream
    child_pid = request_client._creator_pid + 1

    with patch("salt.transport.tcp.os.getpid", return_value=child_pid):
        # The child's own reader must be started on its new stream.
        request_client._stream_return_running = False
        with patch.object(request_client, "_stream_return", new=AsyncMock()):
            await request_client.connect()
            await asyncio.sleep(0)

    assert request_client._stream is fresh
    assert getstream.calls == 1
    inherited.close.assert_not_called()
    request_client._stream_return_running = True


async def test_request_client_stream_return_exits_in_forked_child(request_client):
    stream = MagicMock()
    stream.read_bytes = AsyncMock(side_effect=AssertionError("read in the child"))
    request_client._stream = stream
    request_client.disconnect_callback = MagicMock()

    # The task records the pid it started in; the next looks (loop check,
    # then the finally) say "other process".
    with patch("salt.transport.tcp.os.getpid", side_effect=[1111, 2222, 2222]):
        await request_client._stream_return()

    stream.read_bytes.assert_not_called()
    stream.close.assert_not_called()
    request_client.disconnect_callback.assert_not_called()
    assert request_client._stream is stream


async def test_request_client_stream_return_reads_in_creating_process(
    request_client,
):
    """
    Control for the test above: in the process that started it, the reader
    delivers replies to the waiting futures.
    """
    stream = MagicMock()
    future = tornado.concurrent.Future()
    request_client.send_future_map["abc"] = future
    payload = salt.transport.frame.frame_msg({"ok": 1}, header={"mid": "abc"})

    async def read_bytes(*args, **kwargs):
        if not request_client.send_future_map:
            # Reply delivered: end the loop the way a shutdown would.
            request_client._closing = True
            raise tornado.iostream.StreamClosedError()
        return payload

    stream.read_bytes = read_bytes
    request_client._stream = stream

    await request_client._stream_return()

    assert future.result() == {"ok": 1}


async def test_request_client_connect_forked_while_connecting(request_client):
    """
    The fork lands while ``getstream`` is in flight: the stream it returns
    was created by the parent and must not be adopted (or closed); the child
    connects again on its own.
    """
    parent_stream = MagicMock()
    fresh = MagicMock()
    real_pid = request_client._creator_pid
    pids = [real_pid]
    streams = [parent_stream, fresh]

    async def getstream(**kwargs):
        stream = streams.pop(0)
        if stream is parent_stream:
            pids[0] = real_pid + 1  # the fork happened during this await
        return stream

    request_client.getstream = getstream
    request_client._stream_return_running = False
    with patch("salt.transport.tcp.os.getpid", side_effect=lambda: pids[0]):
        with patch.object(request_client, "_stream_return", new=AsyncMock()):
            await request_client.connect()
            await asyncio.sleep(0)

    assert request_client._stream is fresh
    assert not streams
    parent_stream.close.assert_not_called()
    assert request_client._creator_pid == real_pid + 1
    request_client._stream_return_running = True


async def test_request_client_getstream_discards_socket_from_before_fork(
    request_client,
):
    parent_stream = MagicMock()
    fresh = MagicMock()
    real_pid = request_client._creator_pid
    pids = [real_pid]

    async def connect_tls(*args, **kwargs):
        if connect_tls.calls == 0:
            pids[0] = real_pid + 1  # forked while the handshake was in flight
            connect_tls.calls += 1
            return parent_stream
        return fresh

    connect_tls.calls = 0
    request_client._tcp_client.connect_tls = connect_tls

    with patch("salt.transport.tcp.os.getpid", side_effect=lambda: pids[0]):
        stream = await request_client.getstream()

    assert stream is fresh
    parent_stream.close.assert_not_called()


# --- cancelled readers must die ------------------------------------------------


async def test_request_client_reader_dies_on_cancel(request_client):
    """
    A cancelled ``_stream_return`` must terminate.  Swallowing the
    CancelledError left the task alive: its next ``read_bytes`` raised
    ``AssertionError: Already reading`` and the generic exception handler
    resurrected it with a close + reconnect, reconnecting forever.
    """
    stream = MagicMock()

    async def read_bytes(*args, **kwargs):
        request_client._closing = True  # cancelled by close()
        raise asyncio.CancelledError()

    stream.read_bytes = read_bytes
    request_client._stream = stream
    request_client.connect = AsyncMock()

    task = asyncio.ensure_future(request_client._stream_return())
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)

    assert task.cancelled()
    # The reader must NOT have resurrected itself with a reconnect, and the
    # stream is close()'s to handle.
    request_client.connect.assert_not_awaited()
    stream.close.assert_not_called()
    assert request_client._stream_return_running is False


async def test_request_client_reader_cancel_not_by_close_fails_waiters(
    request_client,
):
    """
    A reader cancelled by anything but close() leaves a stream nobody reads:
    the waiting sends are failed at once (not left to time out) and the
    stream is dropped, so the next send() reconnects with a new reader.
    """
    stream = MagicMock()
    stream.read_bytes = AsyncMock(side_effect=asyncio.CancelledError())
    request_client._stream = stream
    request_client.connect = AsyncMock()
    waiter = asyncio.get_running_loop().create_future()
    request_client.send_future_map = {"mid-1": waiter}

    task = asyncio.ensure_future(request_client._stream_return())
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)

    request_client.connect.assert_not_awaited()
    assert isinstance(waiter.exception(), tornado.iostream.StreamClosedError)
    assert request_client.send_future_map == {}
    assert request_client._stream is None
    stream.close.assert_called_once()
    assert request_client._stream_return_running is False


async def test_request_client_reader_cancel_in_child_leaves_parent_stream(
    request_client,
):
    """
    A forked child cancelling the reader it inherited (e.g. SyncWrapper's
    orphan reaping) must not close or fail the parent's stream and futures.
    """
    stream = MagicMock()
    waiter = asyncio.get_running_loop().create_future()
    request_client._stream = stream
    request_client.send_future_map = {"mid-1": waiter}
    real_pid = os.getpid()
    pids = [real_pid]

    async def read_bytes(*args, **kwargs):
        pids[0] = real_pid + 1  # the fork happens while the read is parked
        raise asyncio.CancelledError()

    stream.read_bytes = read_bytes
    with patch("salt.transport.tcp.os.getpid", side_effect=lambda: pids[0]):
        task = asyncio.ensure_future(request_client._stream_return())
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)

    stream.close.assert_not_called()
    assert not waiter.done()
    assert request_client._stream is stream


async def test_request_client_reader_cancel_during_reconnect_resets_flag(
    request_client,
):
    """
    A cancel landing while the reader is reconnecting (inside an exception
    handler, not at ``read_bytes``) still clears ``_stream_return_running``
    and drops whatever stream is current, so a later connect() starts a
    reader again instead of leaving a stream nobody reads.
    """
    stream = MagicMock()
    stream.read_bytes = AsyncMock(side_effect=tornado.iostream.StreamClosedError())
    request_client._stream = stream

    async def connect():
        await asyncio.Event().wait()  # master down: parked in backoff

    request_client.connect = connect
    task = asyncio.ensure_future(request_client._stream_return())
    await asyncio.sleep(0.05)
    assert request_client._stream_return_running is True

    # Meanwhile a send's connect() installs a new stream; it saw the flag
    # still set, so it started no reader of its own.
    new_stream = MagicMock()
    request_client._stream = new_stream

    task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    assert request_client._stream_return_running is False
    # No stream may be left without a reader: the next send reconnects.
    assert request_client._stream is None
    new_stream.close.assert_called_once()


async def test_request_client_reader_cancel_terminates_drain(request_client):
    """
    Cancel + gather a parked reader: the drain completes (previously hung
    forever: the reader survived the cancel, then failed ``read_bytes`` with
    "Already reading" and reconnected).
    """
    stream = MagicMock()

    async def read_bytes(*args, **kwargs):
        await asyncio.Event().wait()  # park like a real pending read

    stream.read_bytes = read_bytes
    request_client._stream = stream
    task = asyncio.ensure_future(request_client._stream_return())
    await asyncio.sleep(0.05)

    task.cancel()
    gathered = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    assert any(isinstance(exc, asyncio.CancelledError) for exc in gathered)
    assert request_client._stream_return_running is False
