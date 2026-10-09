"""
``prometheus_client`` backend for :mod:`salt.utils.metrics`.

Selected with ``metrics.exporter: prometheus``.  The OpenTelemetry SDK is
not involved: counters and histograms are plain ``prometheus_client``
metrics running in its *multiprocess* mode.

Every process (the master, each MWorker, the minion and its job
processes) writes its own values into a small mmap file in a shared
directory.  The process that called :func:`start` first serves
``/metrics``; on every scrape it reads all the files and adds the values
up.  Scrapers therefore see one series per metric and label set, with no
per-process label and nothing to ``sum``.

Observable gauges stay callbacks.  They are evaluated at scrape time in
the serving process, which is where Salt registers them (the master
parent, or the minion).

Known limitation: the files of exited processes stay in the directory
until the master stops, because deleting them would make the counters go
down.  ``prometheus_client`` has no compaction for counters and
histograms (``mark_process_dead`` only removes live gauges).  If this
becomes a problem, merge the files of dead pids into one with
``MultiProcessCollector.merge(files, accumulate=False)``, holding a lock
against concurrent scrapes and re-checking that the pid is still dead.

The directory belongs to Salt: it is created when the serving process
starts and removed when it stops, so values from a previous run never
leak in.  Do not set ``PROMETHEUS_MULTIPROC_DIR`` yourself; use
``metrics.prometheus.multiproc_dir`` to choose the location.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
import threading
from collections.abc import Callable, Iterable, Iterator
from types import SimpleNamespace
from typing import Any, TypeVar, cast

log = logging.getLogger(__name__)

_ENV = "PROMETHEUS_MULTIPROC_DIR"
# Set by the serving process so that processes that did not fork from it
# can tell its directory from one the user put in the environment.
_OWNER_ENV = "SALT_METRICS_PROMETHEUS_OWNER"

# Default bucket boundaries of the OpenTelemetry SDK for millisecond
# histograms; used when ``metrics.histogram_boundaries`` has no entry.
_DEFAULT_BOUNDARIES = (
    0.0,
    5.0,
    10.0,
    25.0,
    50.0,
    75.0,
    100.0,
    250.0,
    500.0,
    750.0,
    1000.0,
    2500.0,
    5000.0,
    7500.0,
    10000.0,
)

# Same unit suffixes the OpenTelemetry Prometheus exporter produces, so
# metric names do not change when the backend does.
_UNITS = {
    "s": "seconds",
    "ms": "milliseconds",
    "us": "microseconds",
    "ns": "nanoseconds",
    "By": "bytes",
}

# An observable-gauge callback takes the (unused) OpenTelemetry callback
# options and returns observations: objects with ``value`` and ``attributes``.
_Callback = Callable[[Any], Iterable[Any]]

_lock = threading.RLock()
_pc: Any = None  # the imported prometheus_client modules, once loaded
_load_failed: bool = False
_start_failed: bool = False

# State of the process that serves /metrics.  ``_dir`` is set (and
# inherited by forked children) once :func:`start` has run in the parent.
_dir: str | None = None
_dir_is_ours: bool = False
_owner_pid: int | None = None
_server: Any = None
_orig_value_class: Any = None
_boundaries: dict[str, tuple[float, ...]] = {}
_target_info: dict[str, str] = {}
# Problems already reported at warning level; see :func:`_warn_once`.
_warned: set[str] = set()

_instruments: dict[tuple[str, str], _Instrument] = {}
_callbacks: dict[str, tuple[_Callback, str, str]] = {}


def load() -> bool:
    """Import ``prometheus_client``; return ``False`` if it is missing."""
    global _pc, _load_failed  # pylint: disable=global-statement
    if _pc is not None:
        return True
    if _load_failed:
        return False
    with _lock:
        if _pc is not None:
            return True
        try:
            # pylint: disable=import-outside-toplevel
            import prometheus_client
            from prometheus_client import multiprocess, values
            from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily
        except ImportError:
            _load_failed = True
            log.error(
                "metrics.exporter is 'prometheus' but prometheus_client is not "
                "installed; metrics remain disabled."
            )
            return False
        _pc = SimpleNamespace(
            lib=prometheus_client,
            multiprocess=multiprocess,
            values=values,
            GaugeMetricFamily=GaugeMetricFamily,
            InfoMetricFamily=InfoMetricFamily,
        )
        return True


def start(opts: dict[str, Any]) -> bool:
    """
    Prepare this process for multiprocess metrics.

    Called from ``metrics.configure`` in every process.  The first call
    in the process tree creates the shared directory and starts the
    ``/metrics`` listener; later calls (forked children) only make sure
    their metrics write into that directory.
    """
    global _dir, _dir_is_ours, _owner_pid  # pylint: disable=global-statement
    global _server, _boundaries  # pylint: disable=global-statement
    global _start_failed, _target_info  # pylint: disable=global-statement
    if not load():
        return False
    with _lock:
        if _start_failed:
            return False
        _boundaries = _parse_boundaries(opts.get("histogram_boundaries"))
        _target_info = _build_target_info(opts)
        if _dir is None and os.environ.get(_ENV):
            if os.environ.get(_OWNER_ENV):
                # Inherited by a process that did not fork from the owner
                # (spawn start method): write into the owner's directory.
                _use_multiprocess_values()
                return True
            log.warning(
                "%s is set in the environment (%s); Salt manages its own "
                "directory and overrides it.",
                _ENV,
                os.environ[_ENV],
            )
        if _dir is not None:
            _use_multiprocess_values()
            return True

        prom_opts = opts.get("prometheus") or {}
        configured = prom_opts.get("multiproc_dir")
        if configured:
            os.makedirs(configured, exist_ok=True)
            for name in os.listdir(configured):
                if name.endswith(".db"):
                    os.remove(os.path.join(configured, name))
            _dir, _dir_is_ours = configured, False
        else:
            _dir, _dir_is_ours = tempfile.mkdtemp(prefix="salt-metrics-"), True
        os.environ[_ENV] = _dir
        os.environ[_OWNER_ENV] = str(os.getpid())
        _owner_pid = os.getpid()
        _use_multiprocess_values()

        host = prom_opts.get("host", "127.0.0.1")
        port = int(prom_opts.get("port", 9464))
        registry = _pc.lib.CollectorRegistry()
        _pc.multiprocess.MultiProcessCollector(registry, path=_dir)
        registry.register(_CallbackCollector())
        try:
            _server = _pc.lib.start_http_server(port=port, addr=host, registry=registry)
        except OSError as exc:
            log.error(
                "Failed to bind Prometheus listener on %s:%d: %s", host, port, exc
            )
            # Processes forked later must not try again and log the same error.
            _start_failed = True
            _teardown()
            return False
        log.info("Prometheus /metrics listener bound on %s:%d", host, port)
        return True


def stop() -> None:
    """Stop serving and remove the shared directory (owner process only)."""
    global _start_failed  # pylint: disable=global-statement
    with _lock:
        _start_failed = False
        _warned.clear()
        if _owner_pid is not None and _owner_pid == os.getpid():
            if isinstance(_server, tuple):
                try:
                    _server[0].shutdown()
                    _server[0].server_close()
                except Exception:  # pylint: disable=broad-except
                    log.debug("prometheus listener shutdown raised", exc_info=True)
            _teardown()
        _instruments.clear()
        _callbacks.clear()


def _teardown() -> None:
    global _dir, _dir_is_ours, _owner_pid, _server  # pylint: disable=global-statement
    if _pc is not None:
        close = getattr(_pc.values.ValueClass, "close_all_files", None)
        if close is not None:
            try:
                close()
            except Exception:  # pylint: disable=broad-except
                log.debug("closing multiprocess files raised", exc_info=True)
        if _orig_value_class is not None:
            _pc.values.ValueClass = _orig_value_class
    directory = _dir
    if directory:
        if _dir_is_ours:
            shutil.rmtree(directory, ignore_errors=True)
        else:
            for name in os.listdir(directory):
                if name.endswith(".db"):
                    try:
                        os.remove(os.path.join(directory, name))
                    except OSError:
                        pass
    os.environ.pop(_ENV, None)
    os.environ.pop(_OWNER_ENV, None)
    _dir, _dir_is_ours, _owner_pid, _server = None, False, None, None


def _use_multiprocess_values() -> None:
    """
    Make ``prometheus_client`` write to the shared directory.

    The library picks its value class when it is imported, from the
    environment.  Another module may have imported it earlier, so set
    the class explicitly instead of relying on the import order.
    """
    global _orig_value_class  # pylint: disable=global-statement
    values = _pc.values
    if getattr(values.ValueClass, "_multiprocess", False):
        return
    if _orig_value_class is None:
        _orig_value_class = values.ValueClass
    values.ValueClass = values.MultiProcessValue()


def _warn_once(key: str, message: str, *args: Any, exc_info: bool = False) -> None:
    """
    Log at warning level the first time ``key`` is seen and at debug level
    afterwards, so a problem on a hot path (or in every worker) shows up
    once without flooding the log.
    """
    if key in _warned:
        log.debug(message, *args, exc_info=exc_info)
        return
    _warned.add(key)
    log.warning(message, *args, exc_info=exc_info)


def _build_target_info(opts: dict[str, Any]) -> dict[str, str]:
    """Labels of the ``target_info`` metric: the service name and ``resource_attributes``."""
    attrs: dict[str, Any] = {"service.name": opts.get("service_name") or "salt"}
    extra = opts.get("resource_attributes")
    if isinstance(extra, dict):
        attrs.update(extra)
    return {_label_name(k): str(v) for k, v in attrs.items()}


def _parse_boundaries(boundaries_map: Any) -> dict[str, tuple[float, ...]]:
    parsed: dict[str, tuple[float, ...]] = {}
    if not isinstance(boundaries_map, dict):
        return parsed
    for name, bounds in boundaries_map.items():
        try:
            parsed[name] = tuple(sorted(float(b) for b in bounds))
        except (TypeError, ValueError):
            _warn_once(
                f"boundaries:{name}",
                "Ignoring non-numeric histogram_boundaries for %s",
                name,
            )
    return parsed


def _metric_name(name: str, unit: str = "") -> str:
    name = re.sub(r"[^a-zA-Z0-9:]+", "_", name)
    if name and name[0].isdigit():
        name = "_" + name[1:]
    unit = _UNITS.get(unit) or re.sub(r"[^a-zA-Z0-9]+", "", re.sub(r"{.*}", "", unit))
    return f"{name}_{unit}" if unit else name


def _label_name(key: Any) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(key))
    return "_" + cleaned if cleaned[:1].isdigit() else cleaned


def _labels(attributes: dict[str, Any] | None) -> dict[str, str]:
    return {_label_name(k): str(v) for k, v in (attributes or {}).items()}


class _Instrument:
    """
    Shared by counters and histograms.

    ``prometheus_client`` fixes the label names when a metric is created,
    while the call sites pass them with each measurement.  The names seen
    on the first measurement win; later measurements with a different set
    are mapped onto it (missing labels become empty, extra ones are
    dropped) instead of raising in the middle of a Salt request.
    """

    def __init__(self, name: str, description: str, unit: str) -> None:
        self._name = _metric_name(name, unit)
        self._description = description or name
        self._metric: Any = None
        self._labelnames: tuple[str, ...] = ()
        self._create_lock = threading.Lock()

    def _create(self, labelnames: tuple[str, ...]) -> Any:
        raise NotImplementedError

    def _child(self, attributes: dict[str, Any] | None) -> Any:
        labels = _labels(attributes)
        if self._metric is None:
            with self._create_lock:
                if self._metric is None:
                    self._labelnames = tuple(sorted(labels))
                    self._metric = self._create(self._labelnames)
        if not self._labelnames:
            return self._metric
        return self._metric.labels(*(labels.get(k, "") for k in self._labelnames))


class _Counter(_Instrument):
    def _create(self, labelnames: tuple[str, ...]) -> Any:
        return _pc.lib.Counter(self._name, self._description, labelnames, registry=None)

    def add(self, amount: float, attributes: dict[str, Any] | None = None) -> None:
        try:
            self._child(attributes).inc(amount)
        except Exception:  # pylint: disable=broad-except
            _warn_once(
                f"counter:{self._name}",
                "Prometheus counter %s could not be updated",
                self._name,
                exc_info=True,
            )


class _Histogram(_Instrument):
    def __init__(self, name: str, description: str, unit: str) -> None:
        super().__init__(name, description, unit)
        self._buckets = _boundaries.get(name) or _DEFAULT_BOUNDARIES

    def _create(self, labelnames: tuple[str, ...]) -> Any:
        return _pc.lib.Histogram(
            self._name,
            self._description,
            labelnames,
            buckets=self._buckets,
            registry=None,
        )

    def record(self, amount: float, attributes: dict[str, Any] | None = None) -> None:
        try:
            self._child(attributes).observe(amount)
        except Exception:  # pylint: disable=broad-except
            _warn_once(
                f"histogram:{self._name}",
                "Prometheus histogram %s could not be updated",
                self._name,
                exc_info=True,
            )


_I = TypeVar("_I", bound=_Instrument)


def _get(kind: str, factory: type[_I], name: str, description: str, unit: str) -> _I:
    key = (kind, name)
    instrument = _instruments.get(key)
    if instrument is None:
        with _lock:
            instrument = _instruments.setdefault(key, factory(name, description, unit))
    return cast(_I, instrument)


def counter(name: str, description: str = "", unit: str = "") -> _Counter:
    """Return the counter ``name``, creating it on first use."""
    return _get("counter", _Counter, name, description, unit)


def histogram(name: str, description: str = "", unit: str = "") -> _Histogram:
    """Return the histogram ``name``, creating it on first use."""
    return _get("histogram", _Histogram, name, description, unit)


def observable_gauge(
    name: str, callback: _Callback, description: str = "", unit: str = ""
) -> None:
    """
    Register ``callback``; it is called at scrape time by the process that
    serves ``/metrics``.  Registered in any other process it is never
    called, which matches how Salt uses these gauges.
    """
    with _lock:
        _callbacks[name] = (callback, description, unit)


class _CallbackCollector:
    """Expose the observable gauges next to the multiprocess metrics."""

    def collect(self) -> Iterator[Any]:
        if _target_info:
            yield _pc.InfoMetricFamily(
                "target", "Target metadata", value=dict(_target_info)
            )
        with _lock:
            callbacks = list(_callbacks.items())
        for name, (callback, description, unit) in callbacks:
            try:
                observations = list(callback(None) or ())
            except Exception:  # pylint: disable=broad-except
                _warn_once(
                    f"gauge:{name}",
                    "Prometheus observable gauge %s could not be read",
                    name,
                    exc_info=True,
                )
                continue
            labelnames = sorted(
                {_label_name(k) for obs in observations for k in (obs.attributes or {})}
            )
            family = _pc.GaugeMetricFamily(
                _metric_name(name, unit), description or name, labels=labelnames
            )
            for obs in observations:
                labels = _labels(obs.attributes)
                family.add_metric([labels.get(k, "") for k in labelnames], obs.value)
            yield family
