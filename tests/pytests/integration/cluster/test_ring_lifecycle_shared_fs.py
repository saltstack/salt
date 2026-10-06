"""
Shared-filesystem variant of the multi-ring lifecycle integration
test.

The companion ``test_ring_lifecycle.py`` runs against the
``*_isolated`` fixtures with ``cluster_isolated_filesystem: True``
— each master has its own pki + cache dirs, exercising the
no-shared-FS path.  This test runs against the default
``cluster_master_{1,2,3}`` fixtures which share ``cluster_pki_dir``
and ``cache_dir`` across all three masters on the test box.

Why both
--------
The :class:`SaltStorage` path scheme is keyed by ``(node_id,
ring_id)``, so per-master Raft state should never collide on a
shared FS.  This test pins that the multi-ring runners and the
per-ring Raft groups all work the same way under shared-FS, since
that's the deployment most operators with shared NFS or single-host
test clusters actually run.
"""

import json
import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
    # The lifecycle test polls three predicates serially against the
    # 3-master cluster (baseline ready, registry+route propagated,
    # ring destroyed), each ``_wait_until`` running ``cluster.members``
    # as a fresh ``salt-run`` subprocess.  Under coverage tracing on a
    # 2-vCPU GHA runner the cumulative wall-clock for those subprocess
    # invocations has been observed at 95-130 s — past the global 90 s
    # pytest-timeout default.  Bump the wall-clock ceiling so the
    # test's own predicate timeouts remain the failure signal.
    pytest.mark.timeout(360, func_only=True),
]


def _run_runner(master, fun, *args, timeout=60):
    cli = master.salt_run_cli(timeout=timeout)
    ret = cli.run("--output=json", fun, *args)
    assert (
        ret.returncode == 0
    ), f"{fun} exited non-zero (stdout={ret.stdout!r}, stderr={ret.stderr!r})"
    if not ret.stdout.strip():
        return None
    try:
        return json.loads(ret.stdout)
    except json.JSONDecodeError:
        return ret.stdout


def _wait_until(predicate, timeout=30, interval=0.5):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last


def test_ring_lifecycle_on_shared_filesystem(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
):
    """
    The ``cluster.ring_create`` / ``route_set`` / ``ring_destroy``
    surface works the same way under shared-FS as under the
    isolated-FS path.  Pin the storage-path-keying contract: per-node
    Raft state never bleeds across masters even when their cachedirs
    share a parent.

    Three masters, all rooted at the same cachedir on disk.  Create
    a ring, route a data type to it, confirm the registry + routing
    commits propagate (via master log tail), then destroy the ring
    and confirm the cluster is unaffected.
    """
    masters = [cluster_master_1, cluster_master_2, cluster_master_3]
    addrs = [m.config["interface"] for m in masters]

    # Baseline — every master sees the same voter set.
    def _baseline_ready():
        for m in masters:
            view = _run_runner(m, "cluster.members")
            if not isinstance(view, dict):
                return False
            if sorted(view.get("voters") or []) != sorted(addrs):
                return False
        return True

    assert _wait_until(_baseline_ready, timeout=60), "cluster baseline never ready"

    # Note on "shared FS" scope: this fixture shares
    # ``cluster_pki_dir`` and ``cache_dir`` across all three masters
    # — that's the meaningful operator-facing knob.  Each master's
    # own ``cachedir`` (the opt :class:`SaltStorage` uses for the
    # Raft log path) is per-master regardless, because
    # ``salt-factories`` injects a per-daemon ``cachedir``.  So
    # multi-ring on-disk state is always isolated by node-id and
    # this test exercises the bootstrap + lifecycle path that runs
    # when operators share ``cluster_pki_dir`` (the common NFS-backed
    # production layout).

    # Create + route — same shape as the isolated test.
    _run_runner(
        cluster_master_1,
        "cluster.ring_create",
        "name=jobs_shared",
        f"voters={json.dumps(addrs)}",
    )
    _run_runner(
        cluster_master_1,
        "cluster.route_set",
        "data_type=jobs",
        "ring=jobs_shared",
    )

    def _registry_and_route_on_every_master():
        # Use the new cluster.rings / cluster.routes runners instead
        # of tailing logs — more robust against unrelated log lines
        # from other tests sharing the cachedir.
        for m in masters:
            rings = _run_runner(m, "cluster.rings")
            if not isinstance(rings, dict):
                return False
            if "jobs_shared" not in rings.get("active_rings", []):
                return False
            routes = _run_runner(m, "cluster.routes")
            if not isinstance(routes, dict):
                return False
            if routes.get("routes", {}).get("jobs") != "jobs_shared":
                return False
        return True

    assert _wait_until(_registry_and_route_on_every_master, timeout=45), (
        "ring + route not visible on every master via cluster.rings / " "cluster.routes"
    )

    # Destroy.
    _run_runner(cluster_master_1, "cluster.ring_destroy", "name=jobs_shared")
    _run_runner(cluster_master_1, "cluster.route_clear", "data_type=jobs")

    def _ring_destroyed_everywhere():
        for m in masters:
            rings = _run_runner(m, "cluster.rings")
            if not isinstance(rings, dict):
                return False
            entry = rings.get("rings", {}).get("jobs_shared")
            if entry is None or entry.get("status") != "destroyed":
                return False
        return True

    assert _wait_until(_ring_destroyed_everywhere, timeout=30)

    # Cluster stays healthy.
    view = _run_runner(cluster_master_1, "cluster.members")
    assert sorted(view.get("voters") or []) == sorted(addrs)
    assert view.get("leader_id") in addrs
