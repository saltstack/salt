"""Master-restart resiliency battery.

Port of ``tests/resiliency/scenarios/master_restart.sh`` to pytest.

Every phase mirrors the bash scenario one-for-one:

    * ``test_master_restart_sigterm``        -- docker stop (SIGTERM + 30s grace)
    * ``test_master_restart_sigkill``        -- docker kill --signal=KILL
    * ``test_master_restart_docker_restart`` -- docker restart (stop + start)
    * ``test_master_restart_rolling[ctr]``   -- parametrized, one per master;
                                                skipped on single-master topos
    * ``test_master_restart_simultaneous``   -- parallel docker restart of all
                                                masters; skipped on single-master

Each phase:
  1. Snapshots the per-minion fd/rss baseline.
  2. Injects the fault.
  3. Sleeps ``RESTART_IDLE_SEC`` where applicable.
  4. Waits for the master container to be Running=true again.
  5. Calls ``topology.assert_reconnect`` which records one JSONL row.

Env knobs preserved from the bash script:

    RESTART_IDLE_SEC       default: ``TIER_SUBKEEPALIVE_SEC``
    INTER_MASTER_WAIT_SEC  default: ``PACING_ROLLING_SEC`` (rolling pacing)
    INTER_PHASE_WAIT_SEC   default: ``PACING_INTER_PHASE_SEC`` (unused in
                           pytest; each test is its own phase so pytest's
                           own setup/teardown cadence is the pacing)

Rolling parametrize strategy: this module defines
``pytest_generate_tests`` which reads the CLI ``--topology`` option and
calls ``lib.topology.load_topology`` (a pure function) to resolve
``spec.masters`` at collection time.  Each master becomes its own
parametrize id, which means one JSONL row per master -- exactly what the
bash ``master_restart_rolling_<ctr>`` label expansion produced.
"""

from __future__ import annotations

import os
import subprocess
import time

import pytest

from tests.resiliency.durations import (
    PACING_INTER_PHASE_SEC,
    PACING_ROLLING_SEC,
    TIER_SUBKEEPALIVE_SEC,
)
from tests.resiliency.lib.topology import load_topology

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from master_restart.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


RESTART_IDLE_SEC = _env_int("RESTART_IDLE_SEC", TIER_SUBKEEPALIVE_SEC)
INTER_MASTER_WAIT_SEC = _env_int("INTER_MASTER_WAIT_SEC", PACING_ROLLING_SEC)
INTER_PHASE_WAIT_SEC = _env_int("INTER_PHASE_WAIT_SEC", PACING_INTER_PHASE_SEC)


# ---------------------------------------------------------------------------
# Collection-time parametrize of rolling tests
# ---------------------------------------------------------------------------


def pytest_generate_tests(metafunc):
    """Expand ``master`` parametrize from the active --topology.

    ``load_topology`` is pure data (no docker side effects), so it's safe
    to call at collection time to size the rolling parametrize.
    """
    if "master" in metafunc.fixturenames:
        topo_name = metafunc.config.getoption("--topology")
        spec = load_topology(topo_name)
        if spec.master_count <= 1:
            # Still produce one id so the test is collected and the
            # conftest skip-with-reason records a skipped_for_topology
            # JSONL row.  The test body will pytest.skip.
            metafunc.parametrize(
                "master",
                [pytest.param(spec.primary_master, id=spec.primary_master)],
            )
        else:
            metafunc.parametrize(
                "master",
                [pytest.param(m, id=m) for m in spec.masters],
            )


# ---------------------------------------------------------------------------
# Helpers (shared across phases)
# ---------------------------------------------------------------------------


def _wait_container_running(container: str, timeout: int = 120) -> bool:
    """Poll ``docker inspect`` until ``.State.Running`` is true.

    We can't use any in-container salt CLI here: during the fault
    window the master is down, so the query would block.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip().lower() == "true":
            return True
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Phase 1: graceful SIGTERM
# ---------------------------------------------------------------------------


def test_master_restart_sigterm(topology, workload, request):
    scenario = "master_restart_sigterm"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.stop(primary, timeout_sec=30)
    time.sleep(RESTART_IDLE_SEC)
    topology.start(primary)

    if not _wait_container_running(primary):
        pytest.fail(f"{scenario}: {primary} did not reach Running=true within 120s")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: SIGKILL
# ---------------------------------------------------------------------------


def test_master_restart_sigkill(topology, workload, request):
    scenario = "master_restart_sigkill"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.kill_signal(primary, "KILL")
    time.sleep(RESTART_IDLE_SEC)
    topology.start(primary)

    if not _wait_container_running(primary):
        pytest.fail(f"{scenario}: {primary} did not reach Running=true within 120s")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: docker restart
# ---------------------------------------------------------------------------


def test_master_restart_docker_restart(topology, workload, request):
    scenario = "master_restart_docker_restart"
    primary = topology.spec.primary_master

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(primary)

    if not _wait_container_running(primary):
        pytest.fail(f"{scenario}: {primary} did not reach Running=true within 120s")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: rolling restart -- parametrized over spec.masters
# ---------------------------------------------------------------------------


def test_master_restart_rolling(topology, workload, request, master):
    if topology.spec.master_count <= 1:
        pytest.skip("single-master topology")

    scenario = f"master_restart_rolling_{master}"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(master)

    if not _wait_container_running(master):
        pytest.fail(f"{scenario}: {master} did not reach Running=true within 120s")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )

    # Pace between rolling steps so a slow reconnect for master N doesn't
    # bleed into the baseline for master N+1.  Bash scenario did this
    # inside its for-loop; pytest spreads it across test boundaries.
    time.sleep(INTER_MASTER_WAIT_SEC)


# ---------------------------------------------------------------------------
# Phase 5: simultaneous restart of every master
# ---------------------------------------------------------------------------


def _docker_restart_bg(container: str) -> subprocess.Popen:
    """Launch ``docker restart`` in the background; caller must ``.wait()``."""
    return subprocess.Popen(
        ["docker", "restart", container],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_master_restart_simultaneous(topology, workload, request):
    if topology.spec.master_count <= 1:
        pytest.skip("single-master topology")

    scenario = "master_restart_simultaneous"

    before = topology.sample_minions()
    fault_start = time.monotonic()

    procs = [_docker_restart_bg(m) for m in topology.spec.masters]
    failures: list[str] = []
    for m, p in zip(topology.spec.masters, procs):
        rc = p.wait()
        if rc != 0:
            failures.append(f"{m}=rc{rc}")
    if failures:
        pytest.fail(
            f"{scenario}: one or more docker restart commands failed: "
            + ", ".join(failures)
        )

    not_up = [m for m in topology.spec.masters if not _wait_container_running(m)]
    if not_up:
        pytest.fail(f"{scenario}: masters did not return to Running=true: {not_up}")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        scenario,
        fault_sec,
        before,
        item=request.node,
    )
