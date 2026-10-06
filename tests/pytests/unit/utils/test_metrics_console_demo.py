"""
End-to-end demonstration of the OpenTelemetry metrics data salt emits.

Exercises a small chain — counter increments, histogram records, an
observable gauge — exports via ``ConsoleMetricExporter`` into a captured
buffer, and asserts both on the structure of the OTel data and on the
literal shape of the rendered JSON.

Run with ``pytest -s`` to see the captured metrics printed.
"""

import io
import json

import pytest
from opentelemetry.metrics import Observation
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

import salt.utils.metrics as metrics


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    metrics.shutdown()
    monkeypatch.setattr(metrics, "_cached_opts", None)
    yield
    metrics.shutdown()


@pytest.fixture
def captured_console(monkeypatch):
    """Build a provider whose ``ConsoleMetricExporter`` writes to a buffer."""
    buf = io.StringIO()
    exporter = ConsoleMetricExporter(out=buf)

    def _build_readers(_opts):
        # Short interval so test exit force-flush fires quickly.
        return [
            PeriodicExportingMetricReader(exporter, export_interval_millis=10_000_000)
        ]

    monkeypatch.setattr(metrics, "_build_readers", _build_readers)
    return buf, exporter


def test_full_pipeline_emits_expected_metric_data(captured_console, capsys):
    """
    Drive a small chain that mimics what a real ``salt '*' test.ping`` would
    emit: a publish counter on the master, a duration histogram on the
    client side, and an observable gauge for "connected minions".
    """
    buf, exporter = captured_console
    metrics.configure(
        {
            "metrics": {"enabled": True, "exporter": "console"},
            "__role": "master",
        }
    )

    # 1. Counter — increment per publish.
    jobs_published = metrics.counter(
        "salt.jobs.published",
        description="Jobs published from the master to minions.",
    )
    for _ in range(3):
        jobs_published.add(1, attributes={"fun": "test.ping"})
    jobs_published.add(1, attributes={"fun": "test.echo"})

    # 2. Histogram — record per-job duration.
    job_duration = metrics.histogram(
        "salt.job.duration",
        description="CLI-to-master-return wall-clock.",
        unit="ms",
    )
    for ms in (12.0, 45.0, 130.0, 600.0):
        job_duration.record(ms, attributes={"fun": "test.ping"})

    # 3. Observable gauge — connected minion count.
    state = {"connected": 5}
    metrics.observable_gauge(
        "salt.master.connected_minions.count",
        lambda _options: (Observation(state["connected"]),),
        description="Number of minions the master currently considers connected.",
    )

    # Flush via shutdown so all instruments land in the captured buffer.
    metrics.shutdown()

    rendered = buf.getvalue()
    with capsys.disabled():
        print("\n\n=== Captured OTel metric data ===")
        print(rendered)
        print("=== End ===\n")

    # ConsoleMetricExporter emits one JSON document per export.  Collect them.
    decoder = json.JSONDecoder()
    documents = []
    text = rendered.strip()
    while text:
        obj, idx = decoder.raw_decode(text)
        documents.append(obj)
        text = text[idx:].lstrip()

    # Flatten all metrics from every document.
    flat = []
    for doc in documents:
        for rm in doc.get("resource_metrics", []):
            for sm in rm.get("scope_metrics", []):
                for metric in sm.get("metrics", []):
                    name = metric["name"]
                    for dp in metric["data"]["data_points"]:
                        attrs = dp.get("attributes") or {}
                        if "value" in dp:
                            flat.append((name, attrs, dp["value"]))
                        elif "sum" in dp:
                            flat.append((name, attrs, dp["sum"], dp.get("count")))

    # 1. Counter assertions.
    counter_rows = {
        tuple(sorted(a.items())): v
        for n, a, v in (r for r in flat if len(r) == 3)
        if n == "salt.jobs.published"
    }
    assert counter_rows.get((("fun", "test.ping"),)) == 3, counter_rows
    assert counter_rows.get((("fun", "test.echo"),)) == 1, counter_rows

    # 2. Histogram assertions: sum of recorded values matches.
    hist_rows = [r for r in flat if r[0] == "salt.job.duration"]
    assert hist_rows, "expected salt.job.duration to be emitted"
    _name, _attrs, hist_sum, hist_count = hist_rows[0]
    assert hist_sum == 12.0 + 45.0 + 130.0 + 600.0
    assert hist_count == 4

    # 3. Observable gauge assertion.
    gauge_rows = [r for r in flat if r[0] == "salt.master.connected_minions.count"]
    assert gauge_rows, "expected connected_minions gauge to fire"
    assert gauge_rows[0][2] == 5

    # Resource carries our auto-derived service.name.
    found_master = any(
        rm["resource"]["attributes"].get("service.name") == "salt-master"
        for doc in documents
        for rm in doc.get("resource_metrics", [])
    )
    assert found_master
