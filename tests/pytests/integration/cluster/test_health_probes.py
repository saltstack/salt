"""
End-to-end tests for the file-sentinel Kubernetes probes.

Verifies that the three sentinels under ``<cachedir>/health/`` are
populated by a real ``salt-master`` process in the right sequence:

  * ``startup`` lands once ``Master.start`` finishes wiring up
    subprocesses (proves the startup probe works for plain masters).
  * ``ready`` lands once a clustered master commits its founding /
    promotion CONFIG entry (proves ``_signal_cluster_ready`` writes
    the readiness sentinel).
  * ``alive`` mtime advances continuously (proves the parent's
    asyncio-loop heartbeat keeps the liveness probe fresh).

The unit-level layout / atomic-write checks live in
``tests/pytests/unit/cluster/test_healthchecks.py``; this file exists
only to catch regressions in the wiring between ``Master.start``,
``MasterPubServerChannel._signal_cluster_ready``, and the heartbeat
loop on the parent process.
"""

import pathlib
import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def _health_dir(master):
    return pathlib.Path(master.config["cachedir"]) / "health"


def _wait_for_sentinel(master, name, timeout=60):
    """Poll until ``<cachedir>/health/<name>`` exists; return True on success."""
    sentinel = _health_dir(master) / name
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sentinel.is_file():
            return True
        time.sleep(0.5)
    return False


def test_startup_sentinel_written_for_clustered_master(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    Once a clustered master finishes ``Master.start`` it must have
    ``<cachedir>/health/startup`` on disk.  Probe spec for
    ``startupProbe`` is ``test -f <cachedir>/health/startup``; this
    test guarantees that file exists.
    """
    for master in (cluster_master_1, cluster_master_2, cluster_master_3):
        assert _wait_for_sentinel(master, "startup", timeout=60), (
            f"startup sentinel never appeared for "
            f"{master.config['interface']} (looked under {_health_dir(master)})"
        )


def test_ready_sentinel_written_after_cluster_consensus(
    cluster_master_1, cluster_master_2, cluster_master_3
):
    """
    A clustered master must write ``health/ready`` only after its Raft
    consensus gate fires — i.e. after the founding/promotion CONFIG
    commits with this node in the voter set.

    For the readiness probe to be useful, the sentinel must exist on
    every master once the cluster has converged.  ``_wait_for_sentinel``
    polls until the file lands or the deadline expires; the timeout
    here is wider than ``startup`` because the join handshake + first
    Raft commit add real latency on top of master init.
    """
    masters = (cluster_master_1, cluster_master_2, cluster_master_3)
    for master in masters:
        assert _wait_for_sentinel(master, "ready", timeout=120), (
            f"ready sentinel never appeared for "
            f"{master.config['interface']}; either ``_signal_cluster_ready`` "
            f"never fired or the sentinel write was skipped"
        )


def test_alive_sentinel_mtime_advances(cluster_master_1):
    """
    The liveness sentinel's mtime must advance continuously.  Capture
    two snapshots ~6 seconds apart (one heartbeat interval is 5 s) and
    assert the mtime moved.  If it does not, the parent process's
    asyncio loop is not running our heartbeat task — the prototypical
    deadlock failure mode that liveness exists to catch.
    """
    assert _wait_for_sentinel(cluster_master_1, "alive", timeout=60), (
        f"alive sentinel never appeared for " f"{cluster_master_1.config['interface']}"
    )
    sentinel = _health_dir(cluster_master_1) / "alive"
    first = sentinel.stat().st_mtime
    # Sleep a full heartbeat interval plus filesystem-mtime granularity
    # margin so the next touch is definitely a distinct timestamp.
    time.sleep(6)
    second = sentinel.stat().st_mtime
    assert second > first, (
        f"alive sentinel mtime did not advance over a 6 s window "
        f"({first} -> {second}); parent asyncio loop appears wedged"
    )


def test_health_dir_wiped_on_restart(cluster_master_1, cluster_master_2):
    """
    ``Master.start`` must wipe ``<cachedir>/health/`` before writing new
    sentinels — otherwise an old ``ready`` from a previous run would
    let kubelet route traffic to a master that is still re-bootstrapping.

    Approach: drop a sentinel-shaped file we never write
    (``health/CANARY``) into master_2's health dir, then bounce
    master_2 and confirm the canary is gone afterward.
    """
    canary = _health_dir(cluster_master_2) / "CANARY"
    canary.parent.mkdir(parents=True, exist_ok=True)
    canary.write_text("from-the-past", encoding="utf-8")
    assert canary.is_file()

    cluster_master_2.terminate()
    with cluster_master_2.started(start_timeout=120):
        # Wait for the new run's startup sentinel to confirm reset_health_dir
        # has run.
        assert _wait_for_sentinel(cluster_master_2, "startup", timeout=60)
        assert not canary.exists(), (
            "Stale 'CANARY' sentinel survived a master restart; "
            "reset_health_dir must wipe the directory before writing the "
            "fresh startup sentinel"
        )
