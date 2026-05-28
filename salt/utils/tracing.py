"""
OpenTelemetry tracing integration for Salt.

This module exposes a small, opinionated wrapper over the OpenTelemetry SDK
so that the rest of the codebase can call ``start_span``, ``inject`` and
``extract`` unconditionally regardless of whether tracing is enabled.

When ``opts['tracing']['enabled']`` is false (the default), every public
function short-circuits and ``start_span`` returns a :class:`_NoopSpan`.  No
spans are created, no exporter is initialised and no background threads are
started.

The carrier format on the wire is W3C TraceContext: a ``traceparent`` (and
optional ``tracestate``) string injected into the appropriate dict / header
/ env var by the caller.

The provider is rebuilt per-PID.  ``BatchSpanProcessor`` runs a background
thread that is not preserved across ``fork``, so every public entry point
calls :func:`_ensure_tracer` which detects a PID change and rebuilds the
provider, processor and exporter in the child.

Configuration lives in ``opts['tracing']``::

    tracing:
      enabled: false
      exporter: otlp-http           # otlp-http | otlp-grpc | console
      endpoint: ""                  # OTel SDK default (4318/v1/traces for http, 4317 for grpc)
      service_name: ""              # auto-derived when empty
      sampler: parent_based         # parent_based | always_on | always_off | trace_id_ratio
      sampler_arg: 1.0
      resource_attributes: {}
      insecure: true
      headers: {}

The default ``otlp-http`` exporter is pure-Python and ships in salt's base
requirements.  The ``otlp-grpc`` exporter is opt-in: install
``opentelemetry-exporter-otlp-proto-grpc`` separately to use it.
"""

import atexit
import contextlib
import logging
import os
import threading

log = logging.getLogger(__name__)

_INSTRUMENTATION_NAME = "salt"

# OpenTelemetry is optional.  It is not shipped in the salt-ssh thin
# tarball, may be absent from older installed onedirs that the upgrade /
# downgrade tests still exercise, and may be intentionally uninstalled by
# operators who want a minimal footprint.  When opentelemetry is missing,
# every public function in this module short-circuits to a no-op, exactly
# as if ``opts['tracing']['enabled']`` were false.
try:
    from opentelemetry import context as otel_context
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter as _OTLPSpanExporterHTTP,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    _OTEL_AVAILABLE = True
    SpanKind = trace.SpanKind
except ImportError:  # pragma: no cover - exercised when opentelemetry is absent
    _OTEL_AVAILABLE = False
    otel_context = None  # type: ignore[assignment]
    trace = None  # type: ignore[assignment]
    _OTLPSpanExporterHTTP = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]
    TracerProvider = None  # type: ignore[assignment]
    BatchSpanProcessor = None  # type: ignore[assignment]
    ConsoleSpanExporter = None  # type: ignore[assignment]
    ALWAYS_OFF = ALWAYS_ON = ParentBased = TraceIdRatioBased = None  # type: ignore[assignment]
    TraceContextTextMapPropagator = None  # type: ignore[assignment]

    class _SpanKindStub:
        """Duck-typed ``trace.SpanKind`` used when opentelemetry is missing."""

        INTERNAL = "INTERNAL"
        SERVER = "SERVER"
        CLIENT = "CLIENT"
        PRODUCER = "PRODUCER"
        CONSUMER = "CONSUMER"

    SpanKind = _SpanKindStub()  # type: ignore[assignment]


_lock = threading.Lock()
_last_pid = None
_provider = None
_tracer = None
_cached_opts = None
_propagator = TraceContextTextMapPropagator() if _OTEL_AVAILABLE else None
_atexit_registered = False


class _InvalidSpanContext:
    """Minimal stand-in for ``trace.INVALID_SPAN_CONTEXT`` when otel is absent."""

    trace_id = 0
    span_id = 0
    is_valid = False
    is_remote = False
    trace_flags = 0
    trace_state = None


_INVALID_SPAN_CONTEXT_FALLBACK = _InvalidSpanContext()


class _NoopSpan:
    """Stand-in returned when tracing is disabled or opentelemetry is absent."""

    is_recording = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, key, value):  # noqa: ARG002
        return None

    def set_attributes(self, attributes):  # noqa: ARG002
        return None

    def add_event(self, name, attributes=None, timestamp=None):  # noqa: ARG002
        return None

    def record_exception(self, exception, attributes=None):  # noqa: ARG002
        return None

    def set_status(self, status, description=None):  # noqa: ARG002
        return None

    def update_name(self, name):  # noqa: ARG002
        return None

    def end(self, end_time=None):  # noqa: ARG002
        return None

    def get_span_context(self):
        if _OTEL_AVAILABLE:
            return trace.INVALID_SPAN_CONTEXT
        return _INVALID_SPAN_CONTEXT_FALLBACK


_NOOP_SPAN = _NoopSpan()


def is_enabled():
    """Return True if tracing is configured and enabled."""
    if not _OTEL_AVAILABLE:
        return False
    return bool(_cached_opts and _cached_opts.get("enabled"))


def configure(opts):
    """
    Initialise tracing for this process.

    ``opts`` is the full Salt opts dict; the ``tracing`` block is read out of
    it.  Safe to call multiple times; the provider is rebuilt only when the
    PID changes or the cached configuration is empty.

    When tracing is disabled — or when opentelemetry is not installed —
    this is a cheap no-op that just caches the opts so that subsequent
    calls in fork children can pick up the same setting.
    """
    global _cached_opts, _atexit_registered
    tracing_opts = (opts or {}).get("tracing") or {}
    _cached_opts = dict(tracing_opts)
    _cached_opts.setdefault("service_name", _default_service_name(opts))
    if not _OTEL_AVAILABLE:
        if _cached_opts.get("enabled"):
            log.warning(
                "tracing.enabled is true but opentelemetry is not installed; "
                "tracing remains disabled in this process."
            )
        return
    if not _atexit_registered:
        atexit.register(shutdown)
        _atexit_registered = True
    if not _cached_opts.get("enabled"):
        log.debug(
            "tracing.configure called but tracing.enabled is false (pid=%d, service=%s)",
            os.getpid(),
            _cached_opts.get("service_name"),
        )
        return
    log.info(
        "Enabling OpenTelemetry tracing (pid=%d, service=%s, exporter=%s, endpoint=%s)",
        os.getpid(),
        _cached_opts.get("service_name"),
        _cached_opts.get("exporter"),
        _cached_opts.get("endpoint") or "<default>",
    )
    _ensure_tracer()


def shutdown():
    """Flush and tear down the active provider."""
    global _provider, _tracer, _last_pid
    with _lock:
        provider = _provider
        _provider = None
        _tracer = None
        _last_pid = None
    if provider is not None:
        try:
            provider.shutdown()
        except Exception:  # pylint: disable=broad-except
            log.debug("tracing provider shutdown raised", exc_info=True)


def start_span(name, *, kind=None, attributes=None, links=None, context=None):
    """
    Open a span as a context manager.

    Returns a no-op context manager when tracing is disabled.  ``context``
    is an opaque value previously returned from :func:`extract` and is used
    to link the new span as a child of a remote parent.
    """
    if not is_enabled():
        return _NOOP_SPAN
    _ensure_tracer()
    if _tracer is None:
        return _NOOP_SPAN
    if context is not None:
        return _start_with_context(name, context, kind, attributes, links)
    return _tracer.start_as_current_span(
        name,
        kind=kind or trace.SpanKind.INTERNAL,
        attributes=attributes,
        links=links,
    )


@contextlib.contextmanager
def _start_with_context(name, ctx, kind, attributes, links):
    token = otel_context.attach(ctx)
    try:
        with _tracer.start_as_current_span(
            name,
            kind=kind or trace.SpanKind.INTERNAL,
            attributes=attributes,
            links=links,
        ) as span:
            yield span
    finally:
        otel_context.detach(token)


def current_span():
    """Return the currently active span, or a :class:`_NoopSpan`."""
    if not is_enabled():
        return _NOOP_SPAN
    return trace.get_current_span()


def set_attribute(key, value):
    """Set an attribute on the current span (no-op when disabled)."""
    if not is_enabled():
        return
    span = trace.get_current_span()
    if span is not None and span.is_recording():
        span.set_attribute(key, value)


def record_exception(exc):
    """Record an exception on the current span (no-op when disabled)."""
    if not is_enabled():
        return
    span = trace.get_current_span()
    if span is not None and span.is_recording():
        span.record_exception(exc)


def inject(carrier):
    """
    Inject the current trace context into ``carrier``.

    ``carrier`` is any ``MutableMapping`` (e.g. the inner ``load`` dict of a
    Salt request, an event ``data`` dict, an HTTP header mapping or an env
    var dict).  When there is no recording span — or when opentelemetry is
    not installed — this is a no-op so the on-the-wire payload is not
    bloated with empty headers.
    """
    if not is_enabled() or _propagator is None:
        return
    span = trace.get_current_span()
    if span is None or not span.is_recording():
        return
    _propagator.inject(carrier)


def extract(carrier):
    """
    Extract a context from ``carrier``.

    Returns an opaque context object suitable for passing to
    :func:`start_span` as ``context=...``, or ``None`` when no context was
    found, tracing is disabled, or opentelemetry is not installed.
    """
    if not is_enabled() or not carrier or _propagator is None:
        return None
    ctx = _propagator.extract(carrier)
    if ctx is otel_context.Context():
        return None
    return ctx


def _ensure_tracer():
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
    global _provider, _tracer
    opts = _cached_opts or {}
    resource = _build_resource(opts)
    sampler = _build_sampler(opts)
    provider = TracerProvider(resource=resource, sampler=sampler)
    exporter = _build_exporter(opts)
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    _provider = provider
    _tracer = provider.get_tracer(_INSTRUMENTATION_NAME)


def _build_resource(opts):
    attrs = {"service.name": opts.get("service_name") or "salt"}
    extra = opts.get("resource_attributes") or {}
    if isinstance(extra, dict):
        attrs.update(extra)
    return Resource.create(attrs)


def _build_sampler(opts):
    name = (opts.get("sampler") or "parent_based").lower()
    arg = opts.get("sampler_arg", 1.0)
    if name == "always_on":
        return ALWAYS_ON
    if name == "always_off":
        return ALWAYS_OFF
    if name == "trace_id_ratio":
        return TraceIdRatioBased(float(arg))
    if name == "parent_based":
        try:
            ratio = float(arg)
        except (TypeError, ValueError):
            ratio = 1.0
        root = ALWAYS_ON if ratio >= 1.0 else TraceIdRatioBased(ratio)
        return ParentBased(root=root)
    log.warning(
        "Unknown tracing sampler %r; defaulting to parent_based+always_on", name
    )
    return ParentBased(root=ALWAYS_ON)


def _build_exporter(opts):
    name = (opts.get("exporter") or "otlp-http").lower()
    endpoint = opts.get("endpoint") or None
    headers = opts.get("headers") or None
    insecure = opts.get("insecure", True)
    try:
        if name == "console":
            return ConsoleSpanExporter()
        if name == "otlp-http":
            kwargs = {}
            if endpoint:
                kwargs["endpoint"] = endpoint
            if headers:
                kwargs["headers"] = headers
            return _OTLPSpanExporterHTTP(**kwargs)
        if name == "otlp-grpc":
            # The gRPC exporter pulls in grpcio which has no wheel for some
            # interpreter / platform combinations.  Import lazily so the
            # default HTTP path works even when grpc isn't installed.
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter as _OTLPSpanExporterGRPC,
                )
            except ImportError:
                log.error(
                    "opentelemetry-exporter-otlp-proto-grpc is not installed; "
                    "either install it or set tracing.exporter to 'otlp-http'."
                )
                return None
            kwargs = {"insecure": bool(insecure)}
            if endpoint:
                kwargs["endpoint"] = endpoint
            if headers:
                kwargs["headers"] = headers
            return _OTLPSpanExporterGRPC(**kwargs)
    except Exception:  # pylint: disable=broad-except
        log.exception("Failed to build tracing exporter %r", name)
        return None
    log.warning("Unknown tracing exporter %r; tracing will be a no-op", name)
    return None


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
