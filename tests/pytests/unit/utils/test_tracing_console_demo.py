"""
End-to-end demonstration of the OpenTelemetry data salt emits.

Every other tracing test uses an ``InMemorySpanExporter`` and asserts on
the SDK objects directly.  This test instead drives the full
``CLI → channel(req) → master-server → channel(pub) → minion-exec →
channel(return) → master-server`` chain through ``inject`` / ``extract``,
captures the rendered JSON from a ``ConsoleSpanExporter``, and asserts
both the structure of the resulting span tree *and* the literal shape of
the human-readable output.

Run with ``pytest -s`` to see the captured spans printed.
"""

import io
import json

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

import salt.utils.tracing as tracing


@pytest.fixture(autouse=True)
def _reset_tracing(monkeypatch):
    tracing.shutdown()
    monkeypatch.setattr(tracing, "_cached_opts", None)
    yield
    tracing.shutdown()


@pytest.fixture
def captured_console(monkeypatch):
    """
    Replace the provider with one whose ConsoleSpanExporter writes to a
    captured ``StringIO``.  ``SimpleSpanProcessor`` flushes synchronously
    so we do not need to wait on the batch processor's timer.
    """
    buf = io.StringIO()
    exporter = ConsoleSpanExporter(out=buf)

    def _build_provider():
        from opentelemetry.sdk.resources import Resource

        provider = TracerProvider(
            resource=Resource.create(
                {"service.name": tracing._cached_opts.get("service_name") or "salt"}
            )
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        # Stash on the tracing module just like the real ``_build_provider``.
        monkeypatch.setattr(tracing, "_provider", provider, raising=False)
        monkeypatch.setattr(
            tracing,
            "_tracer",
            provider.get_tracer(tracing._INSTRUMENTATION_NAME),
            raising=False,
        )

    monkeypatch.setattr(tracing, "_build_provider", _build_provider)
    return buf


def _parse_console_spans(text):
    """ConsoleSpanExporter emits one JSON object per finished span."""
    decoder = json.JSONDecoder()
    spans = []
    s = text.strip()
    while s:
        obj, idx = decoder.raw_decode(s)
        spans.append(obj)
        s = s[idx:].lstrip()
    return spans


def test_full_pipeline_emits_expected_otel_data(captured_console, capsys):
    """
    Exercise the same code path a real ``salt '*' test.ping`` would take
    and assert on the resulting OTel data.  The captured ConsoleSpanExporter
    output is printed (visible with ``pytest -s``) as a canonical reference.
    """
    tracing.configure(
        {
            "tracing": {
                "enabled": True,
                "exporter": "console",
                "sampler": "always_on",
            },
            "__role": "master",
        }
    )

    jid = "20260516000000000000"

    # ── 1. CLI root span ────────────────────────────────────────────────
    with tracing.start_span(
        "salt.cli.test.ping",
        kind=tracing.SpanKind.CLIENT,
        attributes={"salt.cli.tgt": "*", "salt.cli.fun": "test.ping"},
    ):

        # ── 2. CLI → master: req-channel inject into the inner load ─────
        req_load = {"cmd": "publish", "fun": "test.ping", "tgt": "*"}
        tracing.inject(req_load)
        assert "traceparent" in req_load, "channel-layer inject failed"

        # ── 3. Master receive: extract → server span around dispatch ────
        master_ctx = tracing.extract(req_load)
        with tracing.start_span(
            "salt.req.recv.publish",
            kind=tracing.SpanKind.SERVER,
            attributes={"salt.req.cmd": "publish"},
            context=master_ctx,
        ):

            # ── 4. Master publish: inject into the pub load ─────────────
            pub_load = {"jid": jid, "fun": "test.ping", "tgt": "*"}
            tracing.inject(pub_load)
            with tracing.start_span(
                "salt.pub.send",
                attributes={"salt.pub.jid": jid, "salt.pub.fun": "test.ping"},
            ):
                pass

            # ── 5. Minion receive: extract → server span on the minion ──
            minion_ctx = tracing.extract(pub_load)
            with tracing.start_span(
                "salt.minion.recv.test.ping",
                kind=tracing.SpanKind.SERVER,
                attributes={"salt.fun": "test.ping", "salt.jid": jid},
                context=minion_ctx,
            ):

                # ── 6. Minion exec ──────────────────────────────────────
                with tracing.start_span(
                    "salt.minion.exec.test.ping",
                    attributes={"salt.fun": "test.ping", "salt.jid": jid},
                ):
                    pass

                # ── 7. Minion → master return: inject into return load ──
                ret_load = {"cmd": "_return", "jid": jid, "return": True}
                tracing.inject(ret_load)

            # ── 8. Master receive return ────────────────────────────────
            ret_ctx = tracing.extract(ret_load)
            with tracing.start_span(
                "salt.req.recv._return",
                kind=tracing.SpanKind.SERVER,
                context=ret_ctx,
            ):
                pass

    # SimpleSpanProcessor flushes on span end; no force_flush needed.
    spans = _parse_console_spans(captured_console.getvalue())

    # Print the captured output for human inspection (visible with -s).
    with capsys.disabled():
        print("\n\n=== Captured OTel span data ===")
        print(captured_console.getvalue())
        print("=== End ===\n")

    # ── Assertions on span tree shape ──────────────────────────────────
    span_names = [s["name"] for s in spans]
    # SimpleSpanProcessor exports each span on ``end()``, and a ``with``
    # block ends the innermost span first.
    assert sorted(span_names) == sorted(
        [
            "salt.pub.send",
            "salt.minion.exec.test.ping",
            "salt.minion.recv.test.ping",
            "salt.req.recv._return",
            "salt.req.recv.publish",
            "salt.cli.test.ping",
        ]
    ), span_names

    # Every span shares one trace_id.
    trace_ids = {s["context"]["trace_id"] for s in spans}
    assert len(trace_ids) == 1, f"expected single trace, got {trace_ids}"

    by_name = {s["name"]: s for s in spans}

    # The CLI root has no parent.
    assert by_name["salt.cli.test.ping"]["parent_id"] is None

    cli_id = by_name["salt.cli.test.ping"]["context"]["span_id"]
    req_id = by_name["salt.req.recv.publish"]["context"]["span_id"]
    mrx_id = by_name["salt.minion.recv.test.ping"]["context"]["span_id"]

    # Parent chain.
    #
    # ``PubServerChannel.publish`` injects the trace context into the load
    # *before* opening the ``salt.pub.send`` span, so on the minion side
    # ``extract`` returns the master's request-server span — not
    # ``salt.pub.send``.  ``salt.pub.send`` ends up as a sibling that
    # measures the local publish step.  The return injection happens
    # inside ``salt.minion.recv`` (after ``salt.minion.exec`` has ended),
    # so the master's return-receive span parents under
    # ``salt.minion.recv``.
    assert by_name["salt.req.recv.publish"]["parent_id"] == cli_id
    assert by_name["salt.pub.send"]["parent_id"] == req_id
    assert by_name["salt.minion.recv.test.ping"]["parent_id"] == req_id
    assert by_name["salt.minion.exec.test.ping"]["parent_id"] == mrx_id
    assert by_name["salt.req.recv._return"]["parent_id"] == mrx_id

    # Attributes carried through.
    assert by_name["salt.cli.test.ping"]["attributes"]["salt.cli.tgt"] == "*"
    assert by_name["salt.cli.test.ping"]["attributes"]["salt.cli.fun"] == "test.ping"
    assert by_name["salt.minion.exec.test.ping"]["attributes"]["salt.jid"] == jid

    # Span kinds came through as the OTel SDK names them.
    assert by_name["salt.cli.test.ping"]["kind"] == "SpanKind.CLIENT"
    assert by_name["salt.req.recv.publish"]["kind"] == "SpanKind.SERVER"
    assert by_name["salt.minion.recv.test.ping"]["kind"] == "SpanKind.SERVER"
    assert by_name["salt.minion.exec.test.ping"]["kind"] == "SpanKind.INTERNAL"

    # Resource carries our service.name.
    assert (
        by_name["salt.cli.test.ping"]["resource"]["attributes"]["service.name"]
        == "salt-master"
    )
