"""
Scenario: operator walks the cache-rings cookbook on a real cluster.

Mechanically executes every numbered step from the published
documentation at ``doc/topics/performance/cache_rings.rst`` against
a live 3-master cluster and asserts the documented post-conditions.
If a step diverges from the doc (or breaks under live wiring), this
test fails loudly so the documentation and the implementation cannot
silently desynchronise.

Covered cookbook steps (matching doc numbering):

* **Step 1** — ``cluster.migrate_jobs_to_cache`` migrates a pre-flip
  ``local_cache`` layout into ``salt_cache`` banks while leaving the
  original tree on disk (doc guarantee: operators reclaim it
  manually).
* **Step 2** — ``cluster.ring_create`` commits a ``RING_REGISTRY``
  entry visible to every master.
* **Step 3** — ``cluster.route_set`` commits a ``ROUTE`` entry; the
  ``cluster.rings`` and ``cluster.routes`` runners (doc's
  authoritative verification path) surface the new state.
* **Step 4** — ``cluster.shed_unowned_all`` fans out to every peer;
  every master writes a ``cluster-shed-status.json`` sentinel.
* **Step 5** — ``cluster.ring_set replicas=N members=voters`` commits
  a ``RING_CONFIG`` entry on the ring's own log.  (Previously only
  unit-tested — no integration coverage before this scenario.)
* **Step 6** — ``cluster.route_clear`` returns to broadcast,
  ``cluster.ring_destroy`` marks the ring destroyed.
"""

import json
import pathlib
import time

import pytest

import salt.cache
import salt.payload
import salt.utils.files
import salt.utils.jid

pytestmark = [
    pytest.mark.slow_test,
    # The cookbook makes 10+ salt-run invocations in series.  Under
    # coverage tracing each pays startup cost; disabling subprocess
    # coverage keeps the test inside the configured timeout without
    # losing the parent-process coverage signal (runner code is
    # unit-tested in the main pytest process).
    pytest.mark.no_subprocess_coverage,
    # Walk-clock budget matches ``test_ring_lifecycle_shared_fs.py``.
    pytest.mark.timeout(480, func_only=True),
]


# ---------------------------------------------------------------------------
# Helpers (same shape as test_ring_lifecycle_shared_fs / test_jobs_migration)
# ---------------------------------------------------------------------------


def _run_runner(master, fun, *args, timeout=60):
    """Invoke ``salt-run --output=json`` on *master* and decode."""
    cli = master.salt_run_cli(timeout=timeout)
    ret = cli.run("--output=json", fun, *args)
    assert ret.returncode == 0, (
        f"{fun} exited {ret.returncode} "
        f"(stdout={ret.stdout!r}, stderr={ret.stderr!r})"
    )
    if not ret.stdout.strip():
        return None
    try:
        return json.loads(ret.stdout)
    except json.JSONDecodeError:
        return ret.stdout


def _wait_until(predicate, timeout=30, interval=0.5):
    """Poll *predicate* until truthy or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    return last


def _log_contains_everywhere(masters, needle):
    """True iff *needle* appears in every master's on-disk log file."""
    for master in masters:
        log_path = master.config.get("log_file")
        if not log_path:
            return False
        try:
            with salt.utils.files.fopen(log_path) as fp:
                if needle not in fp.read():
                    return False
        except OSError:
            return False
    return True


# ---------------------------------------------------------------------------
# The cookbook
# ---------------------------------------------------------------------------


def test_cache_rings_cookbook_end_to_end(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
):
    """
    Walk the documented cookbook steps 1..6 in order on a live
    3-master cluster.  Each step asserts the documented
    post-condition before moving on.
    """
    masters = [cluster_master_1, cluster_master_2, cluster_master_3]
    addrs = [m.config["interface"] for m in masters]
    originator = cluster_master_1

    # --- Baseline: every master sees the 3-voter cluster ---
    def _baseline_ready():
        for master in masters:
            view = _run_runner(master, "cluster.members")
            if not isinstance(view, dict):
                return False
            if sorted(view.get("voters") or []) != sorted(addrs):
                return False
        return True

    assert _wait_until(
        _baseline_ready, timeout=120
    ), "cluster never converged on the 3-voter baseline"

    # --- Step 1: Migrate pre-flip job data ---
    #
    # Doc says: run before enabling routing when upgrading an existing
    # ``local_cache`` deployment; source tree is left in place.
    cachedir = pathlib.Path(originator.config["cachedir"])
    jobs_root = cachedir / "jobs"
    jid = "20260101000000000001"
    jid_dir = pathlib.Path(salt.utils.jid.jid_dir(jid, str(jobs_root), "sha256"))
    jid_dir.mkdir(parents=True, exist_ok=True)
    with salt.utils.files.fopen(str(jid_dir / ".load.p"), "w+b") as fp:
        salt.payload.dump({"jid": jid, "fun": "test.ping", "tgt": "*"}, fp)
    with salt.utils.files.fopen(str(jid_dir / ".minions.p"), "w+b") as fp:
        salt.payload.dump(["minion-a"], fp)

    migrate = _run_runner(originator, "cluster.migrate_jobs_to_cache")
    assert isinstance(migrate, dict), f"migrate returned {migrate!r}"
    assert migrate.get("status") == "ok", migrate
    # ``>= 1`` rather than ``== 1``: a live cluster has background
    # salt-run invocations (``cluster.members`` during our baseline
    # check) that drop their own JIDs under ``local_cache`` too, so
    # the migrator counts those alongside the seeded one.  The point
    # is that OUR seeded JID landed in the new banks — asserted
    # below.
    assert migrate.get("migrated", 0) >= 1, migrate
    assert migrate.get("scanned", 0) >= 1, migrate

    # Doc guarantee: the source tree is left on disk.
    assert (jid_dir / ".load.p").is_file(), (
        "migrate_jobs_to_cache deleted the source ``local_cache`` layout; "
        "the cookbook's guarantee is that it stays on disk until the "
        "operator reclaims it"
    )

    # And the banks the docs name are actually populated.
    cache = salt.cache.Cache(
        dict(originator.config),
        driver=originator.config.get("cache", "localfs"),
    )
    assert (
        cache.fetch("jobs/loads", jid)["fun"] == "test.ping"
    ), "migrate_jobs_to_cache did not populate jobs/loads keyed by JID"
    assert cache.fetch("jobs/minions", jid) == [
        "minion-a"
    ], "migrate_jobs_to_cache did not populate jobs/minions keyed by JID"

    # --- Step 2: Create the ring ---
    #
    # Doc says: ``cluster.ring_create name=jobs voters=[...]`` fires a
    # ``cluster/runner/ring_create`` event; the publish daemon proposes
    # a ``RING_REGISTRY`` entry on the cluster Raft group.
    create = _run_runner(
        originator,
        "cluster.ring_create",
        "name=jobs",
        f"voters={json.dumps(addrs)}",
    )
    assert isinstance(create, dict)
    assert create.get("status") == "fan-out initiated", create
    assert create.get("tag") == "cluster/runner/ring_create", create

    assert _wait_until(
        lambda: _log_contains_everywhere(masters, "ring=jobs status=active"),
        timeout=60,
    ), (
        "RING_REGISTRY commit for ring=jobs never observed on every "
        "master — the doc says the entry propagates on commit"
    )

    # Authoritative view (what the doc tells operators to check).
    rings_view = _run_runner(originator, "cluster.rings")
    assert isinstance(rings_view, dict)
    assert "jobs" in rings_view.get("active_rings", []), rings_view

    # --- Step 3: Route the data type to the ring ---
    route_result = _run_runner(
        originator, "cluster.route_set", "data_type=jobs", "ring=jobs"
    )
    assert isinstance(route_result, dict)
    assert route_result.get("status") == "fan-out initiated", route_result

    assert _wait_until(
        lambda: _log_contains_everywhere(
            masters, "route committed — data_type=jobs -> ring=jobs"
        ),
        timeout=30,
    ), "ROUTE commit for data_type=jobs not observed on every master"

    # Doc's recommended verification path: cluster.routes.
    routes_view = _run_runner(originator, "cluster.routes")
    assert isinstance(routes_view, dict)
    assert routes_view["routes"].get("jobs") == "jobs", routes_view

    # --- Step 4: Shed unowned (dry-run, then commit) ---
    dry = _run_runner(
        originator, "cluster.shed_unowned_all", "ring=jobs", "dry_run=True"
    )
    assert isinstance(dry, dict)
    assert isinstance(dry.get("fan_out"), dict)
    assert dry["fan_out"].get("status") == "fan-out initiated", dry
    assert dry.get("local", {}).get("dry_run") is True

    committed = _run_runner(originator, "cluster.shed_unowned_all", "ring=jobs")
    assert isinstance(committed, dict)
    assert committed.get("fan_out", {}).get("status") == "fan-out initiated"

    # Doc says: each peer writes a sentinel at
    # ``<cachedir>/cluster-shed-status.json``.
    def _sentinel_on_every_master():
        for master in masters:
            status = _run_runner(master, "cluster.shed_status")
            if not isinstance(status, dict):
                return False
            if status.get("status") == "missing":
                return False
        return True

    assert _wait_until(_sentinel_on_every_master, timeout=90), (
        "cluster-shed-status.json sentinel never appeared on every "
        "master after shed_unowned_all — doc says the fan-out writes "
        "one per peer"
    )

    # --- Step 5: Tune ring policy ---
    #
    # Doc says: ``cluster.ring_set replicas=N members=voters`` proposes
    # a ``RING_CONFIG`` entry on the ring's OWN Raft log (not the
    # cluster log).  Previously had no integration test coverage.
    policy = _run_runner(
        originator,
        "cluster.ring_set",
        "name=jobs",
        "members=voters",
        "replicas=2",
    )
    assert isinstance(policy, dict)
    assert policy.get("status") == "fan-out initiated", policy

    assert _wait_until(
        lambda: _log_contains_everywhere(
            masters,
            "ring=jobs policy committed — members=voters replicas=2",
        ),
        timeout=30,
    ), (
        "RING_CONFIG commit for ring=jobs policy change never observed "
        "on every master — doc says the ring-local log propagates the "
        "policy to every ring member"
    )

    # --- Step 6: Reverse — clear route, destroy ring ---
    clear = _run_runner(originator, "cluster.route_clear", "data_type=jobs")
    assert isinstance(clear, dict)
    assert clear.get("status") == "fan-out initiated", clear

    assert _wait_until(
        lambda: _log_contains_everywhere(masters, "route cleared — data_type=jobs"),
        timeout=30,
    ), "ROUTE clear for data_type=jobs not observed on every master"

    destroy = _run_runner(originator, "cluster.ring_destroy", "name=jobs")
    assert isinstance(destroy, dict)
    assert destroy.get("status") == "fan-out initiated", destroy

    assert _wait_until(
        lambda: _log_contains_everywhere(masters, "ring=jobs status=destroyed"),
        timeout=30,
    ), "RING_REGISTRY destroy for ring=jobs not observed on every master"

    # Final authoritative check: ring is no longer in active_rings.
    rings_after = _run_runner(originator, "cluster.rings")
    assert "jobs" not in rings_after.get("active_rings", []), rings_after
