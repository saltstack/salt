"""Pytest port of ``tests/resiliency/scenarios/disk_faults.sh``.

Each phase exercises a different failure mode of the primary master's
local filesystem state (cachedir, logdir, pki) and, after the fault
clears, ``Topology.assert_reconnect`` verifies every minion in
``spec.minion_ids`` still answers ``test.ping`` within the recovery
window and that fd/RSS haven't crept past the thresholds encoded in
``durations.py``.

Phase labels (preserved verbatim from the bash scenario so the
``results.jsonl`` schema stays stable for the analyzer):

    disk_cache_enospc     fill /var/cache/salt/master via fallocate/dd
    disk_cache_readonly   mount -o remount,ro (chmod fallback) on cachedir
    disk_cache_slow_io    dd ``DISK_SLOW_MB`` pressure write on cachedir
    disk_log_fill         fill /var/log/salt via fallocate/dd
    disk_pki_readonly     chmod -R u-w on /etc/salt/pki/master

The cache_readonly and pki_readonly phases use the shared
``remounted_readonly`` injector from ``lib/injectors.py`` which already
tries mount-remount first and falls back to chmod -R u-w when
CAP_SYS_ADMIN is missing; it calls ``pytest.skip`` if both modes fail.

Env knobs (preserve bash defaults from disk_faults.sh):

    PHASE_DURATION_SEC    default: ``TIER_STANDARD_SEC``
    DISK_FILL_MB          default: 500  (enospc + log fill)
    DISK_SLOW_MB          default: 200  (slow-io direct-write)
"""

from __future__ import annotations

import os
import time

import pytest

from tests.resiliency.durations import TIER_STANDARD_SEC
from tests.resiliency.lib.injectors import filled_filesystem, remounted_readonly

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


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
DISK_FILL_MB = _env_int("DISK_FILL_MB", 500)
DISK_SLOW_MB = _env_int("DISK_SLOW_MB", 200)


MASTER_CACHEDIR = "/var/cache/salt/master"
MASTER_LOGDIR = "/var/log/salt"
MASTER_PKIDIR = "/etc/salt/pki/master"


# ---------------------------------------------------------------------------
# Phase 1: cachedir ENOSPC
# ---------------------------------------------------------------------------


def test_disk_cache_enospc(topology, workload, request):
    """Fill the master cachedir and hold PHASE_DURATION_SEC."""
    scenario = "disk_cache_enospc"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    with filled_filesystem(
        topology,
        primary,
        MASTER_CACHEDIR,
        size_mb=DISK_FILL_MB,
    ):
        time.sleep(PHASE_DURATION_SEC)

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"method=fallocate size={DISK_FILL_MB}M",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: cachedir read-only
# ---------------------------------------------------------------------------


def test_disk_cache_readonly(topology, workload, request):
    """Remount the master cachedir read-only (chmod fallback)."""
    scenario = "disk_cache_readonly"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    with remounted_readonly(topology, primary, MASTER_CACHEDIR):
        time.sleep(PHASE_DURATION_SEC)

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"remount_ro {MASTER_CACHEDIR}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: slow-I/O proxy -- direct-io write to pressure the buffer cache
# ---------------------------------------------------------------------------


def test_disk_cache_slow_io(topology, workload, request):
    """dd DISK_SLOW_MB with oflag=direct on the cachedir (buffered fallback)."""
    scenario = "disk_cache_slow_io"
    primary = topology.spec.primary_master

    slow_file = f"{MASTER_CACHEDIR}/__resiliency_pressure"

    before = topology.sample_minions()

    applied = False
    direct_cmd = (
        f"sync; dd if=/dev/zero of='{slow_file}' bs=1M count={DISK_SLOW_MB} "
        "oflag=direct 2>/dev/null"
    )
    direct_proc = topology.exec(primary, "sh", "-c", direct_cmd, check=False)
    if direct_proc.returncode == 0:
        applied = True
        notes = f"dd {DISK_SLOW_MB}M oflag=direct"
    else:
        # Retry without oflag=direct (tmpfs/overlayfs reject direct io).
        buffered_cmd = (
            f"sync; dd if=/dev/zero of='{slow_file}' bs=1M count={DISK_SLOW_MB} "
            "2>/dev/null"
        )
        buf_proc = topology.exec(primary, "sh", "-c", buffered_cmd, check=False)
        if buf_proc.returncode == 0:
            applied = True
            notes = f"dd {DISK_SLOW_MB}M buffered"
        else:
            notes = ""

    if not applied:
        pytest.skip(
            f"unable to write pressure file in {primary}:{MASTER_CACHEDIR}; "
            "cachedir may be full or readonly"
        )

    try:
        time.sleep(PHASE_DURATION_SEC)
    finally:
        topology.exec(
            primary,
            "sh",
            "-c",
            f"rm -f '{slow_file}' 2>/dev/null || true",
            check=False,
        )

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=notes,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: /var/log/salt fill
# ---------------------------------------------------------------------------


def test_disk_log_fill(topology, workload, request):
    """Fill the master logdir via fallocate/dd."""
    scenario = "disk_log_fill"
    primary = topology.spec.primary_master

    # Guard: the injector will skip if dir missing, but the bash scenario
    # produced a setup_error specifically for a missing logdir -- keep that
    # behaviour by probing first.
    probe = topology.exec(
        primary,
        "sh",
        "-c",
        f"[ -d '{MASTER_LOGDIR}' ]",
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip(f"{MASTER_LOGDIR} does not exist on {primary}")

    before = topology.sample_minions()
    with filled_filesystem(
        topology,
        primary,
        MASTER_LOGDIR,
        size_mb=DISK_FILL_MB,
    ):
        time.sleep(PHASE_DURATION_SEC)

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"fill {DISK_FILL_MB}M in {MASTER_LOGDIR}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: PKI read-only -- exercise auth-cache reload path
# ---------------------------------------------------------------------------


def test_disk_pki_readonly(topology, workload, request):
    """chmod -R u-w on /etc/salt/pki/master (or remount ro if available)."""
    scenario = "disk_pki_readonly"
    primary = topology.spec.primary_master

    probe = topology.exec(
        primary,
        "sh",
        "-c",
        f"[ -d '{MASTER_PKIDIR}' ]",
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip(f"{MASTER_PKIDIR} not present on {primary}")

    before = topology.sample_minions()
    with remounted_readonly(topology, primary, MASTER_PKIDIR):
        time.sleep(PHASE_DURATION_SEC)

    topology.assert_reconnect(
        scenario,
        fault_sec=PHASE_DURATION_SEC,
        before=before,
        notes=f"chmod -R u-w {MASTER_PKIDIR}",
        item=request.node,
    )
