"""
Unit tests for salt.utils.metrics — the OpenTelemetry metrics wrapper.
"""

import socket
import subprocess
import sys
import textwrap
import time

import pytest

import salt.utils.metrics as metrics


@pytest.fixture(autouse=True)
def _reset_metrics_state(monkeypatch):
    """Reset module-level state between tests so they are isolated."""
    metrics.shutdown()
    monkeypatch.setattr(metrics, "_cached_opts", None)
    yield
    metrics.shutdown()


@pytest.fixture
def in_memory_reader(monkeypatch):
    """Replace the reader builder so all metrics flow into an InMemoryMetricReader."""
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    monkeypatch.setattr(metrics, "_build_readers", lambda _opts: [reader])
    return reader


def _collect_metrics(reader):
    """Return a flat list of (name, attributes, value-or-sum) tuples."""
    out = []
    data = reader.get_metrics_data()
    if data is None:
        return out
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                for dp in metric.data.data_points:
                    attrs = dict(dp.attributes) if dp.attributes else {}
                    value = getattr(dp, "value", None)
                    if value is None:
                        value = getattr(dp, "sum", None)
                    out.append((metric.name, attrs, value))
    return out


def test_disabled_is_noop():
    """When metrics are disabled, every API call short-circuits."""
    assert metrics.is_enabled() is False
    c = metrics.counter("foo")
    assert c is metrics._NOOP_COUNTER
    c.add(1, attributes={"a": "b"})
    h = metrics.histogram("foo")
    assert h is metrics._NOOP_HISTOGRAM
    h.record(123, attributes={"a": "b"})
    g = metrics.observable_gauge("foo", lambda _options: [])
    assert g is metrics._NOOP_OBSERVABLE


def test_configure_disabled_remains_noop():
    metrics.configure({"metrics": {"enabled": False}})
    assert metrics.is_enabled() is False
    assert metrics.counter("foo") is metrics._NOOP_COUNTER


def test_counter_records(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    assert metrics.is_enabled() is True
    c = metrics.counter("salt.test.counter")
    c.add(2, attributes={"fun": "test.ping"})
    c.add(3, attributes={"fun": "test.ping"})
    c.add(1, attributes={"fun": "test.echo"})

    rows = _collect_metrics(in_memory_reader)
    by_attr = {
        tuple(sorted(a.items())): v for n, a, v in rows if n == "salt.test.counter"
    }
    assert by_attr[(("fun", "test.ping"),)] == 5
    assert by_attr[(("fun", "test.echo"),)] == 1


def test_histogram_records(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    h = metrics.histogram("salt.test.duration", unit="ms")
    h.record(10.0, attributes={"fun": "test.ping"})
    h.record(20.0, attributes={"fun": "test.ping"})

    rows = _collect_metrics(in_memory_reader)
    durations = [v for n, _, v in rows if n == "salt.test.duration"]
    # InMemoryMetricReader emits the histogram sum here.
    assert durations and durations[0] == 30.0


def test_observable_gauge_invoked(in_memory_reader):
    from opentelemetry.metrics import Observation

    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )

    state = {"value": 42}

    def _cb(_options):
        return (Observation(state["value"], {"queue": "default"}),)

    metrics.observable_gauge("salt.test.gauge", _cb)
    rows = _collect_metrics(in_memory_reader)
    gauge_rows = [r for r in rows if r[0] == "salt.test.gauge"]
    assert gauge_rows, "expected gauge to have been observed"
    _, attrs, value = gauge_rows[0]
    assert attrs == {"queue": "default"}
    assert value == 42


def test_histogram_view_uses_configured_boundaries(in_memory_reader):
    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "console",
                "histogram_boundaries": {"salt.test.bucketed": [10.0, 100.0, 1000.0]},
            },
            "__role": "master",
        }
    )
    h = metrics.histogram("salt.test.bucketed", unit="ms")
    h.record(5)
    h.record(50)
    h.record(500)
    h.record(5000)
    data = in_memory_reader.get_metrics_data()
    boundaries = None
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == "salt.test.bucketed":
                    for dp in m.data.data_points:
                        boundaries = list(dp.explicit_bounds)
    assert boundaries == [10.0, 100.0, 1000.0]


def test_service_name_auto_master():
    metrics.configure({"__role": "master", "metrics": {"enabled": False}})
    assert metrics._cached_opts["service_name"] == "salt-master"


def test_service_name_auto_minion():
    metrics.configure({"__role": "minion", "id": "m1", "metrics": {"enabled": False}})
    assert metrics._cached_opts["service_name"] == "salt-minion-m1"


def test_service_name_override():
    metrics.configure(
        {
            "__role": "master",
            "metrics": {"enabled": False, "service_name": "custom-svc"},
        }
    )
    assert metrics._cached_opts["service_name"] == "custom-svc"


def test_otlp_grpc_missing_is_graceful(monkeypatch, caplog):
    """
    Picking ``otlp-grpc`` without the optional grpc package installed must
    not raise; the build call returns an empty reader list and a clear
    error is logged.
    """
    import logging

    real_import = __import__

    def _no_grpc_import(name, *args, **kwargs):
        if name.startswith("opentelemetry.exporter.otlp.proto.grpc"):
            raise ImportError("simulated: no grpcio in environment")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _no_grpc_import)
    with caplog.at_level(logging.ERROR, logger="salt.utils.metrics"):
        readers = metrics._build_readers({"enabled": True, "exporter": "otlp-grpc"})
    assert readers == []
    assert any(
        "opentelemetry-exporter-otlp-proto-grpc is not installed" in rec.message
        for rec in caplog.records
    )


def test_prometheus_exporter_binds_listener():
    """End-to-end check: configure with ``exporter: prometheus`` and
    ``GET /metrics`` from the bound port returns Prometheus text exposition."""
    import urllib.request

    # Pick a free local port to avoid collisions.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "prometheus",
                "prometheus": {"host": "127.0.0.1", "port": port},
            },
            "__role": "master",
        }
    )
    # Increment a counter so /metrics has something to show.
    metrics.counter("salt.test.prom_counter").add(7, attributes={"fun": "test.ping"})

    # Read /metrics.  Retry briefly to let the http_server thread bind.
    body = ""
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/metrics", timeout=2
            ) as resp:
                body = resp.read().decode()
                break
        except Exception:  # pylint: disable=broad-except
            time.sleep(0.2)
    assert "salt_test_prom_counter" in body, body[:500]
    assert 'fun="test.ping"' in body, body[:500]


def test_module_works_when_opentelemetry_missing():
    """
    Reload ``salt.utils.metrics`` in a fresh subprocess with
    ``opentelemetry`` blocked at import time and assert that every public
    API still works as a complete no-op.  Subprocess isolation prevents
    the import-block from leaking into other tests.
    """
    script = textwrap.dedent(
        """
        import sys


        class _BlockOtel:
            def find_spec(self, name, path=None, target=None):
                if name == 'opentelemetry' or name.startswith('opentelemetry.'):
                    raise ImportError('simulated: opentelemetry not installed')
                return None


        sys.meta_path.insert(0, _BlockOtel())
        for cached in [k for k in sys.modules if k.startswith('opentelemetry')]:
            del sys.modules[cached]

        import salt.utils.metrics as m

        assert m._OTEL_AVAILABLE is False, 'expected otel to look absent'
        m.configure({'metrics': {'enabled': True}, '__role': 'master'})
        assert m.is_enabled() is False, 'enabled must stay false without otel'
        c = m.counter('foo')
        assert c is m._NOOP_COUNTER
        c.add(1, attributes={'fun': 'x'})
        h = m.histogram('foo')
        assert h is m._NOOP_HISTOGRAM
        h.record(10)
        g = m.observable_gauge('foo', lambda options: [])
        assert g is m._NOOP_OBSERVABLE
        m.shutdown()
        print('OK')
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"subprocess failed (rc={result.returncode}):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "OK" in result.stdout


def test_configure_idempotent(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    first = metrics._provider
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    # Configure does not rebuild when PID + opts are still valid.
    assert metrics._provider is first
