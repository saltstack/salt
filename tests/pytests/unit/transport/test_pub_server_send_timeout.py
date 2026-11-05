"""
Regression tests for saltstack/salt#69824 -- a wedged event-bus pull
side must not deadlock the publisher forever.

``_TCPPubServerPublisher.send`` accepts a ``timeout`` in seconds. When
the underlying stream write does not complete within it, the send
raises ``TimeoutError`` to the caller instead of waiting forever.
``PublishServer.publish`` forwards the timeout so both the sync
(``SyncWrapper``) and async call paths behave the same way.
"""

import asyncio
import gc
import os

import pytest
import tornado.concurrent
import tornado.iostream

import salt.transport.tcp
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.core_test,
]


class _WedgedStream:
    """Stream stand-in whose write never completes (wedged pull side)."""

    def closed(self):
        return False

    def write(self, data):
        return tornado.concurrent.Future()  # never resolves


class _InstantStream:
    """Stream stand-in whose write completes immediately."""

    def closed(self):
        return False

    def write(self, data):
        future = tornado.concurrent.Future()
        future.set_result(None)
        return future


def _publisher(stream):
    pub = object.__new__(salt.transport.tcp._TCPPubServerPublisher)
    pub.stream = stream
    pub._closing = True  # keep __del__ quiet for the stub
    pub._creator_pid = os.getpid()
    return pub


async def test_send_with_timeout_raises_timeout_error_on_wedged_write():
    pub = _publisher(_WedgedStream())
    with pytest.raises(TimeoutError):
        # The outer wait_for only bounds the test harness; the inner
        # send timeout is the behavior under test.
        await asyncio.wait_for(pub.send(b"payload", timeout=0.1), timeout=10)


async def test_send_without_timeout_completes():
    pub = _publisher(_InstantStream())
    assert await pub.send(b"payload") is None


def test_publish_server_publish_forwards_timeout():
    server = object.__new__(salt.transport.tcp.PublishServer)
    server.opts = {}
    server.pub_sock = MagicMock()
    asyncio.run(server.publish(b"payload", timeout=7))
    server.pub_sock.send.assert_called_once_with(b"payload", timeout=7)


class _ClosedStream:
    """Stream stand-in whose write fails immediately (closed connection)."""

    def closed(self):
        return False

    def write(self, data):
        future = tornado.concurrent.Future()
        future.set_exception(
            tornado.iostream.StreamClosedError(real_error=OSError("closed"))
        )
        return future


async def test_send_with_timeout_propagates_stream_errors():
    """A failed write surfaces its own error, not a timeout."""
    pub = _publisher(_ClosedStream())
    with pytest.raises(tornado.iostream.StreamClosedError):
        await pub.send(b"payload", timeout=5)


async def test_send_timeout_does_not_cancel_the_write():
    """On timeout the caller stops waiting; the pending write is observed,
    not cancelled, so bytes the stream may still flush are not dropped and
    the late completion produces no unretrieved-exception warning."""
    write_future = tornado.concurrent.Future()

    class _SlowStream:
        def closed(self):
            return False

        def write(self, data):
            return write_future

    pub = _publisher(_SlowStream())
    with pytest.raises(TimeoutError):
        await pub.send(b"payload", timeout=0.05)
    assert not write_future.cancelled()
    # Late completion is consumed by the observer, no warning is emitted.
    write_future.set_result(None)
    await asyncio.sleep(0)


def test_fire_event_uses_configured_publish_timeout(monkeypatch):
    import salt.utils.event
    import salt.utils.metrics
    import salt.utils.tracing

    monkeypatch.setattr(salt.utils.tracing, "inject", lambda data: None)

    class _Counter:
        def add(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        salt.utils.metrics, "counter", lambda *args, **kwargs: _Counter()
    )

    event = object.__new__(salt.utils.event.SaltEvent)
    event.opts = {"max_event_size": 100000, "event_publish_timeout": 7}
    event.cpush = True
    event._run_io_loop_sync = True
    event.pusher = MagicMock()

    assert event.fire_event({"data": "x"}, "tag") is True
    event.pusher.publish.assert_called_once()
    assert event.pusher.publish.call_args.kwargs["timeout"] == 7


def test_fire_event_uses_default_publish_timeout(monkeypatch):
    import salt.utils.event
    import salt.utils.metrics
    import salt.utils.tracing

    monkeypatch.setattr(salt.utils.tracing, "inject", lambda data: None)

    class _Counter:
        def add(self, *args, **kwargs):
            pass

    monkeypatch.setattr(
        salt.utils.metrics, "counter", lambda *args, **kwargs: _Counter()
    )

    event = object.__new__(salt.utils.event.SaltEvent)
    event.opts = {"max_event_size": 100000}
    event.cpush = True
    event._run_io_loop_sync = True
    event.pusher = MagicMock()

    assert event.fire_event({"data": "x"}, "tag") is True
    event.pusher.publish.assert_called_once()
    assert event.pusher.publish.call_args.kwargs["timeout"] == 60


def _capture_loop_errors(loop):
    handler = MagicMock()
    loop.set_exception_handler(handler)
    return handler


async def test_unobserved_failed_future_warns_via_loop_handler():
    """Adverse control: the detection used below actually fires."""
    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        future = tornado.concurrent.Future()
        future.set_exception(RuntimeError("late"))
        del future
        gc.collect()
        await asyncio.sleep(0)
        assert handler.called
    finally:
        loop.set_exception_handler(None)


async def test_observe_late_write_consumes_already_failed_future():
    """A write that fails inside the timeout/cancel race window is
    already done when observed; it must still be consumed so no
    'exception was never retrieved' warning reaches the loop."""
    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        future = tornado.concurrent.Future()
        future.set_exception(RuntimeError("late"))
        salt.transport.tcp._observe_late_write(future)
        del future
        gc.collect()
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)


async def _timeout_then_late_failure():
    """Shared flow: send times out on a wedged write, the write then
    fails late, every reference is released and the garbage collector
    runs. Returns the loop exception handler mock; an unretrieved late
    failure would surface through it on GC."""
    write_future = tornado.concurrent.Future()

    class _SlowStream:
        def closed(self):
            return False

        def write(self, data):
            return write_future

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        pub = _publisher(_SlowStream())
        with pytest.raises(TimeoutError):
            await pub.send(b"payload", timeout=0.05)
        write_future.set_exception(RuntimeError("late"))
        # Let the observer's done-callback run, then release EVERY
        # reference (the stream's closure goes with ``pub``) so an
        # unconsumed failure would hit Future.__del__ and warn.
        await asyncio.sleep(0)
        del pub, write_future
        gc.collect()
        await asyncio.sleep(0)
        return handler
    finally:
        loop.set_exception_handler(None)


async def test_send_timeout_then_late_failure_is_consumed():
    handler = await _timeout_then_late_failure()
    assert not handler.called


async def test_send_timeout_late_failure_warns_when_observer_disabled(monkeypatch):
    """RED control: with the observer disabled, the identical sequence
    DOES warn - so the GREEN assertion proves real consumption, not a
    future that is merely still referenced."""
    monkeypatch.setattr(salt.transport.tcp, "_observe_late_write", lambda write: None)
    handler = await _timeout_then_late_failure()
    assert handler.called


async def test_send_timeout_then_write_cancellation_is_consumed():
    """A pending write cancelled after the timeout must not surface an
    unhandled CancelledError from the observer callback."""
    write_future = tornado.concurrent.Future()

    class _SlowStream:
        def closed(self):
            return False

        def write(self, data):
            return write_future

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        pub = _publisher(_SlowStream())
        with pytest.raises(TimeoutError):
            await pub.send(b"payload", timeout=0.05)
        write_future.cancel()
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)


async def _caller_cancellation_then_late_failure():
    """Shared flow: the caller of send() is cancelled; the pending
    write must be observed (not cancelled) and its late failure
    consumed. Returns the loop exception handler mock."""
    write_future = tornado.concurrent.Future()

    class _SlowStream:
        def closed(self):
            return False

        def write(self, data):
            return write_future

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        pub = _publisher(_SlowStream())
        task = asyncio.ensure_future(pub.send(b"payload", timeout=5))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not write_future.cancelled()
        write_future.set_exception(RuntimeError("late"))
        # Let the observer's done-callback run, then release EVERY
        # reference so an unconsumed failure would warn on GC.
        await asyncio.sleep(0)
        del pub, task, write_future
        gc.collect()
        await asyncio.sleep(0)
        return handler
    finally:
        loop.set_exception_handler(None)


async def test_send_caller_cancellation_late_failure_warns_when_observer_disabled(
    monkeypatch,
):
    """RED control: with the observer disabled, the caller-cancel
    sequence DOES warn on GC."""
    monkeypatch.setattr(salt.transport.tcp, "_observe_late_write", lambda write: None)
    handler = await _caller_cancellation_then_late_failure()
    assert handler.called


async def test_send_caller_cancellation_observes_the_write():
    handler = await _caller_cancellation_then_late_failure()
    assert not handler.called


def _async_publish_server():
    server = object.__new__(salt.transport.tcp.PublishServer)
    server.opts = {"master_async_mworker": True}
    server.pull_host = "127.0.0.1"
    server.pull_port = 4514
    server.pull_path = None
    return server


def _fake_pub_factory(created, fail_first_send=False):
    def _make(*args, **kwargs):
        pub = MagicMock()
        pub.stream.closed.return_value = False
        pub.send_calls = []

        async def _connect():
            return None

        async def _send(payload, timeout=None):
            pub.send_calls.append((payload, timeout))
            if fail_first_send and len(created) == 1:
                raise tornado.iostream.StreamClosedError(real_error=OSError("closed"))

        pub.connect = _connect
        pub.send = _send
        created.append(pub)
        return pub

    return _make


async def test_publish_async_first_send_forwards_configured_timeout(monkeypatch):
    created = []
    monkeypatch.setattr(
        salt.transport.tcp,
        "_TCPPubServerPublisher",
        _fake_pub_factory(created),
    )
    server = _async_publish_server()
    await server.publish(b"payload", timeout=7)
    assert len(created) == 1
    assert created[0].send_calls == [(b"payload", 7)]


async def test_publish_async_retry_forwards_configured_timeout(monkeypatch):
    created = []
    monkeypatch.setattr(
        salt.transport.tcp,
        "_TCPPubServerPublisher",
        _fake_pub_factory(created, fail_first_send=True),
    )
    server = _async_publish_server()
    await server.publish(b"payload", timeout=7)
    assert len(created) == 2
    assert created[0].send_calls == [(b"payload", 7)]
    assert created[1].send_calls == [(b"payload", 7)]


async def test_publish_sync_path_forwards_configured_timeout():
    server = object.__new__(salt.transport.tcp.PublishServer)
    server.opts = {}
    server.pub_sock = MagicMock()
    await server.publish(b"payload", timeout=7)
    server.pub_sock.send.assert_called_once_with(b"payload", timeout=7)


async def test_publish_sync_path_omits_timeout_kwarg_when_unset():
    """Call shape stays uniform with the other transports when no
    timeout is configured: no keyword is passed at all."""
    server = object.__new__(salt.transport.tcp.PublishServer)
    server.opts = {}
    server.pub_sock = MagicMock()
    await server.publish(b"payload")
    server.pub_sock.send.assert_called_once_with(b"payload")


def test_master_rst_event_return_example_not_split_by_new_section():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[4]
    text = (root / "doc" / "ref" / "configuration" / "master.rst").read_text()
    # The pre-existing event_return YAML example stays one contiguous
    # block, and the new option is documented outside it.
    assert "event_return:\n      - syslog\n      - splunk" in text
    assert ".. conf_master:: event_publish_timeout" in text
