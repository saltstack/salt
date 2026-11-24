"""
Regression tests for saltstack/salt#70938 -- the ws PublishServer must
not wedge the master when a subscriber stalls.

``PublishServer.publish`` accepts a ``timeout`` in seconds. When the
underlying ``StreamWriter.drain`` does not complete within it, publish
raises ``TimeoutError`` to the caller instead of waiting forever.
``PublishServer.publish_payload`` applies the same bound per client: a
stalled subscriber is dropped (same remediation as ``ConnectionResetError``)
and the fan-out continues so one slow minion cannot stop publishes to
every other minion.

Mirrors ``test_pub_server_send_timeout.py`` (the TCP seam added by
#70461).
"""

import asyncio
import gc

import pytest

import salt.transport.ws
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.core_test,
]


class _WedgedWriter:
    """StreamWriter stand-in whose drain() never completes."""

    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)

    async def drain(self):
        # Never resolves.
        await asyncio.Future()


class _InstantWriter:
    """StreamWriter stand-in whose drain() completes immediately."""

    def __init__(self):
        self.written = []

    def write(self, data):
        self.written.append(data)

    async def drain(self):
        return None


class _SlowWriter:
    """StreamWriter stand-in whose drain() resolves via an external future."""

    def __init__(self, drain_future):
        self.written = []
        self._drain_future = drain_future

    def write(self, data):
        self.written.append(data)

    async def drain(self):
        await self._drain_future


def _publish_server(pub_writer):
    server = object.__new__(salt.transport.ws.PublishServer)
    server.pub_writer = pub_writer
    server.clients = set()
    return server


def _capture_loop_errors(loop):
    handler = MagicMock()
    loop.set_exception_handler(handler)
    return handler


async def test_publish_with_timeout_raises_timeout_error_on_wedged_drain():
    server = _publish_server(_WedgedWriter())
    with pytest.raises(TimeoutError):
        # Outer wait_for only bounds the harness; the inner publish
        # timeout is what we are asserting on.
        await asyncio.wait_for(server.publish(b"payload", timeout=0.1), timeout=10)


async def test_publish_without_timeout_completes():
    server = _publish_server(_InstantWriter())
    assert await server.publish(b"payload") is None


async def test_publish_timeout_does_not_cancel_the_drain():
    """On timeout the caller stops waiting; the pending drain is
    observed, not cancelled, so bytes the stream may still flush are
    not dropped and the late completion produces no unretrieved-
    exception warning."""
    drain_future = asyncio.get_running_loop().create_future()
    server = _publish_server(_SlowWriter(drain_future))

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        with pytest.raises(TimeoutError):
            await server.publish(b"payload", timeout=0.05)
        assert not drain_future.cancelled()
        # Late completion is consumed by the observer, no warning.
        drain_future.set_result(None)
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)


async def test_publish_timeout_late_failure_is_consumed():
    """A drain that fails after the caller gave up must not surface
    through the loop exception handler."""
    drain_future = asyncio.get_running_loop().create_future()
    server = _publish_server(_SlowWriter(drain_future))

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        with pytest.raises(TimeoutError):
            await server.publish(b"payload", timeout=0.05)
        drain_future.set_exception(RuntimeError("late"))
        await asyncio.sleep(0)
        del server, drain_future
        gc.collect()
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)


async def test_publish_timeout_late_failure_warns_when_observer_disabled(
    monkeypatch,
):
    """RED control: with the observer disabled, the identical sequence
    DOES warn - so the GREEN assertion above proves real consumption,
    not a future that is merely still referenced."""
    monkeypatch.setattr(salt.transport.ws, "_observe_late_task", lambda task: None)
    drain_future = asyncio.get_running_loop().create_future()
    server = _publish_server(_SlowWriter(drain_future))

    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:
        with pytest.raises(TimeoutError):
            await server.publish(b"payload", timeout=0.05)
        drain_future.set_exception(RuntimeError("late"))
        await asyncio.sleep(0)
        del server, drain_future
        gc.collect()
        await asyncio.sleep(0)
        assert handler.called
    finally:
        loop.set_exception_handler(None)


class _WedgedWS:
    """WebSocketResponse stand-in whose send_bytes() never completes."""

    def __init__(self):
        self.sent = []

    async def send_bytes(self, payload):
        self.sent.append(payload)
        await asyncio.Future()


class _InstantWS:
    """WebSocketResponse stand-in whose send_bytes() completes immediately."""

    def __init__(self):
        self.sent = []

    async def send_bytes(self, payload):
        self.sent.append(payload)


async def test_publish_payload_drops_stalled_subscriber_and_continues():
    """A subscriber whose send_bytes stalls is dropped from
    ``self.clients`` (same remediation as ``ConnectionResetError``) and
    the fan-out continues to the healthy subscribers."""
    wedged = _WedgedWS()
    healthy = _InstantWS()
    server = _publish_server(_InstantWriter())
    server.clients = {wedged, healthy}
    # Per-subscriber timeout is instance-scoped so ``publish_payload``'s
    # signature stays identical to the abstract base (see
    # ``test_transport_publishserver_has_method_signatures``).
    server._publish_payload_timeout = 0.05
    await server.publish_payload({"ok": True})
    # Wedged client was dropped.
    assert wedged not in server.clients
    # Healthy client stayed and received the payload.
    assert healthy in server.clients
    assert len(healthy.sent) == 1


async def test_publish_payload_without_timeout_unchanged():
    """``timeout=None`` keeps the original path: fan-out awaits each
    ``send_bytes`` directly without a timeout wrap."""
    healthy = _InstantWS()
    server = _publish_server(_InstantWriter())
    server.clients = {healthy}
    await server.publish_payload({"ok": True})
    assert healthy in server.clients
    assert len(healthy.sent) == 1


async def test_publish_payload_wedged_send_is_observed_not_cancelled():
    """Per-client timeout must observe the stalled send, not cancel
    it, so the aiohttp writer isn't torn down mid-flight by us."""
    loop = asyncio.get_running_loop()
    send_future = loop.create_future()

    class _SlowWS:
        def __init__(self):
            self.sent = []

        async def send_bytes(self, payload):
            self.sent.append(payload)
            await send_future

    slow = _SlowWS()
    server = _publish_server(_InstantWriter())
    server.clients = {slow}
    server._publish_payload_timeout = 0.05

    handler = _capture_loop_errors(loop)
    try:
        await server.publish_payload({"ok": True})
        assert slow not in server.clients
        # Late completion is consumed; no warning.
        send_future.set_result(None)
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)


async def test_observe_late_task_consumes_already_failed_future():
    """A task that fails inside the timeout/cancel race window is
    already done when observed; it must still be consumed so no
    'exception was never retrieved' warning reaches the loop."""
    loop = asyncio.get_running_loop()
    handler = _capture_loop_errors(loop)
    try:

        async def _boom():
            raise RuntimeError("late")

        task = asyncio.ensure_future(_boom())
        # Let it finish failing.
        await asyncio.sleep(0)
        assert task.done()
        salt.transport.ws._observe_late_task(task)
        del task
        gc.collect()
        await asyncio.sleep(0)
        assert not handler.called
    finally:
        loop.set_exception_handler(None)
