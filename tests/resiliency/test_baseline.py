"""Baseline sanity battery -- pytest port of ``scenarios/baseline.sh``.

Every phase here is a "null fault": none of them injects a real outage.
Their job is to prove the measurement harness itself (fd / RSS sampling,
``assert_reconnect``'s minute-normalised slope check, the reconnect
budget) does not manufacture phantom leaks or phantom recoveries on a
healthy fleet.  If any of these tests fail, verdicts from the real
fault scenarios are suspect -- they are likely reporting the same
noise.

Phase -> test mapping (same labels as the bash scenario, passed as the
first arg to ``assert_reconnect`` / ``stash_result`` so results.jsonl
rows stay compatible with the analyzer):

    baseline_idle_300s                     test_baseline_idle_short
    baseline_idle_1800s                    test_baseline_idle_long
    baseline_workload_only_600s            test_baseline_workload_only
    baseline_workload_only_600s_ping       (post-workload reconnect check
                                            inside test_baseline_workload_only)
    baseline_rapid_ping_burst_60s          test_baseline_rapid_ping_burst
    baseline_rapid_runner_60s              test_baseline_rapid_runner
    baseline_ping_200_concurrent           test_baseline_ping_200_concurrent
    baseline_recovery_window_tightness     test_baseline_recovery_window_tightness

Env knobs (defaults preserved from baseline.sh):

    BASELINE_IDLE_SHORT_SEC      TIER_DEEPREC_SEC (300)
    BASELINE_LONG_IDLE           0   (set to 1 to enable the long-idle test)
    BASELINE_IDLE_LONG_SEC       TIER_ACCUM_SEC (1800)
    BASELINE_WORKLOAD_SEC        TIER_BACKOFF_SEC (600)
    BASELINE_BURST_SEC           TIER_STANDARD_SEC (90)
    BASELINE_BURST_SLEEP_MS      100
    BASELINE_CONCURRENT_N        200
    BASELINE_CONCURRENT_PAR      50
    BASELINE_TIGHT_HOLD_SEC      1
    BASELINE_TIGHT_WINDOW_SEC    10
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from tests.resiliency.conftest import stash_result
from tests.resiliency.durations import (
    PING_TIMEOUT_SEC,
    RECOVER_FAST_SEC,
    RECOVER_STANDARD_SEC,
    RSS_LEAK_KB_PER_MIN,
    TIER_ACCUM_SEC,
    TIER_BACKOFF_SEC,
    TIER_DEEPREC_SEC,
    TIER_STANDARD_SEC,
)
from tests.resiliency.lib.injectors import sigstopped_container

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


# ---------------------------------------------------------------------------
# Env-var helpers (preserve the BASELINE_* knob names from baseline.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


# ---------------------------------------------------------------------------
# Phase 1: short idle
# ---------------------------------------------------------------------------


def test_baseline_idle_short(topology, request):
    """baseline_idle_300s -- 5 min idle, no workload, no faults.

    fd/rss delta is the empirical no-leak floor.  assert_reconnect is
    called with fault_sec=0 so reconnect must be ~instant.  A non-zero
    fd delta is annotated in ``notes`` but still records as
    ``recovered`` -- a healthy host still has non-zero deltas from
    fd_exporter / prometheus scrapes.
    """
    label = "baseline_idle_short"
    before = topology.sample_minions()
    idle_sec = _env_int("BASELINE_IDLE_SHORT_SEC", TIER_DEEPREC_SEC)
    time.sleep(idle_sec)

    now = topology.sample_minions()
    fd_delta = now.fds - before.fds
    notes = ""
    if fd_delta > 0:
        notes = f"fd grew +{fd_delta}; expected ~0; check monitoring stack footprint"

    topology.assert_reconnect(
        label,
        fault_sec=0,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: long idle (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("BASELINE_LONG_IDLE") != "1",
    reason="BASELINE_LONG_IDLE=0 (set to 1 to opt in; 30-min runtime)",
)
def test_baseline_idle_long(topology, request):
    """baseline_idle_1800s -- 30 min idle; opt-in via BASELINE_LONG_IDLE=1.

    Skipped by default (conftest's hook maps the pytest skip to
    results.jsonl outcome="skipped_for_topology" iff the topology
    marker triggered it; a plain skipif here is treated as
    scenario-not-invoked, matching the bash behavior of recording a
    setup_error only when the flag was set and setup failed).
    """
    label = "baseline_idle_long"
    before = topology.sample_minions()
    idle_sec = _env_int("BASELINE_IDLE_LONG_SEC", TIER_ACCUM_SEC)
    time.sleep(idle_sec)

    topology.assert_reconnect(
        label,
        fault_sec=0,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="long_idle=1",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: workload-only 600s -- THE KEY TEST
# ---------------------------------------------------------------------------


def test_baseline_workload_only(topology, workload, request):
    """baseline_workload_only_600s -- run workload for ~10 min, compute
    minute-normalised RSS slope in-script, compare to
    :data:`RSS_LEAK_KB_PER_MIN`.

    This test owns its slope verdict (does NOT delegate to
    assert_reconnect's hidden calculation) so the "why did baseline
    fail" answer is one line in CI output.

    After the workload teardown, a second reconnect assertion under
    label ``baseline_workload_only_600s_ping`` proves the fleet is
    still responsive.  That assertion stashes over the slope-verdict
    row, so we emit two JSONL rows: the slope verdict first (via
    direct stash_result), then the post-workload health-check row
    (via assert_reconnect).  See conftest._append_jsonl_row -- it only
    emits once per test, keyed off the final stash state, so we
    instead emit the slope row from a sub-scope by calling
    stash_result with the slope label and letting the makereport hook
    use it.

    Simpler plan (matches contract): record the slope verdict inline
    via stash_result + assert_reconnect replaces it with the health
    row.  To preserve both rows the bash emitted, we fail-fast on the
    slope check (so the slope row wins) or pass-through to
    assert_reconnect (so the health row wins).  The analyzer reads
    whichever wins; both outcomes reflect the same underlying state.
    """
    label = "baseline_workload_only_600s"
    workload_sec = _env_int("BASELINE_WORKLOAD_SEC", TIER_BACKOFF_SEC)

    before = topology.sample_minions()

    # The ``workload`` fixture already launched workload.sh in a
    # dedicated pgroup before this test body ran.  Just hold for the
    # measurement window.
    start = time.monotonic()
    time.sleep(workload_sec)
    elapsed = int(time.monotonic() - start)

    after = topology.sample_minions()
    delta = after - before
    fd_delta = delta.fds
    rss_delta_kb = delta.rss_kb

    # Guard against sub-minute windows with the same 60s floor
    # assert_reconnect uses so our slope is directly comparable.
    window = max(60, elapsed)
    rss_per_min = rss_delta_kb * 60 // window

    notes = (
        f"rss_kb_per_min={rss_per_min} "
        f"threshold={RSS_LEAK_KB_PER_MIN} "
        f"workload_s={elapsed}"
    )

    if rss_per_min > RSS_LEAK_KB_PER_MIN:
        # Stash the slope-verdict row then fail; conftest will emit
        # one JSONL row with outcome="failed" and the slope in notes.
        stash_result(
            request.node,
            scenario=label,
            reconnect_seconds=0,
            attempts=1,
            missing=[],
            fd_delta=fd_delta,
            rss_kb_delta=rss_delta_kb,
            fault_seconds=elapsed,
            notes=notes,
        )
        pytest.fail(f"{label}: LEAK -- {notes}")

    # Clean slope.  Stash the verdict row (recorded only if this
    # test exits without further assertions mutating user_properties).
    stash_result(
        request.node,
        scenario=label,
        reconnect_seconds=0,
        attempts=1,
        missing=[],
        fd_delta=fd_delta,
        rss_kb_delta=rss_delta_kb,
        fault_seconds=elapsed,
        notes=notes,
    )

    # Workload fixture tears itself down on test exit, but we want the
    # post-workload health probe to see a clean fleet.  The teardown
    # happens in the fixture's finalizer; for the purpose of the
    # health-check we sample AFTER the workload-hold above, which is
    # the closest approximation to the bash scenario's
    # "tear down workload BEFORE the final ping" ordering we can
    # get without reaching into the fixture.
    ping_before = topology.sample_minions()
    topology.assert_reconnect(
        f"{label}_ping",
        fault_sec=0,
        before=ping_before,
        window_sec=RECOVER_FAST_SEC,
        notes="post_workload_health_check",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: rapid test.ping burst
# ---------------------------------------------------------------------------


def test_baseline_rapid_ping_burst(topology, request):
    """baseline_rapid_ping_burst_60s -- tight test.ping loop at
    100 ms interval for 60 s; assert every sweep succeeded and no fd
    growth."""
    label = "baseline_rapid_ping_burst_60s"
    burst_sec = _env_int("BASELINE_BURST_SEC", TIER_STANDARD_SEC)
    sleep_ms = _env_int("BASELINE_BURST_SLEEP_MS", 100)
    sleep_frac = sleep_ms / 1000.0

    before = topology.sample_minions()
    deadline = time.monotonic() + burst_sec
    attempts = 0
    failures = 0
    master = topology.spec.primary_master

    while time.monotonic() < deadline:
        attempts += 1
        rc = subprocess.run(
            [
                "docker",
                "exec",
                master,
                "salt",
                f"--timeout={min(PING_TIMEOUT_SEC, 10)}",
                "--out=json",
                "*",
                "test.ping",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        if rc != 0:
            failures += 1
        time.sleep(sleep_frac)

    after = topology.sample_minions()
    delta = after - before
    fd_delta = delta.fds
    rss_delta_kb = delta.rss_kb
    notes = f"attempts={attempts} failures={failures}"

    if failures > 0 or fd_delta > 0:
        stash_result(
            request.node,
            scenario=label,
            reconnect_seconds=-1,
            attempts=attempts,
            missing=[],
            fd_delta=fd_delta,
            rss_kb_delta=rss_delta_kb,
            fault_seconds=burst_sec,
            notes=notes,
        )
        pytest.fail(f"{label}: {notes} fd_delta={fd_delta} rss_delta_kb={rss_delta_kb}")

    stash_result(
        request.node,
        scenario=label,
        reconnect_seconds=0,
        attempts=attempts,
        missing=[],
        fd_delta=fd_delta,
        rss_kb_delta=rss_delta_kb,
        fault_seconds=burst_sec,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Phase 5: rapid runner (manage.status) burst
# ---------------------------------------------------------------------------


def test_baseline_rapid_runner(topology, request):
    """baseline_rapid_runner_60s -- tight salt-run manage.status loop at
    100 ms interval for 60 s; assert every sweep succeeded and no fd
    growth."""
    label = "baseline_rapid_runner_60s"
    burst_sec = _env_int("BASELINE_BURST_SEC", TIER_STANDARD_SEC)
    sleep_ms = _env_int("BASELINE_BURST_SLEEP_MS", 100)
    sleep_frac = sleep_ms / 1000.0

    before = topology.sample_minions()
    deadline = time.monotonic() + burst_sec
    attempts = 0
    failures = 0
    master = topology.spec.primary_master

    while time.monotonic() < deadline:
        attempts += 1
        rc = subprocess.run(
            ["docker", "exec", master, "salt-run", "manage.status"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        if rc != 0:
            failures += 1
        time.sleep(sleep_frac)

    after = topology.sample_minions()
    delta = after - before
    fd_delta = delta.fds
    rss_delta_kb = delta.rss_kb
    notes = f"attempts={attempts} failures={failures}"

    if failures > 0 or fd_delta > 0:
        stash_result(
            request.node,
            scenario=label,
            reconnect_seconds=-1,
            attempts=attempts,
            missing=[],
            fd_delta=fd_delta,
            rss_kb_delta=rss_delta_kb,
            fault_seconds=burst_sec,
            notes=notes,
        )
        pytest.fail(f"{label}: {notes} fd_delta={fd_delta} rss_delta_kb={rss_delta_kb}")

    stash_result(
        request.node,
        scenario=label,
        reconnect_seconds=0,
        attempts=attempts,
        missing=[],
        fd_delta=fd_delta,
        rss_kb_delta=rss_delta_kb,
        fault_seconds=burst_sec,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Phase 6: 200 concurrent async pings
# ---------------------------------------------------------------------------


def test_baseline_ping_200_concurrent(topology, request):
    """baseline_ping_200_concurrent -- fire N async pings concurrently
    (xargs -P in bash; we use a bounded ThreadPool-free fan-out via
    subprocess.Popen batches), then assert the fleet is responsive
    inside 2x the normal reconnect window.

    Individual ping failures are tolerated; we rely on
    assert_reconnect to decide health, exactly as the bash scenario
    does.
    """
    label = "baseline_ping_200_concurrent"
    n = _env_int("BASELINE_CONCURRENT_N", 200)
    par = _env_int("BASELINE_CONCURRENT_PAR", 50)
    master = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    # Fan out n async pings; cap concurrency at par.  Any individual
    # failure is ignored -- the surviving assert_reconnect decides
    # health.
    running: list[subprocess.Popen] = []
    for _ in range(n):
        if len(running) >= par:
            # Wait for the oldest to drain before launching more.
            running.pop(0).wait()
        running.append(
            subprocess.Popen(
                [
                    "docker",
                    "exec",
                    master,
                    "salt",
                    "--async",
                    "*",
                    "test.ping",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    # Drain the remainder.
    for proc in running:
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    fault_s = int(time.monotonic() - fault_start)

    window = RECOVER_STANDARD_SEC * 2
    notes = f"n={n} par={par} window={window}s"
    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=window,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 7: null-fault recovery-window tightness
# ---------------------------------------------------------------------------


def test_baseline_recovery_window_tightness(topology, request):
    """baseline_recovery_window_tightness -- 1 s SIGSTOP on the primary
    master, then assert the fleet is back inside 10 s (not the full
    default 180 s window).

    Catches an ``assert_reconnect`` that rubber-stamps the max window
    because it waits for the first 5 s poll iteration.  Uses
    :func:`sigstopped_container` so SIGCONT is guaranteed even if we
    abort mid-test.
    """
    label = "baseline_recovery_window_tightness"
    hold_sec = _env_int("BASELINE_TIGHT_HOLD_SEC", 1)
    window_sec = _env_int("BASELINE_TIGHT_WINDOW_SEC", 10)

    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, topology.spec.primary_master):
        time.sleep(hold_sec)
    fault_s = int(time.monotonic() - fault_start)

    notes = f"null_fault hold={hold_sec}s budget={window_sec}s"
    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=window_sec,
        notes=notes,
        item=request.node,
    )
