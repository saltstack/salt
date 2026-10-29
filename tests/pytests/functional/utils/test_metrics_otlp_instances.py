"""
End-to-end check of the OTLP series identity for forked master processes.

Several forked processes (standing in for the master and its MWorkers) record
the same counter and export it over OTLP/HTTP to a small receiver that plays
the collector.  Every process must show up as its own series, and the series
must add up to the total, instead of overwriting each other (#70248).
"""

import gzip
import http.server
import multiprocessing
import socket
import threading

import pytest

import salt.utils.metrics as metrics

pytest.importorskip("opentelemetry.sdk.metrics")
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.metric_exporter")
metrics_service_pb2 = pytest.importorskip(
    "opentelemetry.proto.collector.metrics.v1.metrics_service_pb2"
)

pytestmark = [
    pytest.mark.skipif(
        "fork" not in multiprocessing.get_all_start_methods(), reason="needs fork"
    ),
]

COUNTER = "salt.test.jobs"
ROUNDS = 3
PER_ROUND = 2


class _Receiver:
    """Collect every OTLP/HTTP metrics export sent to it."""

    def __init__(self):
        self.requests = []
        self._lock = threading.Lock()
        receiver = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # pylint: disable=invalid-name
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                request = metrics_service_pb2.ExportMetricsServiceRequest()
                request.ParseFromString(body)
                with receiver._lock:  # pylint: disable=protected-access
                    receiver.requests.append(request)
                payload = metrics_service_pb2.ExportMetricsServiceResponse()
                data = payload.SerializeToString()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # pylint: disable=arguments-differ
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/v1/metrics"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def series(self):
        """
        Return ``{service.instance.id: [cumulative value, ...]}`` in the order
        the values were received.
        """
        out = {}
        with self._lock:
            requests = list(self.requests)
        for request in requests:
            for resource_metrics in request.resource_metrics:
                instance = {
                    kv.key: kv.value.string_value
                    for kv in resource_metrics.resource.attributes
                }.get("service.instance.id")
                for scope in resource_metrics.scope_metrics:
                    for metric in scope.metrics:
                        if metric.name != COUNTER:
                            continue
                        for point in metric.sum.data_points:
                            out.setdefault(instance, []).append(point.as_int)
        return out


def _record(endpoint, name):
    """Run in a forked child: act as one named master process."""
    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "otlp-http",
                "endpoint": endpoint,
                "export_interval_seconds": 3600,
            },
            "__role": "master",
            "__metrics_instance": {"id": name},
        }
    )
    counter = metrics.counter(COUNTER)
    for _ in range(ROUNDS):
        for _ in range(PER_ROUND):
            counter.add(1)
        metrics._provider.force_flush()  # pylint: disable=protected-access
    metrics.shutdown()


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    # The receiver is local; never send it through a proxy.  This also keeps
    # ``requests`` from asking macOS for proxy settings in a forked child,
    # which aborts the process.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    metrics.shutdown()
    yield
    metrics.shutdown()


def test_forked_processes_export_separate_series():
    names = ["Master", "MWorker-0", "MWorker-1", "MWorker-2"]
    ctx = multiprocessing.get_context("fork")
    with _Receiver() as receiver:
        procs = [
            ctx.Process(target=_record, args=(receiver.endpoint, n)) for n in names
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            proc.join(timeout=60)
            assert proc.exitcode == 0
        series = receiver.series()

    host = socket.gethostname()
    assert sorted(series) == sorted(f"{host}/{n}" for n in names)
    for instance, values in series.items():
        # Each process sends a cumulative value that only grows.
        assert values == sorted(values), (instance, values)
        assert values[-1] == ROUNDS * PER_ROUND, (instance, values)
    # The per-process series add up to the real total.
    assert sum(v[-1] for v in series.values()) == len(names) * ROUNDS * PER_ROUND
