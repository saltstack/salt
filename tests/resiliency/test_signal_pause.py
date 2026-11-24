"""Signal / pause battery -- pytest port of ``scenarios/signal_pause.sh``.

Each test injects a different signal-driven disturbance on a master or
minion container, then calls :py:meth:`Topology.assert_reconnect` to
verify every minion in ``spec.minion_ids`` answers ``test.ping`` within
the standard window and that fd/rss haven't ballooned.

Phase -> test mapping (phase labels are passed verbatim to
``assert_reconnect`` so results.jsonl rows stay compatible with the
analyzer):

    signal_sigstop_master_30s         test_signal_sigstop_master_30s
    signal_sigstop_master_120s        test_signal_sigstop_master_120s
    signal_sigstop_minion             test_signal_sigstop_minion
    signal_sighup_master              test_signal_sighup_master
    signal_sigusr1_master             test_signal_sigusr1_master
    signal_kill_mworker               test_signal_kill_mworker
    signal_kill_publisher             test_signal_kill_publisher
    signal_rolling_sigstop_cluster    test_signal_rolling_sigstop_cluster
"""

from __future__ import annotations

import os
import time

import pytest

from tests.resiliency.durations import (
    TIER_DEEPREC_SEC,
    TIER_FIRSTMISS_SEC,
    TIER_STANDARD_SEC,
)
from tests.resiliency.lib.injectors import sigstopped_container

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict


def _int_env(name: str, default: int) -> int:
    """Honor bash env-knob overrides.  Scenario tests take their fault
    hold from these on a per-run basis; defaults track the tier table.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Phase 1: short SIGSTOP on the primary master (GC-pause analogue)
# ---------------------------------------------------------------------------


def test_signal_sigstop_master_30s(topology, request):
    """signal_sigstop_master_30s -- SIGSTOP primary master for the
    ``TIER_FIRSTMISS_SEC`` window, then SIGCONT.  Simulates a short
    stop-the-world event just past the first keepalive miss.
    """
    label = "signal_sigstop_master_30s"
    hold = _int_env("SIGSTOP_SHORT_SEC", TIER_FIRSTMISS_SEC)
    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, topology.spec.primary_master):
        time.sleep(hold)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        notes=f"hold={hold}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: long SIGSTOP on the primary master (past master_alive_interval)
# ---------------------------------------------------------------------------


def test_signal_sigstop_master_120s(topology, request):
    """signal_sigstop_master_120s -- SIGSTOP primary master for the
    ``TIER_DEEPREC_SEC`` window, well past the master_alive_interval."""
    label = "signal_sigstop_master_120s"
    hold = _int_env("SIGSTOP_LONG_SEC", TIER_DEEPREC_SEC)
    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, topology.spec.primary_master):
        time.sleep(hold)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        notes=f"hold={hold}s",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: SIGSTOP the first minion container
# ---------------------------------------------------------------------------


def test_signal_sigstop_minion(topology, request):
    """signal_sigstop_minion -- SIGSTOP the first minion container for
    the ``TIER_STANDARD_SEC`` window, then SIGCONT.  Verifies that the
    minion rejoins the fleet once unpaused.
    """
    label = "signal_sigstop_minion"
    hold = _int_env("SIGSTOP_MINION_SEC", TIER_STANDARD_SEC)
    first_minion = topology.spec.minion_containers[0]
    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, first_minion):
        time.sleep(hold)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        notes=f"hold={hold}s container={first_minion}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 4: SIGHUP on the primary master -- config reload, no restart
# ---------------------------------------------------------------------------


def test_signal_sighup_master(topology, request):
    """signal_sighup_master -- send SIGHUP to the primary master.

    salt-master installs no SIGHUP handler (``salt/scripts.py`` wires
    one only on the minion side for in-process config reload), so the
    signal takes Python's default disposition and terminates the
    master; once tini loses its direct child the container exits.
    This test exercises the operator-recoverable "master was hit by a
    stray SIGHUP" scenario: revive the container and verify the fleet
    reconnects cleanly.  If a future salt change adds in-process
    SIGHUP reload, this test should be re-cast to the no-fault
    variant.
    """
    label = "signal_sighup_master"
    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    topology.kill_signal(primary, "HUP")
    # tini propagates SIGHUP to its child; give the process a moment
    # to exit so ``inspect_running`` sees the terminal state rather
    # than racing the exit code.  Then revive unconditionally -- an
    # already-running container just no-ops at ``docker start``.
    time.sleep(2)
    if not topology.inspect_running(primary):
        topology.start(primary)
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        item=request.node,
        # Cold-starting the master re-runs ``_load_modules()`` + spawns
        # a fresh MWorker pool and minions re-auth over the new auth
        # channel; the bulk-RSS ramp + fd spike that result are
        # legitimate cold-start cost, not retention.  Same rationale
        # as the minion cold-restart tests in test_minion_churn.py.
        allow_fault_rss=True,
    )


# ---------------------------------------------------------------------------
# Phase 5: SIGUSR1 on the primary master -- Salt dumps internal state
# ---------------------------------------------------------------------------


def test_signal_sigusr1_master(topology, request):
    """signal_sigusr1_master -- send SIGUSR1 so Salt dumps its internal
    state.  Verify the master doesn't crash and minions remain reachable.
    """
    label = "signal_sigusr1_master"
    primary = topology.spec.primary_master
    # The prior ``test_signal_sighup_master`` terminates this
    # container; ``_ensure_primary_alive`` revives it before this test
    # runs, but a ``docker start`` returns well before
    # ``salt.master.Master.start`` has reached
    # ``enable_sigusr1_handler()``.  A SIGUSR1 that lands before the
    # handler is installed takes Python's default disposition and
    # terminates the master -- not a salt regression, just a startup
    # race.  Gate on an MWorker being visible, which proves the handler
    # is wired (ProcessManager spawns workers in the same start()
    # frame, immediately after the handler registration).
    if not topology.wait_master_ready(primary, timeout=60):
        pytest.fail(
            f"{label}: {primary} did not spawn any MWorker-* child within 60s "
            "(SIGUSR1 handler would not be installed yet)"
        )
    before = topology.sample_minions()
    fault_start = time.monotonic()
    topology.kill_signal(primary, "USR1")
    # Give Salt a moment to write its state dump; still inside the
    # reconnect window so it counts as part of the fault.
    time.sleep(5)
    if not topology.inspect_running(primary):
        pytest.fail(f"{label}: {primary} not Running=true after SIGUSR1")
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: SIGKILL one MWorker-* child; master should respawn it
# ---------------------------------------------------------------------------


def test_signal_kill_mworker(topology, request):
    """signal_kill_mworker -- SIGKILL one ``MWorker-`` child on the
    primary master; the master process manager must respawn it and the
    fleet must stay healthy.
    """
    label = "signal_kill_mworker"
    primary = topology.spec.primary_master
    # If the prior signal_* test terminated the master,
    # ``_ensure_primary_alive`` will have revived it -- but a freshly-
    # started master takes a few seconds to spawn its MWorker pool,
    # and ``pkill -f MWorker-`` returning exit 1 on an empty match
    # would surface as a ``CalledProcessError`` here, masking the
    # real regression this test is meant to catch (does the process
    # manager respawn a single downed worker?).
    if not topology.wait_master_ready(primary, timeout=60):
        pytest.fail(f"{label}: {primary} did not spawn any MWorker-* child within 60s")
    before = topology.sample_minions()
    fault_start = time.monotonic()
    # -n picks the newest matching PID so we kill ONE worker, not all.
    # Bash signal_pause.sh is explicit on this: killing the whole pool
    # at once tests a different hypothesis (can the master survive
    # losing every worker concurrently?) than the regression gate
    # (does the process manager respawn a single downed worker?).
    topology.exec(primary, "pkill", "-SIGKILL", "-n", "-f", "MWorker-")
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 7: SIGKILL the PubServerChannel / EventPublisher child
# ---------------------------------------------------------------------------


def test_signal_kill_publisher(topology, request):
    """signal_kill_publisher -- SIGKILL the PubServerChannel /
    EventPublisher child; supervisor-owned so it must respawn.
    """
    label = "signal_kill_publisher"
    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    # Kill ONE publisher-side child (newest match); bash scenario walks
    # three patterns in order and kills the first found so it always
    # kills one child, not multiple.
    for pattern in (
        "PubServerChannel._publish_daemon",
        "PubServerChannel",
        "EventPublisher",
    ):
        rc = topology.exec(
            primary,
            "pkill",
            "-SIGKILL",
            "-n",
            "-f",
            pattern,
            check=False,
        )
        if rc.returncode == 0:
            break
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 8: rolling SIGSTOP across every master (cluster / multimaster)
# ---------------------------------------------------------------------------


@pytest.mark.topology(
    "cluster3",
    "cluster5",
    "multimaster-failover",
    "multimaster-hothot",
    "syndic",
)
def test_signal_rolling_sigstop_cluster(topology, request):
    """signal_rolling_sigstop_cluster -- SIGSTOP each master in forward
    order holding ``TIER_STANDARD_SEC`` each, then SIGCONT in reverse
    order.  Proves the fleet rides out a cascading pause front.

    Only meaningful on topologies with >1 master; the topology marker
    skips single-master invocations.
    """
    label = "signal_rolling_sigstop_cluster"
    masters = tuple(topology.spec.masters)
    per_hold = _int_env("SIGSTOP_ROLLING_SEC", TIER_STANDARD_SEC)
    before = topology.sample_minions()
    fault_start = time.monotonic()
    stopped: list[str] = []
    try:
        for m in masters:
            topology.kill_signal(m, "STOP")
            # Prepend so the reverse-order SIGCONT below is a plain forward
            # iteration over ``stopped``.
            stopped.insert(0, m)
            time.sleep(per_hold)
    finally:
        # SIGCONT in reverse order (LIFO via the prepended ``stopped``).
        for m in stopped:
            try:
                topology.kill_signal(m, "CONT")
            except Exception:  # noqa: BLE001 - belt-and-braces
                pass
    fault_s = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_s,
        before=before,
        notes=f"masters={len(masters)} per_hold={per_hold}s",
        item=request.node,
    )
