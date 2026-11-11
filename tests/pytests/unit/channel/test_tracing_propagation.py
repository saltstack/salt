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
    monkeypatch.setattr(tracing, "_OTEL_AVAILABLE", None)
    monkeypatch.setattr(tracing, "_otel", None)
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


def _flush():
    if tracing._provider is not None:
        tracing._provider.force_flush()


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


# ---------------------------------------------------------------------------
# ReqServerChannel.handle_message span attributes --- Bug B regression
# ---------------------------------------------------------------------------


async def _run_handle_message_capturing_spans(load_cmd, extra_load, in_memory_exporter):
    """Drive ReqServerChannel.handle_message far enough to open the
    ``salt.req.recv.<cmd>`` span, then flush and return the captured
    span attributes."""
    import salt.channel.server as server_mod
    from tests.support.mock import AsyncMock, MagicMock, patch

    opts = {
        "id": "test-master",
        "minimum_auth_version": 0,
        "request_server_ttl": 0,
    }
    # Bypass __init__ (which touches cache/pki) --- handle_message only
    # reads ``self.opts`` + patched methods.
    req = server_mod.ReqServerChannel.__new__(server_mod.ReqServerChannel)
    req.opts = opts
    req.transport = None

    load = {"cmd": load_cmd}
    load.update(extra_load)
    payload = {"version": 0, "enc": "clear", "load": load, "id": "test-master-id"}

    with patch(
        "salt.channel.server.ReqServerChannel._decode_payload",
        MagicMock(return_value=payload),
    ), patch(
        "salt.channel.server._cluster_is_ready", MagicMock(return_value=True)
    ), patch(
        "salt.channel.server.ReqServerChannel.payload_handler",
        AsyncMock(return_value=(None, {"fun": "send_clear"})),
        create=True,
    ):
        await req.handle_message(payload)

    _flush()
    return in_memory_exporter.get_finished_spans()


async def test_handle_message_return_span_adds_jid_and_fun(in_memory_exporter):
    """``_return`` spans must surface ``salt.jid`` + ``salt.fun`` so a
    return span is joinable to the originating publish without a trace
    walk."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    spans = await _run_handle_message_capturing_spans(
        "_return",
        {"jid": "20261101000000000003", "fun": "test.ping", "id": "east-minion-1"},
        in_memory_exporter,
    )
    assert spans, "expected at least one span to be exported"
    recv_spans = [s for s in spans if s.name == "salt.req.recv._return"]
    assert recv_spans, [s.name for s in spans]
    attrs = dict(recv_spans[0].attributes)
    assert attrs.get("salt.jid") == "20261101000000000003"
    assert attrs.get("salt.fun") == "test.ping"
    assert attrs.get("salt.req.cmd") == "_return"


async def test_handle_message_publish_span_adds_jid_and_tgt(in_memory_exporter):
    """``publish`` spans have an empty ``salt.req.minion_id`` (the request
    is master-directed) --- surface ``salt.jid`` + ``salt.pub.tgt`` so the
    span is joinable without a trace walk."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    spans = await _run_handle_message_capturing_spans(
        "publish",
        {"jid": "20261101000000000004", "tgt": "*", "fun": "test.ping"},
        in_memory_exporter,
    )
    recv_spans = [s for s in spans if s.name == "salt.req.recv.publish"]
    assert recv_spans, [s.name for s in spans]
    attrs = dict(recv_spans[0].attributes)
    assert attrs.get("salt.jid") == "20261101000000000004"
    assert attrs.get("salt.pub.tgt") == "*"


async def test_handle_message_other_cmd_does_not_add_jid(in_memory_exporter):
    """Non-``_return``/non-``publish`` commands must not grow ``salt.jid``
    attribute by surprise."""
    tracing.configure(
        {"tracing": {"enabled": True, "exporter": "console", "sampler": "always_on"}}
    )
    spans = await _run_handle_message_capturing_spans(
        "_pillar", {"id": "foo"}, in_memory_exporter
    )
    recv_spans = [s for s in spans if s.name == "salt.req.recv._pillar"]
    assert recv_spans, [s.name for s in spans]
    attrs = dict(recv_spans[0].attributes)
    assert "salt.jid" not in attrs
    assert "salt.pub.tgt" not in attrs
