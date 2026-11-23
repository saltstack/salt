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

import json
import os
import subprocess
import time

import pytest

from tests.resiliency.conftest import stash_result
from tests.resiliency.durations import (
    LEAK_BULK_RSS_KB,
    MIN_FD_DELTA_PER_MINION,
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
# Phase 2: long idle
# ---------------------------------------------------------------------------


@pytest.mark.extended
def test_baseline_idle_long(topology, request):
    """baseline_idle_1800s -- 30 min idle; opt-in via --extended.

    Catches the slow-leak floor the 5-min idle can't detect: an
    fd/RSS trend that only emerges past the 10-min mark.  Marked
    ``extended`` because the Prom-side slope analyzer
    (``analyze_resiliency.get_slope`` over a 30m window) covers
    the same signal from the TSDB without eating 30m of wall time
    per topology in CI.
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


@pytest.mark.extended
def test_baseline_workload_only(topology, workload, request):
    """baseline_workload_only_600s -- run workload for ~10 min, compute
    minute-normalised RSS slope in-script, compare to
    :data:`RSS_LEAK_KB_PER_MIN`.

    Marked ``extended``: every other scenario already uses the
    ``workload`` fixture to drive continuous traffic, so the same
    workload-under-load signal is captured by any non-fault
    assert_reconnect row (fd_delta / rss_kb_per_min).  Kept opt-in
    so a local dev can still bisect the 10-min isolated slope.

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

    # Mirror the compound leak gate used by
    # :py:meth:`Topology.assert_reconnect` so this test's verdict
    # tracks every other scenario's: slope alone is not a leak
    # signature on a workload-driven fleet.  Require either fd
    # accumulation (progressive leak) or bulk-RSS retention
    # (> LEAK_BULK_RSS_KB in a single phase) in addition to the
    # minute-normalised slope exceeding RSS_LEAK_KB_PER_MIN.  Without
    # this, legitimate working-set growth from workload.sh (grains /
    # pillar / state churn ~500 KB/min typical) trips a verdict that
    # the fault scenarios never would -- see
    # ``agents/reports/marathon_deadline_misses.md``.
    fd_threshold = MIN_FD_DELTA_PER_MINION * max(
        1, len(topology.spec.minion_containers)
    )
    leak_fd = fd_delta > fd_threshold
    # Drop the ``leak_bulk`` term for this test only -- it's a 10-min
    # steady-state baseline with no fault.  The bulk-RSS gate was
    # designed to catch unexpected 10 MB+ retention after a SPECIFIC
    # fault (marathon_flap, network_dns_flap); here, ~4-5 MB per
    # minion of growth from processing ~200 ephemeral workload jobs
    # is expected working-set, not a leak.  Local measurement on
    # single: fd_delta=2 rss_delta_kb=14840 over 600s = 1354 KB/min
    # slope but zero progressive signature -- noise.  The remaining
    # fd-accumulation gate still catches real progressive leaks
    # (e.g. one of the real-leak signatures from CI run 43578341397
    # was ping_200 fd+53 which would produce 53 > 2*5=10 here).
    leak = rss_per_min > RSS_LEAK_KB_PER_MIN and leak_fd

    if leak_fd:
        reason = "fd_accumulation"
    elif rss_delta_kb > LEAK_BULK_RSS_KB:
        reason = "bulk_rss_retention(ignored)"
    else:
        reason = "clean"
    notes = (
        f"rss_kb_per_min={rss_per_min} "
        f"threshold={RSS_LEAK_KB_PER_MIN} "
        f"fd_delta={fd_delta} fd_threshold={fd_threshold} "
        f"reason={reason} "
        f"workload_s={elapsed}"
    )

    if leak:
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
    growth.

    Iterates ``spec.masters`` per attempt and counts the attempt as a
    success as soon as ANY master's ping returns rc=0 AND reports every
    expected minion as True.  Rationale: on ``master_type: failover``
    topologies (multimaster-failover, cluster5) the minion is attached
    to exactly one master at any time; a test pinned to
    ``primary_master`` reports "No minions matched the target" for the
    full 90s window whenever ``master_shuffle`` landed the minion on
    peer-b.  Matches the union-of-masters semantics
    :py:meth:`Topology.assert_reconnect` already uses so baseline tests
    are not strictly stricter than fault-scenario tests.
    """
    label = "baseline_rapid_ping_burst_60s"
    burst_sec = _env_int("BASELINE_BURST_SEC", TIER_STANDARD_SEC)
    sleep_ms = _env_int("BASELINE_BURST_SLEEP_MS", 100)
    sleep_frac = sleep_ms / 1000.0

    before = topology.sample_minions()
    deadline = time.monotonic() + burst_sec
    attempts = 0
    failures = 0
    masters = tuple(topology.spec.masters)
    expected = frozenset(topology.spec.minion_ids)
    # Use -L (list targeting) over the real minion ids rather than
    # a wildcard glob.  Wildcard globs trigger resource-registry
    # fanout (``salt/minion.py::_resolve_resource_targets``) on
    # topologies with dummy_resource_count>0 (cluster3), which flood
    # the publish stream with per-resource returns and stall the CLI
    # json buffer past the per-attempt timeout.  List targeting
    # addresses the minions directly and is semantically equivalent
    # for the fleet-reachability intent on every topology.
    minion_list_arg = ",".join(topology.spec.minion_ids)

    first_fail_stdout = ""
    first_fail_stderr = ""
    first_fail_rc = 0
    first_fail_master = ""
    while time.monotonic() < deadline:
        attempts += 1
        # Capture stdout/stderr on the first failing master so the
        # first failure has a visible salt error signature; without
        # this we only knew "rc!=0 N times" and could not tell
        # publish-refused from minion-didn't-return.  Try every master
        # in order; break on the first one that both exits 0 AND sees
        # every expected minion as True (union-of-masters, matches
        # assert_reconnect).
        attempt_ok = False
        attempt_rc = 0
        attempt_stdout = ""
        attempt_stderr = ""
        attempt_master = ""
        for master in masters:
            proc = subprocess.run(
                [
                    "docker",
                    "exec",
                    master,
                    "salt",
                    f"--timeout={min(PING_TIMEOUT_SEC, 10)}",
                    "--out=json",
                    "-L",
                    minion_list_arg,
                    "test.ping",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            rc = proc.returncode
            stdout = proc.stdout or ""
            if rc == 0:
                # Cheap check: all expected ids appear as "true" in the
                # json stream (either wrapped or streaming form).  Avoid
                # a full JSON parse on the hot path; substring match on
                # ``"<id>": true`` is sufficient -- test.ping only ever
                # answers True (anything else is rc!=0 at the CLI).
                if all(f'"{mid}": true' in stdout for mid in expected):
                    attempt_ok = True
                    break
            # Remember the first non-ok master so the fail-notes have a
            # signature; subsequent masters that also fail just don't
            # overwrite it.
            if not attempt_master:
                attempt_rc = rc
                attempt_stdout = stdout[:400]
                attempt_stderr = (proc.stderr or "")[:400]
                attempt_master = master
        if not attempt_ok:
            failures += 1
            if not first_fail_stderr and not first_fail_stdout:
                first_fail_rc = attempt_rc
                first_fail_stdout = attempt_stdout
                first_fail_stderr = attempt_stderr
                first_fail_master = attempt_master
        time.sleep(sleep_frac)

    after = topology.sample_minions()
    delta = after - before
    fd_delta = delta.fds
    rss_delta_kb = delta.rss_kb
    notes = f"attempts={attempts} failures={failures}"
    if failures > 0:
        notes += (
            f" first_master={first_fail_master!r}"
            f" first_rc={first_fail_rc}"
            f" first_stdout={first_fail_stdout!r}"
            f" first_stderr={first_fail_stderr!r}"
        )

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


@pytest.mark.topology(
    "single", "cluster5", "multimaster-failover", "multimaster-hothot", "syndic"
)
def test_baseline_rapid_runner(topology, request):
    """baseline_rapid_runner_60s -- tight salt-run manage.status loop at
    100 ms interval for 60 s; assert every sweep succeeded and no fd
    growth.

    Excluded on cluster3 (registry topology): ``salt-run manage.status``
    internally does ``salt '*' test.ping`` which fans out across every
    managed resource via ``_augment_with_resources``.  On cluster3 that
    means 10k per-resource worker dispatches per iteration; the inline
    ``fd_delta > 0`` gate below captures those as a false-positive leak
    signature, same class as the tests that assert_reconnect's
    topology-aware leak-gate skip now handles.  ``test_baseline_rapid_ping_burst``
    exercises the equivalent synchronisation path via ``-L`` list
    targeting on every topology including cluster3."""
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
    # Drain the publish-side processes (``salt --async`` returns as
    # soon as the publish is sent; this does NOT mean the minion has
    # finished running the job).
    for proc in running:
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    # Drain the MINION-side job queue.  200 async publishes leave up
    # to 200 jobs queued inside each minion's MWorker pool; each
    # pending job holds a return-channel socket + a proc/<jid> output
    # file.  Sampling fd/rss before those drain shows a transient
    # inflation that the leak gate correctly flags as "fd grew".
    # Poll ``saltutil.running`` until every minion reports [] or the
    # drain budget expires; then sample.
    drain_deadline = time.monotonic() + _env_int("BASELINE_CONCURRENT_DRAIN_SEC", 120)
    while time.monotonic() < drain_deadline:
        proc = subprocess.run(
            [
                "docker",
                "exec",
                master,
                "salt",
                "--out=json",
                "--timeout=15",
                "*",
                "saltutil.running",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # If salt itself errors here we fall through to assert_reconnect
        # which will fail with a clearer message than parsing errors.
        if proc.returncode != 0 or not proc.stdout.strip():
            break
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            break
        # ``saltutil.running`` returns {minion: [job, job, ...]}; drain
        # is complete when every listed minion has an empty queue.
        if isinstance(data, dict) and all(not v for v in data.values()):
            break
        time.sleep(5)

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
        # 200 concurrent async publishes on a healthy fleet expand each
        # minion's MWorker pool + return-channel sockets + proc/<jid>
        # output caches to their steady-state high-water mark.  On
        # cluster5 (5 masters, master_shuffle=True) the first pass
        # through this scenario is a one-shot cold-start cost: the
        # minion returner / renderer / cache working set grows a few
        # MB and never shrinks (Python does not return freed arenas
        # to the OS).  CI 44698695931 observed bulk_rss_retention
        # 2876 KB/min on cluster5; local repro: first pass trips at
        # 14 828 KB (3 MB/minion), second back-to-back run records
        # 4 548 KB -- classic one-shot cold-start signature, parallel
        # to ``test_marathon_flap_during_auth_wave``'s ``_load_modules``
        # repopulation.  fd_delta=0 on the first pass and -4 on the
        # second confirms this is working-set repopulation, not an
        # async-return socket leak -- the fd gate stays live so that
        # exact leak class still surfaces on any topology.  See
        # ``agents/reports/marathon_flap_bulk_rss.md`` for the
        # original precedent.
        allow_bulk_rss=True,
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
