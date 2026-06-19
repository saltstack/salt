"""
Integration tests for Raft consensus over a real three-master cluster.

Uses the same ``cluster_master_1/2/3`` fixtures from conftest.py which
spin up actual Salt master processes on 127.0.0.1/2/3.

Each master starts with ``cluster_id`` and ``cluster_peers`` set, so
``MasterPubServerChannel._publish_daemon`` will construct a ``RaftService``
and begin Raft elections over the real ``cluster_pool_port`` TCP channel.

We observe Raft activity by watching each master's log file for the
``BECOMING LEADER`` message that ``Node.become_leader`` emits.
"""

import re
import time

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
]

# How long to wait for an election to complete across real processes.
# Bumped from 30 → 60 because Photon ARM64 fips and Debian ARM64 runners
# regularly need more than 30 s for the Raft handshake to converge under
# load, producing flaky CI failures otherwise.
_ELECTION_TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_log(master_factory):
    """Return the contents of a master's log file, or empty string."""
    import os  # pylint: disable=import-outside-toplevel

    log_path = master_factory.config.get("log_file")
    if not log_path:
        return ""
    if not os.path.isabs(log_path):
        root_dir = master_factory.config.get("root_dir", "")
        log_path = os.path.join(root_dir, log_path)
    try:
        with salt.utils.files.fopen(log_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


_BECOMING_RE = re.compile(
    r"Node \S+ BECOMING (LEADER|FOLLOWER|CANDIDATE) for term (\d+)"
)


def _current_leader(masters):
    """
    Return the *current* leader (or None) by reading each master's log
    and finding whichever node most recently logged ``BECOMING LEADER``
    for the highest term it ever reached without subsequently stepping
    down to FOLLOWER at a still-higher term.

    Counting every historical ``BECOMING LEADER`` line conflates Raft's
    safety property (≤ 1 leader at any moment) with liveness churn
    (leadership can legitimately move between terms in noisy CI), so we
    inspect the most recent state instead.
    """
    last_state = {}  # node -> (term, state)
    for m in masters:
        node_state = None
        node_term = -1
        for match in _BECOMING_RE.finditer(_read_log(m)):
            state, term = match.group(1), int(match.group(2))
            if term >= node_term:
                node_term, node_state = term, state
        last_state[m.config["interface"]] = (node_term, node_state)
    leaders = [addr for addr, (_, state) in last_state.items() if state == "LEADER"]
    return leaders


def _count_leaders(masters):
    """
    Count how many masters are *currently* the leader.  See
    :func:`_current_leader`; an alias kept for backward compatibility
    with the existing assertion messages.
    """
    leaders = _current_leader(masters)
    return len(leaders), leaders


def _wait_for_election(masters, timeout=_ELECTION_TIMEOUT):
    """
    Poll until exactly one master has become leader, or timeout expires.
    Returns ``(leader_count, leader_interfaces)``.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count, leaders = _count_leaders(masters)
        if count == 1:
            return count, leaders
        time.sleep(0.5)
    return _count_leaders(masters)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# Coverage init in every salt-master subprocess adds ~hundreds of ms per
# fork, which is enough to push the Raft election timer past its budget
# on a 2-vCPU GHA runner — masters keep timing out before AppendEntries
# replicate, candidates step on each other, and ``assert_no_election_storm``
# (correctly) flags the watchdog-driven recovery.  Skip subprocess
# coverage for this test: the Raft / leader-election code is exercised by
# unit tests in the main pytest process (which is still traced), so the
# subprocess-side data is redundant signal.
@pytest.mark.no_subprocess_coverage
def test_raft_election_three_masters(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    Three masters with cluster_id + cluster_peers should elect exactly one
    Raft leader within the election timeout window.
    """
    from tests.pytests.integration.cluster.conftest import assert_no_election_storm

    masters = [cluster_master_1, cluster_master_2, cluster_master_3]
    count, leaders = _wait_for_election(masters)
    assert count == 1, (
        f"Expected exactly 1 Raft leader, got {count}: {leaders}. "
        f"Check that 'BECOMING LEADER' appears in exactly one master log."
    )
    # If the test "passed" only because some watchdog rescued a stuck
    # pre-vote / candidacy loop, surface that loudly instead of silently
    # accepting it.  See ``assert_no_election_storm`` for the rationale.
    assert_no_election_storm(masters)


def test_raft_service_started_on_all_masters(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    All three masters should log that their Raft consensus service started.
    """
    masters = [cluster_master_1, cluster_master_2, cluster_master_3]
    # Give services a moment to start
    time.sleep(5)
    for m in masters:
        log = _read_log(m)
        assert "Raft consensus service started" in log, (
            f"Master {m.config['interface']} did not log Raft service start. "
            f"Log tail: {log[-2000:]!r}"
        )


@pytest.mark.timeout(240)
@pytest.mark.flaky(max_runs=3)
def test_raft_re_election_after_leader_restart(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    After the leader master is stopped, the remaining two masters should
    elect a new leader within the election timeout.
    """
    from tests.pytests.integration.cluster.conftest import assert_no_election_storm

    masters = [cluster_master_1, cluster_master_2, cluster_master_3]
    count, leaders = _wait_for_election(masters)
    assert count == 1, f"No initial leader elected: {leaders}"

    leader_addr = leaders[0]
    leader_master = next(m for m in masters if m.config["interface"] == leader_addr)
    survivors = [m for m in masters if m.config["interface"] != leader_addr]

    # Snapshot the survivors' BECOMING LEADER counts BEFORE terminating the
    # leader.  Under CPU contention, ``leader_master.terminate()`` can block
    # several seconds waiting for the SIGTERM-reaped process to actually
    # exit; during that window the survivors notice heartbeats stopping,
    # fire their election timers, and re-elect — logging a fresh
    # ``BECOMING LEADER for term N`` line *before* this snapshot if it ran
    # post-terminate.  Then ``after - before == 0`` and the assertion fails
    # even though re-election succeeded perfectly.  Snapshot first.
    before = {
        m.config["interface"]: _read_log(m).count("BECOMING LEADER") for m in survivors
    }

    # Stop the leader
    leader_master.terminate()

    new_count, new_leaders = _wait_for_election(survivors, timeout=_ELECTION_TIMEOUT)

    # At least one survivor must have a new BECOMING LEADER entry
    after = {
        m.config["interface"]: _read_log(m).count("BECOMING LEADER") for m in survivors
    }
    new_elections = {addr: after[addr] - before[addr] for addr in before}
    assert any(v > 0 for v in new_elections.values()), (
        f"No re-election detected after leader {leader_addr} stopped. "
        f"New election counts: {new_elections}"
    )
    # Re-election + initial election may legitimately bump the survivors'
    # CANDIDATE/FOLLOWER counts a bit more than the standard fixture; raise
    # the per-master cap accordingly but still fail loudly if we're seeing
    # 10+ rounds (the slow-runner CI failure mode).
    assert_no_election_storm(
        survivors, max_candidate_per_master=8, max_follower_per_master=8
    )
