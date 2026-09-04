"""
Verify trace context propagates through the channel layer:
* injection happens inside the AES envelope, not on the outer wrapper.
* the receive side can extract the context and link a child span.
"""

import pytest

import salt.channel.client
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


class _FakeCrypticle:
    """Capture the cleartext load handed to dumps() for assertion."""

    captured: dict = {}

    def dumps(self, load):
        type(self).captured = dict(load)
        return b"<encrypted>"


class _FakeAuth:
    def __init__(self):
        self.session_crypticle = _FakeCrypticle()
        self.authenticated = True

    def gen_token(self, _salt):
        return b"tok"


def _make_channel():
    channel = salt.channel.client.AsyncReqChannel.__new__(
        salt.channel.client.AsyncReqChannel
    )
    channel.auth = _FakeAuth()
    channel.opts = {
        "id": "minion-x",
        "encryption_algorithm": "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA1",
    }
    return channel


def test_package_load_injects_into_encrypted_load(in_memory_exporter):
    """traceparent must be inside the load before AES, not on the outer envelope."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    channel = _make_channel()
    with tracing.start_span("outer"):
        envelope = channel._package_load({"cmd": "test.ping"})

    # Outer envelope must NOT carry the trace headers.
    assert "traceparent" not in envelope
    assert "_trace" not in envelope

    # The crypticle saw the cleartext load WITH traceparent inside.
    captured: dict = _FakeCrypticle.captured
    assert captured, "expected the crypticle to capture a load dict"
    assert "traceparent" in captured
    # Salt's auth fields are also present.
    assert captured["cmd"] == "test.ping"
    assert captured["id"] == "minion-x"


def test_package_load_skipped_when_no_span(in_memory_exporter):
    """No active span ⇒ no trace headers in the load (avoid bloat)."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    channel = _make_channel()
    channel._package_load({"cmd": "test.ping"})
    captured: dict = _FakeCrypticle.captured
    assert "traceparent" not in captured


def test_extract_from_inner_load_links_child_span(in_memory_exporter):
    """The receive-side flow: extract from cleartext load gives a usable context."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    channel = _make_channel()
    with tracing.start_span("client") as client_span:
        client_trace_id = client_span.get_span_context().trace_id
        channel._package_load({"cmd": "test.ping"})
    cleartext_load = _FakeCrypticle.captured

    # Simulate the server side decoding & extracting.
    ctx = tracing.extract(cleartext_load)
    assert ctx is not None
    with tracing.start_span("server", context=ctx) as server_span:
        assert server_span.get_span_context().trace_id == client_trace_id
