"""Prometheus slope queries for the Salt resiliency pytest suite.

Thin stdlib wrapper around the Prometheus HTTP API, mirroring the
graceful-degrade semantics of ``tests/resiliency/analyze_resiliency.py``:
every network failure is logged as a WARNING and reduced to a slope of
``0.0``, so a scenario test never crashes merely because Prometheus was
unreachable.  The pytest layer calls :func:`prometheus_up` separately to
decide whether a ``0.0`` means "no leak detected" or "no data at all".

Thresholds come from :mod:`tests.resiliency.durations` -- no magic numbers
live in this module.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from tests.resiliency.durations import (
    MASTER_FD_LEAK_PER_MIN,
    MASTER_RSS_LEAK_BYTES_PER_SEC,
)

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


log = logging.getLogger("resiliency.metrics")


# Match analyze_resiliency.py's DEFAULT_PROM_URL: 127.0.0.1 (not
# ``localhost``) to dodge IPv6 resolution surprises on Ubuntu runners
# where ``localhost`` resolves to ``::1`` and Prometheus binds v4-only.
_DEFAULT_PROM_URL = "http://127.0.0.1:19090"


def _resolve_url(url: str | None) -> str:
    """URL precedence: explicit arg -> ``PROMETHEUS_URL`` env -> default.

    Callers for multimaster/syndic/cluster5 either pass ``url=`` explicitly
    or set ``PROMETHEUS_URL`` in the environment; those topologies run
    Prometheus on different host ports (19091/19092/19093).
    """
    if url is not None:
        return url
    return os.environ.get("PROMETHEUS_URL", _DEFAULT_PROM_URL)


def _query(prom_url: str, promql: str, timeout: int) -> dict | None:
    """Issue an instant query, returning the parsed JSON body or ``None``.

    ``None`` is returned on any network / decode failure after logging a
    WARNING -- callers map this to a slope of ``0.0``.
    """
    params = urllib.parse.urlencode({"query": promql})
    endpoint = f"{prom_url}/api/v1/query?{params}"
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout) as response:
            body = response.read().decode()
    except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
        log.warning("prometheus query %r at %s failed: %s", promql, prom_url, exc)
        return None
    except OSError as exc:
        # urllib occasionally surfaces bare socket errors (e.g. refused
        # connection on an unused port) as OSError rather than URLError.
        log.warning("prometheus query %r at %s failed: %s", promql, prom_url, exc)
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        log.warning(
            "prometheus query %r at %s returned non-JSON: %s", promql, prom_url, exc
        )
        return None


def prometheus_slope(
    query: str,
    duration: str = "30m",
    url: str | None = None,
    timeout: int = 10,
) -> float:
    """Return ``deriv(query[duration])`` as a scalar.

    On unreachable Prometheus or an empty result set, returns ``0.0``
    after logging a WARNING.  When multiple series are returned (e.g.
    one per master in a cluster), the max slope wins -- a leak in any
    master is a leak worth reporting.

    URL precedence: explicit ``url`` arg -> ``PROMETHEUS_URL`` env ->
    ``http://127.0.0.1:19090``.
    """
    prom_url = _resolve_url(url)
    promql = f"deriv({query}[{duration}])"
    data = _query(prom_url, promql, timeout)
    if data is None:
        return 0.0
    try:
        results = data["data"]["result"]
    except (KeyError, TypeError):
        log.warning(
            "prometheus query %r at %s: unexpected response shape", promql, prom_url
        )
        return 0.0
    if not results:
        return 0.0
    slopes: list[float] = []
    for series in results:
        try:
            slopes.append(float(series["value"][1]))
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return max(slopes) if slopes else 0.0


def master_fd_slope(url: str | None = None) -> float:
    """``deriv(salt_master_open_fds[30m])`` in fds/sec."""
    return prometheus_slope("salt_master_open_fds", url=url)


def master_rss_slope(url: str | None = None) -> float:
    """``deriv(salt_master_rss_bytes[30m])`` in bytes/sec."""
    return prometheus_slope("salt_master_rss_bytes", url=url)


def master_fd_leak_detected(url: str | None = None) -> bool:
    """True iff the master fd slope exceeds the per-minute threshold.

    ``MASTER_FD_LEAK_PER_MIN`` is operator-friendly (fds/min); deriv()
    returns fds/sec, so divide by 60.  Matches analyze_resiliency.py's
    ``fd_fail_threshold`` calculation.
    """
    return master_fd_slope(url=url) > (MASTER_FD_LEAK_PER_MIN / 60.0)


def master_rss_leak_detected(url: str | None = None) -> bool:
    """True iff the master RSS slope exceeds the bytes/sec threshold."""
    return master_rss_slope(url=url) > MASTER_RSS_LEAK_BYTES_PER_SEC


def prometheus_up(url: str | None = None, timeout: int = 3) -> bool:
    """Return True iff Prometheus is reachable and reports healthy.

    Hits ``/-/healthy``, which Prometheus answers with HTTP 200 and the
    literal body ``Prometheus Server is Healthy.`` when running.  Any
    network failure, non-200 status, or decode error -> False.
    """
    prom_url = _resolve_url(url)
    endpoint = f"{prom_url.rstrip('/')}/-/healthy"
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        log.warning("prometheus healthcheck at %s failed: %s", prom_url, exc)
        return False
