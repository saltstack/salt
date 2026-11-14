"""Pytest port of ``tests/resiliency/scenarios/clock_skew.sh``.

Walks minion and master containers through forward / backward clock
jumps (small and large) and a mid-auth skew race.  After each phase the
clock is restored and ``Topology.assert_reconnect`` verifies every
minion in ``spec.minion_ids`` still answers ``test.ping`` within the
recovery window and that fd/RSS haven't crept past the thresholds
encoded in ``durations.py``.

Phase labels (preserved verbatim from the bash scenario so the
``results.jsonl`` schema stays stable for the analyzer):

    clock_minion_fwd_60s         first minion: date -s '+60s'
    clock_minion_back_300s       first minion: date -s '-5m'
    clock_master_fwd_60s         primary master: date -s '+60s'
    clock_master_back_3600s      primary master: date -s '-1h'
    clock_drift_during_auth      first minion: +120s during docker restart

The signed deltas (+60, -300, +60, -3600, +120) are part of the label
semantics: they're baked into the label itself and are kept exact.

Capabilities each phase needs:

    phases 1-5: CAP_SYS_TIME inside the target container so ``date -s``
    actually changes the kernel clock.  If the container shares the
    host clock (typical for docker without CAP_SYS_TIME), ``date -s``
    fails or silently no-ops; we detect that by re-reading the clock
    and ``pytest.skip`` with reason.

Env knobs (preserve bash defaults from clock_skew.sh):

    PHASE_DURATION_SEC    default: ``TIER_STANDARD_SEC``
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from tests.resiliency.durations import TIER_STANDARD_SEC

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


log = logging.getLogger("resiliency.clock_skew")


# ---------------------------------------------------------------------------
# Env knobs
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


PHASE_DURATION_SEC = _env_int("PHASE_DURATION_SEC", TIER_STANDARD_SEC)


# ---------------------------------------------------------------------------
# Clock probe / mutation helpers
# ---------------------------------------------------------------------------


def _container_epoch(topology, container: str) -> int | None:
    """Read current UTC epoch inside ``container``; ``None`` on error."""
    proc = topology.exec(
        container,
        "sh",
        "-c",
        "date -u +%s",
        check=False,
    )
    if proc.returncode != 0:
        return None
    raw = (proc.stdout or "").strip()
    try:
        return int(raw)
    except ValueError:
        return None


def _set_container_epoch(topology, container: str, epoch: int) -> bool:
    """``date -u -s @<epoch>`` inside ``container``.  True on exit-0."""
    proc = topology.exec(
        container,
        "sh",
        "-c",
        f"date -u -s '@{epoch}' >/dev/null 2>&1",
        check=False,
    )
    return proc.returncode == 0


def _can_set_clock(topology, container: str) -> bool:
    """Probe whether ``date -s`` actually moves the clock in ``container``.

    Pushes the clock +5s, re-reads, then restores to host UTC.  Returns
    True iff the forward move took effect (>=3s delta tolerates rounding).
    Mirrors ``can_set_clock`` in clock_skew.sh.
    """
    before = _container_epoch(topology, container)
    if before is None:
        return False
    host_now = int(time.time())
    if not _set_container_epoch(topology, container, host_now + 5):
        return False
    after = _container_epoch(topology, container)
    # Restore to host UTC regardless of whether the probe worked.
    _set_container_epoch(topology, container, int(time.time()))
    if after is None:
        return False
    return after >= before + 3


def _apply_skew(topology, container: str, delta: int) -> bool:
    """Apply a signed skew (seconds) relative to host wall clock."""
    target = int(time.time()) + delta
    return _set_container_epoch(topology, container, target)


def _restore_clock(topology, container: str) -> None:
    """Restore container clock to host UTC.  Best-effort."""
    # hwclock -s is a noop on most containers but cheap.
    topology.exec(container, "sh", "-c", "hwclock -s 2>/dev/null", check=False)
    _set_container_epoch(topology, container, int(time.time()))


@contextmanager
def _clock_skewed(topology, container: str, delta: int) -> Iterator[None]:
    """Context manager: apply ``delta`` skew on enter, restore on exit.

    Probes CAP_SYS_TIME first; ``pytest.skip`` if ``date -s`` can't move
    the clock.  Guarantees the clock is restored even on exception.
    """
    if not _can_set_clock(topology, container):
        pytest.skip(f"CAP_SYS_TIME unavailable in {container}")

    if not _apply_skew(topology, container, delta):
        pytest.skip(f"apply_skew({delta}s) failed on {container} after probe succeeded")

    try:
        yield
    finally:
        _restore_clock(topology, container)


# ---------------------------------------------------------------------------
# Phases 1-4: simple skew / hold / restore
# ---------------------------------------------------------------------------


def _first_minion(topology) -> str:
    return topology.spec.minion_containers[0]


def test_clock_minion_fwd_60s(topology, workload, request):
    scenario = "clock_minion_fwd_60s"
    container = _first_minion(topology)
    before = topology.sample_minions()
    with _clock_skewed(topology, container, 60):
        time.sleep(PHASE_DURATION_SEC)
    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"skew +60s on {container}",
        item=request.node,
    )


def test_clock_minion_back_300s(topology, workload, request):
    scenario = "clock_minion_back_300s"
    container = _first_minion(topology)
    before = topology.sample_minions()
    with _clock_skewed(topology, container, -300):
        time.sleep(PHASE_DURATION_SEC)
    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"skew -300s on {container}",
        item=request.node,
    )


def test_clock_master_fwd_60s(topology, workload, request):
    scenario = "clock_master_fwd_60s"
    container = topology.spec.primary_master
    before = topology.sample_minions()
    with _clock_skewed(topology, container, 60):
        time.sleep(PHASE_DURATION_SEC)
    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"skew +60s on {container}",
        item=request.node,
    )


def test_clock_master_back_3600s(topology, workload, request):
    """-3600s on primary master; tests mWorker monotonic-vs-wall key
    rotation handling."""
    scenario = "clock_master_back_3600s"
    container = topology.spec.primary_master
    before = topology.sample_minions()
    with _clock_skewed(topology, container, -3600):
        time.sleep(PHASE_DURATION_SEC)
    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"skew -3600s on {container}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: clock drift during auth
#
# Restart the first minion container AND skew its clock +120s before
# salt-minion finishes authing to the master.  We approximate the race:
# fire ``docker restart`` async, poll for ``State.Running=true`` (usually
# a few hundred ms), and immediately apply the skew.  Skip if the
# container doesn't honour ``date -s`` (CAP_SYS_TIME missing) or if the
# race window is too tight.
# ---------------------------------------------------------------------------


def test_clock_drift_during_auth(topology, workload, request):
    scenario = "clock_drift_during_auth"
    container = _first_minion(topology)

    # Probe first so we distinguish "race missed" from "no CAP_SYS_TIME".
    if not _can_set_clock(topology, container):
        pytest.skip(f"CAP_SYS_TIME unavailable in {container}")

    before = topology.sample_minions()

    # Restart in the background by invoking topology.restart via a thread
    # so we can race against ``State.Running``.  topology.restart itself
    # blocks until docker restart returns, so we thread it.
    import threading

    restart_err: list[BaseException] = []

    def _restart_worker() -> None:
        try:
            topology.restart(container)
        except BaseException as exc:  # noqa: BLE001
            restart_err.append(exc)

    worker = threading.Thread(target=_restart_worker, daemon=True)
    worker.start()

    # Wait for the container to transition back to Running=true.  dockerd
    # cycles through "restarting", so spin on State.Running.
    deadline = time.monotonic() + 30
    skew_applied = False
    while time.monotonic() < deadline:
        if topology.inspect_running(container):
            if _apply_skew(topology, container, 120):
                skew_applied = True
            break
        # Tight loop; sub-second resolution matters for the race.
        time.sleep(0.1)

    # Make sure the restart worker finished even if we broke out early.
    worker.join(timeout=60)

    if not skew_applied:
        pytest.skip(
            "unable to apply skew within 30s of restart; race may be "
            f"impractical on this host (restart_err={restart_err!r})"
        )

    try:
        time.sleep(PHASE_DURATION_SEC)
    finally:
        _restore_clock(topology, container)

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes="skew +120s applied during post-restart auth window",
        item=request.node,
    )
