"""
Unit tests for salt.utils.tracing — the OpenTelemetry wrapper.
"""

import multiprocessing
import os

import pytest

import salt.utils.tracing as tracing


@pytest.fixture(autouse=True)
def _reset_tracing_state(monkeypatch):
    """Reset module-level state between tests so they are isolated."""
    tracing.shutdown()
    monkeypatch.setattr(tracing, "_cached_opts", None)
    yield
    tracing.shutdown()


@pytest.fixture
def in_memory_exporter(monkeypatch):
    """Replace the exporter builder so all spans land in an InMemorySpanExporter."""
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    monkeypatch.setattr(tracing, "_build_exporter", lambda _opts: exporter)
    return exporter


def _flush():
    """Force the BatchSpanProcessor to flush pending spans."""
    if tracing._provider is not None:
        tracing._provider.force_flush()


def test_disabled_is_noop():
    """When tracing is disabled, every API call short-circuits."""
    assert tracing.is_enabled() is False

    with tracing.start_span("foo") as span:
        assert span is tracing._NOOP_SPAN
        span.set_attribute("k", "v")  # must not raise
        carrier = {}
        tracing.inject(carrier)
        assert carrier == {}
    assert tracing.extract({"traceparent": "00-x-x-01"}) is None


def test_configure_disabled_remains_noop():
    tracing.configure({"tracing": {"enabled": False}})
    assert tracing.is_enabled() is False

    with tracing.start_span("foo") as span:
        assert span is tracing._NOOP_SPAN


def test_configure_enabled_starts_real_span(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    assert tracing.is_enabled() is True

    with tracing.start_span("test") as span:
        assert span is not tracing._NOOP_SPAN
        assert span.is_recording

    _flush()
    spans = in_memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test"


def test_inject_skipped_when_no_recording_span(in_memory_exporter):
    """inject() must be a no-op when no recording span is active."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    carrier = {}
    tracing.inject(carrier)
    assert "traceparent" not in carrier


def test_inject_extract_round_trip(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    carrier = {}
    with tracing.start_span("outer") as outer:
        outer_trace_id = outer.get_span_context().trace_id
        tracing.inject(carrier)
        assert "traceparent" in carrier

    ctx = tracing.extract(carrier)
    assert ctx is not None

    with tracing.start_span("child", context=ctx) as child:
        assert child.get_span_context().trace_id == outer_trace_id


def test_sampler_parent_based_default(in_memory_exporter):
    tracing.configure({"tracing": {"enabled": True, "exporter": "console"}})
    sampler = tracing._provider.sampler
    assert "ParentBased" in type(sampler).__name__


def test_sampler_always_off(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_off"}}
    )
    with tracing.start_span("dropped"):
        pass
    _flush()
    assert in_memory_exporter.get_finished_spans() == ()


def test_service_name_auto_master():
    tracing.configure({"__role": "master", "tracing": {"enabled": False}})
    assert tracing._cached_opts["service_name"] == "salt-master"


def test_service_name_auto_minion():
    tracing.configure({"__role": "minion", "id": "m1", "tracing": {"enabled": False}})
    assert tracing._cached_opts["service_name"] == "salt-minion-m1"


def test_service_name_override():
    tracing.configure(
        {
            "__role": "master",
            "tracing": {"enabled": False, "service_name": "custom-svc"},
        }
    )
    assert tracing._cached_opts["service_name"] == "custom-svc"


def _child_emit(queue, opts):
    """Child entry point for the fork test."""
    import opentelemetry.sdk.trace as sdk_trace
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    import salt.utils.tracing as t

    exporter = InMemorySpanExporter()

    # Build a provider directly inside the child to avoid depending on
    # the parent's BatchSpanProcessor configuration surviving the fork.
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    setattr(t, "_provider", provider)
    setattr(t, "_tracer", provider.get_tracer("salt"))
    setattr(t, "_last_pid", os.getpid())
    setattr(t, "_cached_opts", (opts or {}).get("tracing") or {})

    with t.start_span("child"):
        pass
    spans = exporter.get_finished_spans()
    queue.put([s.name for s in spans])


def test_fork_isolation():
    """The provider rebuilds in a forked child; the child can emit spans."""
    if not hasattr(os, "fork"):
        pytest.skip("fork not available on this platform")
    ctx = multiprocessing.get_context("fork")
    queue = ctx.Queue()
    opts = {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    proc = ctx.Process(target=_child_emit, args=(queue, opts))
    proc.start()
    proc.join(timeout=15)
    assert proc.exitcode == 0
    names = queue.get(timeout=5)
    assert names == ["child"]


def test_configure_idempotent(in_memory_exporter):
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    first = tracing._provider
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    # Configure does not rebuild when PID + opts are still valid.
    assert tracing._provider is first
