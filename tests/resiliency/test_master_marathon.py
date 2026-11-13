"""Marathon-outage battery -- pytest port of ``scenarios/master_marathon.sh``.

These phases hold the master unreachable for 30 minutes to 2 hours while
the workload hammers it.  They catch long-outage auth-race bugs that
short faults never reproduce -- specifically the
``AsyncAuth._authenticate`` ``InvalidStateError`` class fixed in
upstream PR saltstack/salt#70772 (Broadcom Jira UBMVCFOPS-19586).

All phases are gated behind ``@pytest.mark.marathon`` which the resiliency
conftest skips unless ``--marathon`` was passed.  The 120-minute phase
has an additional ``MARATHON_120M`` env opt-in on top.

Phase -> test mapping (phase labels passed verbatim to
``assert_reconnect`` so results.jsonl rows stay compatible):

    marathon_outage_30m                 test_marathon_outage_30m
    marathon_outage_60m                 test_marathon_outage_60m
    marathon_outage_120m                test_marathon_outage_120m
    marathon_flap_during_auth_wave      test_marathon_flap_during_auth_wave

Every marathon test passes ``window_sec=RECOVER_MARATHON_SEC`` because
the default 180 s window is too tight for a minion that queued
thousands of retries during a multi-hour outage.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time

import pytest

from tests.resiliency.durations import (
    RECOVER_MARATHON_SEC,
    TIER_ACCUM_SEC,
    TIER_MARATHON_SEC,
    TIER_SUBKEEPALIVE_SEC,
    TIER_UPGRADE_SEC,
)

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict


# ---------------------------------------------------------------------------
# Phase 1: 30-minute outage
# ---------------------------------------------------------------------------


@pytest.mark.marathon
def test_marathon_outage_30m(topology, workload, request):
    """marathon_outage_30m -- docker stop primary master for
    ``TIER_ACCUM_SEC``, keep workload running, start, assert fleet
    recovers inside ``RECOVER_MARATHON_SEC``.
    """
    label = "marathon_outage_30m"
    hold = TIER_ACCUM_SEC
    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    topology.stop(primary, timeout_sec=30)
    try:
        time.sleep(hold)
    finally:
        topology.start(primary)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=RECOVER_MARATHON_SEC,
        notes=f"docker stop {primary} {hold}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: 60-minute outage
# ---------------------------------------------------------------------------


@pytest.mark.marathon
def test_marathon_outage_60m(topology, workload, request):
    """marathon_outage_60m -- same as 30m but with ``TIER_MARATHON_SEC``
    hold (nominally one hour).
    """
    label = "marathon_outage_60m"
    hold = TIER_MARATHON_SEC
    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    topology.stop(primary, timeout_sec=30)
    try:
        time.sleep(hold)
    finally:
        topology.start(primary)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=RECOVER_MARATHON_SEC,
        notes=f"docker stop {primary} {hold}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: 2-hour outage (extra env opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.marathon
@pytest.mark.skipif(
    os.environ.get("MARATHON_120M") != "1",
    reason="MARATHON_120M=0 (set to 1 to opt in on top of --marathon)",
)
def test_marathon_outage_120m(topology, workload, request):
    """marathon_outage_120m -- 2-hour outage.  Requires both
    ``--marathon`` and ``MARATHON_120M=1`` so the default marathon run
    doesn't cost 3.5 h by itself.
    """
    label = "marathon_outage_120m"
    hold = TIER_UPGRADE_SEC
    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    topology.stop(primary, timeout_sec=30)
    try:
        time.sleep(hold)
    finally:
        topology.start(primary)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=RECOVER_MARATHON_SEC,
        notes=f"docker stop {primary} {hold}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: flap-during-auth-wave
# ---------------------------------------------------------------------------


@pytest.mark.marathon
def test_marathon_flap_during_auth_wave(topology, workload, request):
    """marathon_flap_during_auth_wave -- the specific recipe that
    reproduces UBMVCFOPS-19586 inside minutes: fire concurrent
    auth-triggering calls (``saltutil.sync_all`` + ``test.ping``) from
    each minion while the master flaps.

    Pending auth requests accumulate during each stop window; the
    colliding result-set at the write site raises InvalidStateError on
    unfixed 3008.x.  On fixed code (saltstack/salt#70772 / #70713) every
    caller gets its own Future and the wave survives.
    """
    label = "marathon_flap_during_auth_wave"
    cycles = 30
    stop_sec = TIER_SUBKEEPALIVE_SEC
    up_sec = TIER_SUBKEEPALIVE_SEC
    primary = topology.spec.primary_master

    before = topology.sample_minions()

    # Spawn one tight-loop auth-waver per minion container.  Each one
    # does continuous salt-call --local test.ping + salt-call test.ping
    # + salt-call saltutil.sync_all; all wrapped in || true so a
    # transient master-down doesn't break the loop.  Each loop runs in
    # its own session (``start_new_session=True``) so the finalizer can
    # kill the whole process group cleanly without racing on reaped
    # children.
    loaders: list[subprocess.Popen] = []
    loader_cmd_tmpl = (
        "while true; do "
        "docker exec {m} salt-call --local test.ping >/dev/null 2>&1 || true; "
        "docker exec {m} salt-call test.ping >/dev/null 2>&1 || true; "
        "docker exec {m} salt-call saltutil.sync_all >/dev/null 2>&1 || true; "
        "done"
    )

    fault_s = 0
    try:
        for m in topology.spec.minion_containers:
            proc = subprocess.Popen(
                ["bash", "-c", loader_cmd_tmpl.format(m=m)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            loaders.append(proc)

        # Flap loop
        fault_start = time.monotonic()
        for _ in range(cycles):
            try:
                topology.stop(primary, timeout_sec=5)
            except Exception:  # noqa: BLE001 - mirror bash "|| true"
                pass
            time.sleep(stop_sec)
            try:
                topology.start(primary)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(up_sec)
        fault_s = int(time.monotonic() - fault_start)
    finally:
        # Terminate every auth-waver's process group so assert_reconnect
        # isn't fighting them for the master's MWorker pool.  SIGTERM
        # first, then SIGKILL anything still alive after a short grace.
        for p in loaders:
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception:  # noqa: BLE001
                pass
        for p in loaders:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except Exception:  # noqa: BLE001
                    pass
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        # Small quiet window so the lingering docker-exec children fully
        # exit before assert_reconnect starts its own ping sweeps.
        time.sleep(5)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        window_sec=RECOVER_MARATHON_SEC,
        notes=(
            f"cycles={cycles} stop={stop_sec}s up={up_sec}s " "auth_wavers=per_minion"
        ),
        item=request.node,
    )
