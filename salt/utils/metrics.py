"""
OpenTelemetry metrics integration for Salt.

This module exposes a small, opinionated wrapper over the OpenTelemetry
Metrics SDK so that the rest of the codebase can create counters,
histograms and observable gauges unconditionally regardless of whether
metrics are enabled.

When ``opts['metrics']['enabled']`` is false (the default), every public
function short-circuits and instrument factories return no-op stubs.  No
``MeterProvider`` is initialised, no exporter is created, no background
thread is started, no listener is bound.

The provider is rebuilt per-PID.  ``PeriodicExportingMetricReader`` and
the Prometheus listener thread do not survive ``fork``, so every public
entry point calls :func:`_ensure_meter` which detects a PID change and
rebuilds the provider, reader and exporter in the child.

Configuration lives in ``opts['metrics']``::

    metrics:
      enabled: false
      exporter: otlp-http             # otlp-http | otlp-grpc | prometheus | console
      endpoint: ""                    # OTLP collector URL when applicable
      service_name: ""                # auto-derived when empty
      resource_attributes: {}
      insecure: true                  # gRPC TLS (ignored for non-grpc)
      headers: {}                     # OTLP auth headers
      export_interval_seconds: 60
      prometheus:
        host: 127.0.0.1               # localhost-bind by default
        port: 9464
      histogram_boundaries:
        salt.job.duration: [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000]
        salt.minion.exec.duration: [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

The default ``otlp-http`` exporter is pure-Python and ships in salt's
base requirements.  The ``otlp-grpc`` exporter is opt-in: install
``opentelemetry-exporter-otlp-proto-grpc`` separately to use it.

**Cardinality**: every instrument's labels must come from a bounded
domain.  Acceptable: ``fun`` (bounded by the salt module space),
``result`` (small enum), ``returner`` (configured returner names).
Unacceptable: ``minion_id``, ``jid``, ``user``.  Use those as trace
span attributes if you need them.
"""

import atexit
import logging
import os
import threading

log = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "salt"

# OpenTelemetry is optional.  It is not shipped in the salt-ssh thin
# tarball, may be absent from older installed onedirs that the upgrade /
# downgrade tests still exercise, and may be intentionally uninstalled
# by operators who want a minimal footprint.  When opentelemetry is
# missing, every public function in this module short-circuits to a
# no-op, exactly as if ``opts['metrics']['enabled']`` were false.
try:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter as _OTLPMetricExporterHTTP,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
    from opentelemetry.sdk.resources import Resource

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when opentelemetry is absent
    _OTEL_AVAILABLE = False
    otel_metrics = None  # type: ignore[assignment]
    _OTLPMetricExporterHTTP = None  # type: ignore[assignment]
    MeterProvider = None  # type: ignore[assignment]
    PeriodicExportingMetricReader = None  # type: ignore[assignment]
    ConsoleMetricExporter = None  # type: ignore[assignment]
    ExplicitBucketHistogramAggregation = None  # type: ignore[assignment]
    View = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]


_lock = threading.Lock()
_last_pid = None
_provider = None
_meter = None
_cached_opts = None
_atexit_registered = False
# Track the Prometheus HTTP server thread so we can stop it across forks.
_prometheus_server_thread = None


class _NoopCounter:
    """Returned when metrics are disabled or opentelemetry is absent."""

    def add(self, amount, attributes=None):  # noqa: ARG002
        return None


class _NoopHistogram:
    def record(self, amount, attributes=None):  # noqa: ARG002
        return None


class _NoopObservableGauge:
    """The OTel API returns nothing useful from create_observable_gauge,
    but we keep a stand-in so call sites have a consistent return type."""


_NOOP_COUNTER = _NoopCounter()
_NOOP_HISTOGRAM = _NoopHistogram()
_NOOP_OBSERVABLE = _NoopObservableGauge()


def is_enabled():
    """Return True if metrics are configured and enabled."""
    if not _OTEL_AVAILABLE:
        return False
    return bool(_cached_opts and _cached_opts.get("enabled"))


def configure(opts):
    """
    Initialise metrics for this process.

    Safe to call multiple times; the provider is rebuilt only when the
    PID changes or the cached configuration is empty.  When metrics are
    disabled — or when opentelemetry is not installed — this is a cheap
    no-op that just caches the opts so subsequent calls in fork children
    can pick up the same setting.
    """
    global _cached_opts, _atexit_registered
    metrics_opts = (opts or {}).get("metrics") or {}
    _cached_opts = dict(metrics_opts)
    _cached_opts.setdefault("service_name", _default_service_name(opts))
    if not _OTEL_AVAILABLE:
        if _cached_opts.get("enabled"):
            log.warning(
                "metrics.enabled is true but opentelemetry is not installed; "
                "metrics remain disabled in this process."
            )
        return
    if not _atexit_registered:
        atexit.register(shutdown)
        _atexit_registered = True
    if not _cached_opts.get("enabled"):
        log.debug(
            "metrics.configure called but metrics.enabled is false (pid=%d, service=%s)",
            os.getpid(),
            _cached_opts.get("service_name"),
        )
        return
    log.info(
        "Enabling OpenTelemetry metrics (pid=%d, service=%s, exporter=%s, endpoint=%s)",
        os.getpid(),
        _cached_opts.get("service_name"),
        _cached_opts.get("exporter"),
        _cached_opts.get("endpoint") or "<default>",
    )
    _ensure_meter()


def shutdown():
    """Flush and tear down the active provider."""
    global _provider, _meter, _last_pid, _prometheus_server_thread
    with _lock:
        provider = _provider
        _provider = None
        _meter = None
        _last_pid = None
        # The prometheus_client http server thread is daemonic; we just
        # drop our reference.  It will exit with the process.
        _prometheus_server_thread = None
    if provider is not None:
        try:
            provider.shutdown()
        except Exception:  # pylint: disable=broad-except
            log.debug("metrics provider shutdown raised", exc_info=True)


def counter(name, *, description="", unit=""):
    """
    Create (or fetch) a Counter instrument.

    Returns :data:`_NOOP_COUNTER` when metrics are disabled so the caller
    can use ``.add(n, attributes=...)`` unconditionally.
    """
    if not is_enabled():
        return _NOOP_COUNTER
    _ensure_meter()
    if _meter is None:
        return _NOOP_COUNTER
    return _meter.create_counter(name, description=description, unit=unit)


def histogram(name, *, description="", unit="ms", boundaries=None):
    """
    Create (or fetch) a Histogram instrument.

    The ``boundaries`` argument is accepted but ignored at instrument
    creation time — the OTel SDK takes histogram bucket boundaries from
    ``View``s attached to the ``MeterProvider``.  Per-metric boundaries
    are wired up in :func:`_build_provider` from
    ``opts['metrics']['histogram_boundaries']``.
    """
    if not is_enabled():
        return _NOOP_HISTOGRAM
    _ensure_meter()
    if _meter is None:
        return _NOOP_HISTOGRAM
    return _meter.create_histogram(name, description=description, unit=unit)


def observable_gauge(name, callback, *, description="", unit=""):
    """
    Register an observable gauge whose value comes from ``callback``.

    ``callback`` must be a callable returning an iterable of
    ``opentelemetry.metrics.Observation`` (typical for OTel's API).  When
    metrics are disabled this returns :data:`_NOOP_OBSERVABLE` and the
    callback is never invoked.

    Observable gauges should be registered in the master parent process
    only — registering them in MWorker children would over-count.
    """
    if not is_enabled():
        return _NOOP_OBSERVABLE
    _ensure_meter()
    if _meter is None:
        return _NOOP_OBSERVABLE
    return _meter.create_observable_gauge(
        name, callbacks=[callback], description=description, unit=unit
    )


def get_meter(name=_INSTRUMENTATION_NAME):
    """Return the underlying OTel Meter, or ``None`` when disabled.

    Useful as an escape hatch for instruments not covered by the
    convenience helpers above.
    """
    if not is_enabled():
        return None
    _ensure_meter()
    return _meter


def _ensure_meter():
    global _last_pid  # pylint: disable=global-statement
    pid = os.getpid()
    if _last_pid == pid and _provider is not None:
        return
    with _lock:
        if _last_pid == pid and _provider is not None:
            return
        if _cached_opts is None or not _cached_opts.get("enabled"):
            return
        _build_provider()
        _last_pid = pid


def _build_provider():
    global _provider, _meter
    opts = _cached_opts or {}
    resource = _build_resource(opts)
    views = _build_views(opts)
    readers = _build_readers(opts)
    if not readers:
        log.warning(
            "metrics enabled but no reader could be built; instruments "
            "will record into the void."
        )
    provider = MeterProvider(
        resource=resource,
        metric_readers=readers,
        views=views,
    )
    otel_metrics.set_meter_provider(provider)
    _provider = provider
    _meter = provider.get_meter(_INSTRUMENTATION_NAME)


def _build_resource(opts):
    attrs = {"service.name": opts.get("service_name") or "salt"}
    extra = opts.get("resource_attributes") or {}
    if isinstance(extra, dict):
        attrs.update(extra)
    return Resource.create(attrs)


def _build_views(opts):
    """
    Build Views that map per-metric histogram bucket boundaries onto the
    matching instruments.  When no boundaries are configured we return an
    empty list and the SDK falls back to its default exponential buckets.
    """
    boundaries_map = opts.get("histogram_boundaries") or {}
    if not isinstance(boundaries_map, dict) or not boundaries_map:
        return []
    views = []
    for instrument_name, bounds in boundaries_map.items():
        if not isinstance(bounds, (list, tuple)) or not bounds:
            continue
        try:
            float_bounds = tuple(float(b) for b in bounds)
        except (TypeError, ValueError):
            log.warning(
                "Ignoring non-numeric histogram_boundaries for %s: %r",
                instrument_name,
                bounds,
            )
            continue
        views.append(
            View(
                instrument_name=instrument_name,
                aggregation=ExplicitBucketHistogramAggregation(boundaries=float_bounds),
            )
        )
    return views


def _build_readers(opts):
    """Build the metric reader(s) for the configured exporter.

    Returns a list because some configurations (notably ``prometheus``)
    naturally combine a pull reader with a push fallback.  Today we
    return exactly one reader per call.
    """
    name = (opts.get("exporter") or "otlp-http").lower()
    interval_seconds = float(opts.get("export_interval_seconds") or 60)
    endpoint = opts.get("endpoint") or None
    headers = opts.get("headers") or None
    insecure = opts.get("insecure", True)

    if name == "console":
        return [
            PeriodicExportingMetricReader(
                ConsoleMetricExporter(),
                export_interval_millis=int(interval_seconds * 1000),
            )
        ]

    if name == "otlp-http":
        kwargs = {}
        if endpoint:
            kwargs["endpoint"] = endpoint
        if headers:
            kwargs["headers"] = headers
        return [
            PeriodicExportingMetricReader(
                _OTLPMetricExporterHTTP(**kwargs),
                export_interval_millis=int(interval_seconds * 1000),
            )
        ]

    if name == "otlp-grpc":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter as _OTLPMetricExporterGRPC,
            )
        except ImportError:
            log.error(
                "opentelemetry-exporter-otlp-proto-grpc is not installed; "
                "either install it or set metrics.exporter to 'otlp-http' "
                "or 'prometheus'."
            )
            return []
        kwargs = {"insecure": bool(insecure)}
        if endpoint:
            kwargs["endpoint"] = endpoint
        if headers:
            kwargs["headers"] = headers
        return [
            PeriodicExportingMetricReader(
                _OTLPMetricExporterGRPC(**kwargs),
                export_interval_millis=int(interval_seconds * 1000),
            )
        ]

    if name == "prometheus":
        try:
            from opentelemetry.exporter.prometheus import PrometheusMetricReader
            from prometheus_client import start_http_server
        except ImportError:
            log.error(
                "opentelemetry-exporter-prometheus is not installed; "
                "either install it or pick a different metrics.exporter."
            )
            return []
        prometheus_opts = opts.get("prometheus") or {}
        host = prometheus_opts.get("host", "127.0.0.1")
        port = int(prometheus_opts.get("port", 9464))
        global _prometheus_server_thread  # pylint: disable=global-statement
        try:
            # ``start_http_server`` is idempotent in the sense that calling
            # it twice in the same process raises ``OSError`` (port in use).
            # We track the thread we started so a fork child can re-bind.
            _prometheus_server_thread = start_http_server(port=port, addr=host)
        except OSError as exc:
            log.error(
                "Failed to bind Prometheus listener on %s:%d: %s",
                host,
                port,
                exc,
            )
            return []
        log.info("Prometheus /metrics listener bound on %s:%d", host, port)
        return [PrometheusMetricReader()]

    log.warning("Unknown metrics exporter %r; metrics will be a no-op", name)
    return []


def _default_service_name(opts):
    if not opts:
        return "salt"
    role = opts.get("__role")
    if role == "master":
        return "salt-master"
    if role == "minion":
        minion_id = opts.get("id") or ""
        return f"salt-minion-{minion_id}" if minion_id else "salt-minion"
    return "salt"
