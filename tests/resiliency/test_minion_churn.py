"""Minion-churn resiliency battery.

Port of ``tests/resiliency/scenarios/minion_churn.sh`` to pytest.

Phases (one JSONL row each):

    * ``test_minion_churn_single_restart``     -- restart the first minion
    * ``test_minion_churn_rolling[ctr]``       -- parametrized, one per minion
    * ``test_minion_churn_simultaneous``       -- parallel restart of all minions
    * ``test_minion_churn_kill9``              -- SIGKILL + docker start
    * ``test_minion_churn_stop_start``         -- docker stop + STOP_DURATION_SEC
                                                   gap + docker start
    * ``test_minion_churn_hothot_both_restart`` -- restart one master AND
                                                   the single minion in
                                                   parallel; only runs on
                                                   ``multimaster-hothot``,
                                                   other topologies skip via
                                                   the ``topology`` marker,
                                                   which conftest records as
                                                   ``skipped_for_topology``

Rolling parametrize strategy: this module defines
``pytest_generate_tests`` which reads the ``--topology`` CLI flag and
calls ``lib.topology.load_topology`` (pure data; no side effects) to
expand ``minion`` across ``spec.minion_containers`` at collection time.
One parametrize id per minion yields one JSONL row per step, matching
the bash ``minion_churn_rolling_<ctr>`` labels exactly.

Env knobs preserved from the bash script:

    INTER_MINION_WAIT_SEC   default ``PACING_ROLLING_SEC``
    STOP_DURATION_SEC       default ``TIER_STANDARD_SEC``
    KILL_RESTART_DELAY_SEC  default 2
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from tests.resiliency.durations import PACING_ROLLING_SEC, TIER_STANDARD_SEC
from tests.resiliency.lib.topology import load_topology

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from minion_churn.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


INTER_MINION_WAIT_SEC = _env_int("INTER_MINION_WAIT_SEC", PACING_ROLLING_SEC)
STOP_DURATION_SEC = _env_int("STOP_DURATION_SEC", TIER_STANDARD_SEC)
KILL_RESTART_DELAY_SEC = _env_int("KILL_RESTART_DELAY_SEC", 2)


# ---------------------------------------------------------------------------
# Collection-time parametrize of rolling tests
# ---------------------------------------------------------------------------


def pytest_generate_tests(metafunc):
    """Expand ``minion`` parametrize from the active --topology."""
    if "minion" in metafunc.fixturenames:
        topo_name = metafunc.config.getoption("--topology")
        spec = load_topology(topo_name)
        metafunc.parametrize(
            "minion",
            [pytest.param(m, id=m) for m in spec.minion_containers],
        )


# ---------------------------------------------------------------------------
# Phase 1: single-minion graceful restart
# ---------------------------------------------------------------------------


def test_minion_churn_single_restart(topology, workload, request):
    scenario = "minion_churn_single_restart"
    target = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(target)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: rolling restart -- parametrized over spec.minion_containers
# ---------------------------------------------------------------------------


def test_minion_churn_rolling(topology, workload, request, minion):
    scenario = f"minion_churn_rolling_{minion}"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(minion)
    # Mirror the bash scenario: pause between the restart and the ping
    # assertion so the minion has time to come back and re-auth before
    # we expect it to answer.  bash slept INTER_MINION_WAIT_SEC inside
    # the loop body BEFORE assert_reconnect, so we do the same.
    time.sleep(INTER_MINION_WAIT_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: simultaneous restart of every minion
# ---------------------------------------------------------------------------


def _docker_restart_bg(container: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["docker", "restart", container],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_minion_churn_simultaneous(topology, workload, request):
    scenario = "minion_churn_simultaneous"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    procs = [_docker_restart_bg(m) for m in topology.spec.minion_containers]
    for p in procs:
        p.wait()

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: SIGKILL one minion then restart it
# ---------------------------------------------------------------------------


def test_minion_churn_kill9(topology, workload, request):
    scenario = "minion_churn_kill9"
    target = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.kill_signal(target, "KILL")
    time.sleep(KILL_RESTART_DELAY_SEC)
    topology.start(target)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: hard pause -- stop, wait STOP_DURATION_SEC, start
# ---------------------------------------------------------------------------


def test_minion_churn_stop_start(topology, workload, request):
    scenario = "minion_churn_stop_start"
    target = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.stop(target, timeout_sec=30)
    time.sleep(STOP_DURATION_SEC)
    topology.start(target)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: multimaster-hothot ONLY -- restart one master AND the minion
# in parallel.  On every other topology this test is skipped by the
# ``topology`` marker, which conftest records as ``skipped_for_topology``.
# ---------------------------------------------------------------------------


@pytest.mark.topology("multimaster-hothot")
def test_minion_churn_hothot_both_restart(topology, workload, request):
    scenario = "minion_churn_hothot_both_restart"
    master_target = topology.spec.masters[0]
    minion_target = topology.spec.minion_containers[0]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    mp = _docker_restart_bg(master_target)
    np_ = _docker_restart_bg(minion_target)
    mp.wait()
    np_.wait()

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        notes="both_legs_required",
        item=request.node,
    )
