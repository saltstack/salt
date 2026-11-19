"""Regression tests for ``analyze_resiliency.PromState.get_slope`` and the
multi-master aggregate-mode routing applied in ``main()``.

Context: CI run 44267471361 flagged a false cluster5 ``master_rss`` leak
of 63,729 B/sec, driven entirely by master-1's post-marathon_outage_120m
revive ramp.  Masters 2-5 were flat.  With ``aggregate="max"`` any single
master's ramp fails the run; with ``aggregate="min"`` a real
cluster-wide leak still fails (present on every master) but a
single-master restart-ramp FP doesn't.  See
``agents/reports/cluster5-master-rss-leak-44267471361.md``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
ANALYZE_PATH = REPO_ROOT / "tests" / "resiliency" / "analyze_resiliency.py"


@pytest.fixture(scope="module")
def analyze():
    spec = importlib.util.spec_from_file_location("analyze_resiliency", ANALYZE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _series(values):
    return {
        "data": {
            "result": [
                {"metric": {"instance": f"m{i}"}, "value": [0.0, str(v)]}
                for i, v in enumerate(values, 1)
            ]
        }
    }


def test_max_mode_trips_on_single_master_ramp(analyze, monkeypatch):
    prom = analyze.PromState("http://x")
    monkeypatch.setattr(
        analyze, "query_prom", lambda url, promql: _series([100000, 500, 500, 500, 500])
    )
    assert prom.get_slope("salt_master_rss_bytes", aggregate="max") == 100000.0


def test_min_mode_filters_single_master_ramp(analyze, monkeypatch):
    """Four masters flat (500 B/sec), one restarted (100000 B/sec)
    ramping.  ``min`` returns 500 so the gate does not trip."""
    prom = analyze.PromState("http://x")
    monkeypatch.setattr(
        analyze, "query_prom", lambda url, promql: _series([100000, 500, 500, 500, 500])
    )
    assert prom.get_slope("salt_master_rss_bytes", aggregate="min") == 500.0


def test_min_mode_still_catches_cluster_wide_leak(analyze, monkeypatch):
    """Every master leaking at 10000 B/sec -- ``min`` still returns
    10000 so a real leak still fails the gate."""
    prom = analyze.PromState("http://x")
    monkeypatch.setattr(
        analyze,
        "query_prom",
        lambda url, promql: _series([10000, 10000, 10000, 10000, 10000]),
    )
    assert prom.get_slope("salt_master_rss_bytes", aggregate="min") == 10000.0


def test_default_aggregate_is_max_for_backcompat(analyze, monkeypatch):
    """Omitting ``aggregate`` preserves the pre-patch behavior (max),
    so callers that haven't migrated to topology-aware routing are
    unchanged."""
    prom = analyze.PromState("http://x")
    monkeypatch.setattr(
        analyze, "query_prom", lambda url, promql: _series([100000, 500])
    )
    assert prom.get_slope("salt_master_rss_bytes") == 100000.0


def test_empty_series_returns_zero(analyze, monkeypatch):
    prom = analyze.PromState("http://x")
    monkeypatch.setattr(
        analyze, "query_prom", lambda url, promql: {"data": {"result": []}}
    )
    assert prom.get_slope("salt_master_rss_bytes", aggregate="min") == 0.0
    assert prom.get_slope("salt_master_rss_bytes", aggregate="max") == 0.0
