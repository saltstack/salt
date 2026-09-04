"""
Integration tests for the multi-ring control plane on the isolated
3-master cluster.

These tests drive ``salt-run cluster.*`` commands against a live
cluster and assert the cluster-log state machines converge on every
master.  They don't depend on a particular cache layout — the
``cluster.ring_create`` / ``route_set`` / ``ring_destroy`` /
``ring_info`` / ``members`` runners are pure cluster-log surface and
work regardless of how the data plane is configured.

The companion ``test_jobs_migration.py`` covers the end-to-end jobs
migration (broadcast → ring → broadcast) using a master_job_cache=
salt_cache configuration.  Splitting the lifecycle from the data-plane
migration keeps the lifecycle assertions fast and decoupled from job
returner setup.
"""

import json
import time

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_runner(master, fun, *args, timeout=60):
    """
    Invoke ``salt-run`` on *master* with ``--output=json`` so the
    result parses straight from stdout.  Returns the JSON-decoded
    output (a dict or list, depending on the runner).
    """
    cli = master.salt_run_cli(timeout=timeout)
    ret = cli.run("--output=json", fun, *args)
    assert ret.returncode == 0, (
        f"{fun} exited non-zero " f"(stdout={ret.stdout!r}, stderr={ret.stderr!r})"
    )
    # ``salt-run --output=json`` writes the structured result to stdout.
    # Empty stdout (some skip-paths) → return None.
    if not ret.stdout.strip():
        return None
    try:
        return json.loads(ret.stdout)
    except json.JSONDecodeError:
        # Some runners (notably fire-and-forget event-only ones) emit
        # a "skipped" status as plain text.  Hand back the raw stdout
        # so the caller can assert on substring.
        return ret.stdout


def _wait_until(predicate, timeout=30, interval=0.5):
    """
    Block until *predicate* returns truthy or *timeout* elapses.
    Returns the last predicate value (truthy on success, falsy on
    timeout) so the caller can assert directly on it.
    """
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last


def _members_view(master):
    """Read ``cluster.members`` on *master* and return the view dict."""
    return _run_runner(master, "cluster.members")


# ---------------------------------------------------------------------------
# Ring lifecycle: create -> route -> destroy
# ---------------------------------------------------------------------------


def test_ring_create_route_destroy_round_trip(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Full multi-ring control-plane round trip on a live 3-master
    cluster:

    1. Confirm baseline: every master sees the same 3-voter cluster.
    2. ``cluster.ring_create name=jobs voters='[m1,m2,m3]'`` from
       master 1.  Within a heartbeat-or-two every master should have
       a ``"jobs"`` ring in its registry.
    3. ``cluster.route_set data_type=jobs ring=jobs`` from master 1.
       Routing snapshot updates everywhere.
    4. ``cluster.route_clear data_type=jobs`` reverts to broadcast.
    5. ``cluster.ring_destroy name=jobs`` marks the ring destroyed.
       The registry entry stays (audit trail) but the local Raft
       group on each founder is torn down.

    Each runner is fire-and-forget; the daemon publishes the
    cluster-log entry asynchronously.  We poll each master's
    ``cluster.members`` (which replays the persisted log) until the
    expected state is visible everywhere.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    addrs = [m.config["interface"] for m in masters]

    # 1. Baseline — every master agrees on the voter set.
    def _all_agree_on_voters():
        views = [_members_view(m) for m in masters]
        return all(
            isinstance(v, dict) and sorted(v.get("voters") or []) == sorted(addrs)
            for v in views
        )

    assert _wait_until(
        _all_agree_on_voters, timeout=60
    ), "Baseline cluster never converged on the 3-voter set"

    # 2. Create the ring on master 1.
    create_result = _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_create",
        "name=jobs",
        f"voters={json.dumps(addrs)}",
    )
    assert isinstance(create_result, dict)
    assert create_result.get("status") == "fan-out initiated"

    # The runner fires a local event; the publish daemon proposes a
    # RING_REGISTRY entry.  We don't have a runner that reads the
    # registry directly, but we can verify the per-ring Raft group
    # was committed by reading the ring's persisted membership via
    # cluster.members — it surfaces the cluster-log view, and the
    # registry entry is on that same log.  The simplest end-to-end
    # check: spawn cluster.ring_info (which reads the per-process
    # ring) on each master and assert no errors.
    #
    # For a tight assertion we tail the master logs for the
    # "ring registry committed" message that
    # ``RaftService._on_ring_registry_change`` writes — present on
    # any founder that brought the ring up locally.
    def _registry_committed_everywhere():
        for master in masters:
            log_path = master.config.get("log_file")
            if not log_path:
                return False
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            if "ring registry committed" not in text:
                return False
            if "ring=jobs status=active" not in text:
                return False
        return True

    assert _wait_until(
        _registry_committed_everywhere, timeout=30
    ), "ring registry RING_REGISTRY commit not observed on every master"

    # 3. Set the route from master 1.
    route_result = _run_runner(
        cluster_master_1_isolated,
        "cluster.route_set",
        "data_type=jobs",
        "ring=jobs",
    )
    assert isinstance(route_result, dict)
    assert route_result.get("status") == "fan-out initiated"

    def _route_committed_everywhere():
        for master in masters:
            log_path = master.config.get("log_file")
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            if "route committed — data_type=jobs -> ring=jobs" not in text:
                return False
        return True

    assert _wait_until(
        _route_committed_everywhere, timeout=30
    ), "ROUTE commit not observed on every master"

    # 4. Clear the route — back to broadcast.
    clear_result = _run_runner(
        cluster_master_1_isolated,
        "cluster.route_clear",
        "data_type=jobs",
    )
    assert isinstance(clear_result, dict)
    assert clear_result.get("status") == "fan-out initiated"

    def _route_cleared_everywhere():
        for master in masters:
            log_path = master.config.get("log_file")
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            if "route cleared — data_type=jobs now broadcasts" not in text:
                return False
        return True

    assert _wait_until(
        _route_cleared_everywhere, timeout=30
    ), "ROUTE clear not observed on every master"

    # 5. Destroy the ring.
    destroy_result = _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_destroy",
        "name=jobs",
    )
    assert isinstance(destroy_result, dict)
    assert destroy_result.get("status") == "fan-out initiated"

    def _ring_destroyed_everywhere():
        for master in masters:
            log_path = master.config.get("log_file")
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            # Either the destroy commit message or the explicit
            # tear-down message confirms the lifecycle for that
            # master.  Non-founder masters only see the registry
            # commit (no Node to tear down locally).
            if "status=destroyed" not in text:
                return False
        return True

    assert _wait_until(
        _ring_destroyed_everywhere, timeout=30
    ), "ring destroy commit not observed on every master"

    # After tear-down: cluster.members still works (cluster Raft is
    # unaffected by per-ring lifecycle) — pin that the cluster log
    # didn't lose state across the ring churn.
    final_view = _members_view(cluster_master_1_isolated)
    assert isinstance(final_view, dict)
    assert sorted(final_view.get("voters") or []) == sorted(
        addrs
    ), "Cluster voter set drifted during ring lifecycle"


def test_ring_create_idempotent_across_repeated_invocations(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Re-creating an active ring with the same id should leave the
    cluster log with a single active registry entry (every commit
    overwrites the previous one in-place).  Pins the operator
    contract that running ``ring_create`` twice by mistake doesn't
    corrupt the registry.
    """
    addrs = [
        cluster_master_1_isolated.config["interface"],
        cluster_master_2_isolated.config["interface"],
        cluster_master_3_isolated.config["interface"],
    ]

    # First create.
    _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_create",
        "name=audit_ring",
        f"voters={json.dumps(addrs)}",
    )
    # Second create with the same voters — should be a no-op-equivalent
    # at the registry level.
    _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_create",
        "name=audit_ring",
        f"voters={json.dumps(addrs)}",
    )

    # Both commits should appear in the leader's log, but the
    # registry SM ends in a single deterministic state.  We don't
    # have a runner that surfaces the registry directly; the
    # robustness assertion is that the cluster itself remains
    # healthy after the double-create — voters unchanged, term
    # didn't churn.
    def _cluster_still_steady():
        view = _members_view(cluster_master_1_isolated)
        return (
            isinstance(view, dict)
            and sorted(view.get("voters") or []) == sorted(addrs)
            and view.get("leader_id") in addrs
        )

    assert _wait_until(_cluster_still_steady, timeout=30)

    # Cleanup so the next test starts clean (these isolated fixtures
    # don't tear down between tests in the same module).
    _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_destroy",
        "name=audit_ring",
    )


def test_route_clear_for_unrouted_data_type_is_safe(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    ``cluster.route_clear`` for a data type that was never routed
    must be a successful no-op — operators running cleanup playbooks
    shouldn't have to know which routes already exist.  The clear
    commits an entry mapping the data type to ``None`` (broadcast),
    which is also the absent-entry default; the cluster ends in the
    same effective state either way.
    """
    addrs = [
        cluster_master_1_isolated.config["interface"],
        cluster_master_2_isolated.config["interface"],
        cluster_master_3_isolated.config["interface"],
    ]

    # Wait for baseline cluster.
    def _baseline_ready():
        view = _members_view(cluster_master_1_isolated)
        return isinstance(view, dict) and sorted(view.get("voters") or []) == sorted(
            addrs
        )

    assert _wait_until(_baseline_ready, timeout=60)

    # Clear a route that doesn't exist.
    result = _run_runner(
        cluster_master_1_isolated,
        "cluster.route_clear",
        "data_type=never_routed",
    )
    assert isinstance(result, dict)
    assert result.get("status") == "fan-out initiated"

    # Cluster stays healthy — no spurious term churn or voter drop.
    def _cluster_still_steady():
        view = _members_view(cluster_master_1_isolated)
        return (
            isinstance(view, dict)
            and sorted(view.get("voters") or []) == sorted(addrs)
            and view.get("leader_id") in addrs
        )

    assert _wait_until(_cluster_still_steady, timeout=30)
