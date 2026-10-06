"""
Event bus tracing: fire_event must inject the current trace context into the
event data dict, and downstream consumers must be able to extract it as the
parent for a child span.
"""

import pytest

import salt.utils.event
import salt.utils.tracing as tracing


@pytest.fixture(autouse=True)
def _reset_tracing(monkeypatch):
    tracing.shutdown()
    monkeypatch.setattr(tracing, "_cached_opts", None)
    yield
    tracing.shutdown()


@pytest.fixture
def in_memory_exporter(monkeypatch):
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    monkeypatch.setattr(tracing, "_build_exporter", lambda _opts: exporter)
    return exporter


def _make_event_stub():
    """Build a SaltEvent without touching IPC sockets; only fire_event() runs."""
    event = salt.utils.event.SaltEvent.__new__(salt.utils.event.SaltEvent)
    event.opts = {"max_event_size": 100000, "subproxy": False}
    event.cpush = True
    event._run_io_loop_sync = True

    sent = []

    class _FakePusher:
        @staticmethod
        def publish(msg):
            sent.append(msg)

    event.pusher = _FakePusher
    return event, sent


def test_fire_event_injects_when_span_active(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    event, sent = _make_event_stub()

    with tracing.start_span("client"):
        event.fire_event({"hello": "world"}, "salt/test/tag")

    assert sent, "expected one event published"
    raw = sent[0]
    _tag, data = salt.utils.event.SaltEvent.unpack(raw)
    assert "traceparent" in data, "event payload must carry traceparent"


def test_fire_event_skipped_when_no_span(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    event, sent = _make_event_stub()
    event.fire_event({"hello": "world"}, "salt/test/tag")

    _tag, data = salt.utils.event.SaltEvent.unpack(sent[0])
    assert "traceparent" not in data


def test_event_round_trip_creates_child_span(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    event, sent = _make_event_stub()
    with tracing.start_span("publisher") as pub_span:
        pub_trace_id = pub_span.get_span_context().trace_id
        event.fire_event({"x": 1}, "salt/test/round_trip")

    _tag, data = salt.utils.event.SaltEvent.unpack(sent[0])
    ctx = tracing.extract(data)
    assert ctx is not None
    with tracing.start_span("consumer", context=ctx) as cons_span:
        assert cons_span.get_span_context().trace_id == pub_trace_id
