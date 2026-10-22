"""
End-to-end check of the real OTLP/HTTP exporters used by ``salt.utils.tracing``
and ``salt.utils.metrics``.

A small HTTP server plays the collector.  The test decodes what it receives, so
a broken exporter fails here instead of passing silently as it would with the
in-memory exporters used by the unit tests.  It also checks that exports honour
``HTTP_PROXY``: opentelemetry 1.45.0 switched the exporters to a urllib3
transport that ignores the proxy environment unless a ``requests.Session`` is
supplied.
"""

import gzip
import http.server
import threading

import pytest

import salt.utils.metrics as metrics
import salt.utils.tracing as tracing

pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry.sdk.metrics")
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.metric_exporter")
trace_service_pb2 = pytest.importorskip(
    "opentelemetry.proto.collector.trace.v1.trace_service_pb2"
)
metrics_service_pb2 = pytest.importorskip(
    "opentelemetry.proto.collector.metrics.v1.metrics_service_pb2"
)

SPAN_NAME = "salt.test.span"
COUNTER = "salt.test.counter"
# Never resolvable, so an export only arrives if it went through the proxy.
COLLECTOR = "http://otlp-collector.invalid:4318"


class _Receiver:
    """
    Collector and forward proxy in one.

    A client talking to a proxy sends the absolute URL in the request line, a
    client talking to the collector directly sends only the path, so the
    recorded target tells the two apart.
    """

    def __init__(self):
        self.exports = []  # (request target, decoded protobuf request)
        self._lock = threading.Lock()
        receiver = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # pylint: disable=invalid-name
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                if self.path.endswith("/v1/traces"):
                    request = trace_service_pb2.ExportTraceServiceRequest()
                    response = trace_service_pb2.ExportTraceServiceResponse()
                else:
                    request = metrics_service_pb2.ExportMetricsServiceRequest()
                    response = metrics_service_pb2.ExportMetricsServiceResponse()
                request.ParseFromString(body)
                with receiver._lock:  # pylint: disable=protected-access
                    receiver.exports.append((self.path, request))
                data = response.SerializeToString()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # pylint: disable=arguments-differ
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.address = f"127.0.0.1:{self.server.server_port}"
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def received(self):
        with self._lock:
            return list(self.exports)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    for name in ("NO_PROXY", "no_proxy", "HTTPS_PROXY", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    tracing.shutdown()
    metrics.shutdown()
    yield
    tracing.shutdown()
    metrics.shutdown()


def _emit_span(endpoint):
    tracing.configure(
        {
            "tracing": {
                "enabled": True,
                "exporter": "otlp-http",
                "endpoint": f"{endpoint}/v1/traces",
                "sampler": "always_on",
            }
        }
    )
    with tracing.start_span(SPAN_NAME):
        pass
    tracing._provider.force_flush()  # pylint: disable=protected-access


def _emit_metric(endpoint):
    metrics.configure(
        {
            "metrics": {
                "enabled": True,
                "exporter": "otlp-http",
                "endpoint": f"{endpoint}/v1/metrics",
                "export_interval_seconds": 3600,
            },
            "__role": "master",
        }
    )
    metrics.counter(COUNTER).add(3)
    metrics._provider.force_flush()  # pylint: disable=protected-access


def _span_names(request):
    return [
        span.name
        for resource_spans in request.resource_spans
        for scope_spans in resource_spans.scope_spans
        for span in scope_spans.spans
    ]


def _counter_values(request):
    return [
        point.as_int
        for resource_metrics in request.resource_metrics
        for scope_metrics in resource_metrics.scope_metrics
        for metric in scope_metrics.metrics
        if metric.name == COUNTER
        for point in metric.sum.data_points
    ]


def test_spans_are_exported_to_collector():
    with _Receiver() as receiver:
        _emit_span(f"http://{receiver.address}")
        exports = receiver.received()

    assert [path for path, _ in exports] == ["/v1/traces"]
    assert _span_names(exports[0][1]) == [SPAN_NAME]


def test_metrics_are_exported_to_collector():
    with _Receiver() as receiver:
        _emit_metric(f"http://{receiver.address}")
        exports = receiver.received()

    assert [path for path, _ in exports] == ["/v1/metrics"]
    assert _counter_values(exports[0][1]) == [3]


def test_spans_honour_http_proxy(monkeypatch):
    with _Receiver() as receiver:
        monkeypatch.setenv("HTTP_PROXY", f"http://{receiver.address}")
        monkeypatch.setenv("http_proxy", f"http://{receiver.address}")
        _emit_span(COLLECTOR)
        exports = receiver.received()

    assert [path for path, _ in exports] == [f"{COLLECTOR}/v1/traces"]
    assert _span_names(exports[0][1]) == [SPAN_NAME]


def test_metrics_honour_http_proxy(monkeypatch):
    with _Receiver() as receiver:
        monkeypatch.setenv("HTTP_PROXY", f"http://{receiver.address}")
        monkeypatch.setenv("http_proxy", f"http://{receiver.address}")
        _emit_metric(COLLECTOR)
        exports = receiver.received()

    assert [path for path, _ in exports] == [f"{COLLECTOR}/v1/metrics"]
    assert _counter_values(exports[0][1]) == [3]
