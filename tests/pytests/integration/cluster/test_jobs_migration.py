"""
End-to-end jobs migration scenario on the isolated 3-master cluster.

Exercises the full multi-ring round-trip for the data plane:

1. **Seed** synthetic ``jobs/loads`` entries on every master so each
   one holds the same baseline keyspace (mimics the broadcast era).
2. **Create** ring=jobs with all three masters as founders and
   route ``data_type=jobs`` to it.
3. **Shed** unowned JIDs on each master, asserting that each one
   keeps only its ring-owned slice and that the union across masters
   equals the original set.
4. **Collect** from peers on master 1, asserting it ends up with
   the full keyspace again.
5. **Clear** the route and **destroy** the ring; verify the cluster
   is back to broadcast.

The salt_cache returner integration is covered separately by
``tests/pytests/unit/returners/test_salt_cache.py`` — this test
proves the multi-ring runners can move arbitrary
:class:`salt.cache.Cache` bank contents end-to-end on a real
cluster, which is the production case once
``master_job_cache: salt_cache`` lands in operator configs.
"""

import json
import time

import pytest

import salt.cache
import salt.utils.files

pytestmark = [
    pytest.mark.slow_test,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_runner(master, fun, *args, timeout=60):
    """Run a runner via ``salt-run --output=json`` and decode."""
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


def _master_cache(master):
    """
    Build a :class:`salt.cache.Cache` rooted at *master*'s configured
    cachedir.  Used to seed and inspect bank state from the test
    process.  Reads the same on-disk paths the master daemon (and
    the runner subprocesses it spawns) read.
    """
    opts = dict(master.config)
    # The Cache abstraction uses ``cachedir`` plus the configured
    # driver.  Both are present in the fixture's opts.
    return salt.cache.Cache(opts, driver=opts.get("cache", "localfs"))


def _expected_partition(jids, voters):
    """Compute which JID each voter owns under the canonical hash ring."""
    from salt.cluster.ring import HashRing

    ring = HashRing()
    ring.rebuild(list(voters))
    per_voter = {v: [] for v in voters}
    for jid in jids:
        per_voter[ring.get_owner(jid)].append(jid)
    return per_voter


# ---------------------------------------------------------------------------
# The scenario
# ---------------------------------------------------------------------------


# Skip subprocess coverage: the round-trip fires
# ``cluster.ring_create → route_set → shed_unowned → collect_from_peers →
# route_clear`` as five (or more) ``salt-run`` subprocesses in series.
# Each subprocess pays the coverage-startup tax (~hundreds of ms on the
# onedir), which stacks up to several seconds and pushes the test past
# pytest's 90 s default timeout on a 2-vCPU runner.  The runner code
# itself is unit-tested in the main pytest process, so the
# subprocess-side coverage data is redundant.
@pytest.mark.no_subprocess_coverage
def test_jobs_migration_round_trip(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Full data-plane round-trip for the jobs cache:

    * Each master holds the same 40-jid baseline.
    * ``ring_create`` + ``route_set`` brings up a 3-voter ring.
    * ``shed_unowned`` partitions the keyspace across the masters.
    * ``collect_from_peers`` reconstitutes the full set on master 1.
    * ``route_clear`` + ``ring_destroy`` returns the cluster to
      broadcast.

    Asserts at every step that:

    * the cluster-log entries propagate to all masters,
    * the data plane on disk matches expected ownership,
    * the cluster itself stays steady (voter set / leader stable).
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    addrs = [m.config["interface"] for m in masters]

    # Baseline: cluster has the right voter set on every master.
    def _baseline_ready():
        for m in masters:
            view = _run_runner(m, "cluster.members")
            if not isinstance(view, dict):
                return False
            if sorted(view.get("voters") or []) != sorted(addrs):
                return False
        return True

    assert _wait_until(_baseline_ready, timeout=60), "cluster baseline never ready"

    # Phase 1: seed the same 40 JIDs into every master's cache.
    seeded = [f"jid-{i:04d}" for i in range(40)]
    for master in masters:
        cache = _master_cache(master)
        for jid in seeded:
            cache.store("jobs/loads", jid, {"fun": "test.ping", "tgt": "*"})
            cache.store("jobs/minions", jid, ["minion-a"])
            # One return entry per JID so the cascade flush actually
            # has something to drop.
            cache.store(f"jobs/returns/{jid}", "minion-a", {"return": True})

    # Sanity: every master sees all 40 JIDs initially.
    for master in masters:
        cache = _master_cache(master)
        assert set(cache.list("jobs/loads")) == set(seeded)

    # Phase 2: create ring + route from master 1.
    create = _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_create",
        "name=jobs",
        f"voters={json.dumps(addrs)}",
    )
    assert create.get("status") == "fan-out initiated"

    route = _run_runner(
        cluster_master_1_isolated,
        "cluster.route_set",
        "data_type=jobs",
        "ring=jobs",
    )
    assert route.get("status") == "fan-out initiated"

    # Wait for both registry + routing entries to commit on every
    # master by tailing the master logs.
    def _ring_and_route_ready():
        for master in masters:
            log_path = master.config.get("log_file")
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            if "ring=jobs status=active" not in text:
                return False
            if "route committed — data_type=jobs -> ring=jobs" not in text:
                return False
        return True

    assert _wait_until(
        _ring_and_route_ready, timeout=45
    ), "ring + route commits not visible on every master"

    # Phase 3: shed unowned JIDs on each master.
    shed_results = {}
    for master in masters:
        result = _run_runner(
            master,
            "cluster.shed_unowned",
            "ring=jobs",
        )
        assert isinstance(result, dict), f"shed result not dict: {result!r}"
        assert result["status"] == "ok"
        shed_results[master.config["interface"]] = result

    # Verify the partition: each master kept its ring-owned JIDs,
    # the union across masters equals the original set, and no
    # master has any unowned JID.
    expected = _expected_partition(seeded, addrs)
    for master in masters:
        addr = master.config["interface"]
        cache = _master_cache(master)
        survivors = set(cache.list("jobs/loads"))
        owned = set(expected[addr])
        unowned = set(seeded) - owned

        assert survivors == owned, (
            f"master {addr}: survivors {sorted(survivors)} != "
            f"expected {sorted(owned)}"
        )
        # Cascade: the returns sub-banks for unowned JIDs are gone.
        for jid in unowned:
            assert (
                list(cache.list(f"jobs/returns/{jid}")) == []
            ), f"master {addr}: returns bank for unowned JID {jid} survived shed"
        # And the returns sub-banks for owned JIDs are intact.
        for jid in owned:
            assert list(cache.list(f"jobs/returns/{jid}")) == ["minion-a"]

    # Union of survivors equals the original set — no JID was lost.
    union = set()
    for master in masters:
        union |= set(_master_cache(master).list("jobs/loads"))
    assert union == set(seeded), (
        f"jids lost in shed: missing={sorted(set(seeded) - union)}, "
        f"extra={sorted(union - set(seeded))}"
    )

    # Phase 4: collect from peers on master 1 — recover full set.
    collect = _run_runner(
        cluster_master_1_isolated,
        "cluster.collect_from_peers",
        "channels=[]",  # only banks, no fixed channels
    )
    assert collect.get("status") == "fan-out initiated"

    # The peer-side ``_handle_collect_request`` streams the requested
    # channels sequentially (``jobs/loads`` first, then ``jobs/minions``,
    # then ``jobs/endtimes``, then ``jobs/nocache``).  Waiting on a
    # single bank's contents would return as soon as that bank
    # completed and race the in-flight chunks for the rest; wait on the
    # operator-facing sentinel instead, which only flips to
    # ``complete=True`` once every peer has eof'd every channel.
    import pathlib

    sentinel_path = (
        pathlib.Path(cluster_master_1_isolated.config["cachedir"])
        / "cluster-collect-status.json"
    )

    def _sentinel_complete():
        if not sentinel_path.exists():
            return False
        try:
            with salt.utils.files.fopen(sentinel_path) as fp:
                doc = json.load(fp)
        except (OSError, json.JSONDecodeError):
            return False
        return doc.get("complete") is True

    assert _wait_until(
        _sentinel_complete, timeout=60
    ), "collect status sentinel did not reach complete=True"

    # Now that every peer has eof'd every channel, master 1 holds the
    # full keyspace across every default bank.
    cache_1 = _master_cache(cluster_master_1_isolated)
    assert set(cache_1.list("jobs/loads")) == set(seeded), (
        f"master 1 missing jobs/loads entries: "
        f"{sorted(set(seeded) - set(cache_1.list('jobs/loads')))}"
    )
    assert set(cache_1.list("jobs/minions")) == set(seeded), (
        f"master 1 missing jobs/minions entries: "
        f"{sorted(set(seeded) - set(cache_1.list('jobs/minions')))}"
    )

    # Phase 5: clear route + destroy ring.
    _run_runner(cluster_master_1_isolated, "cluster.route_clear", "data_type=jobs")
    _run_runner(cluster_master_1_isolated, "cluster.ring_destroy", "name=jobs")

    def _cleanup_visible():
        for master in masters:
            log_path = master.config.get("log_file")
            try:
                with salt.utils.files.fopen(log_path) as fp:
                    text = fp.read()
            except OSError:
                return False
            if "route cleared — data_type=jobs now broadcasts" not in text:
                return False
            if "status=destroyed" not in text:
                return False
        return True

    assert _wait_until(
        _cleanup_visible, timeout=30
    ), "route_clear / ring_destroy not visible on every master"

    # Cluster stayed healthy through the whole churn — voter set
    # unchanged, leader still present.
    final = _run_runner(cluster_master_1_isolated, "cluster.members")
    assert isinstance(final, dict)
    assert sorted(final.get("voters") or []) == sorted(addrs)
    assert final.get("leader_id") in addrs


def test_shed_unowned_dry_run_preserves_state(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    ``cluster.shed_unowned dry_run=True`` reports the partition but
    leaves the on-disk state untouched.  Operators must be able to
    preview before committing.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    addrs = [m.config["interface"] for m in masters]

    # Baseline.
    def _baseline():
        view = _run_runner(cluster_master_1_isolated, "cluster.members")
        return isinstance(view, dict) and sorted(view.get("voters") or []) == sorted(
            addrs
        )

    assert _wait_until(_baseline, timeout=60)

    # Seed master 1 with a small set.
    cache = _master_cache(cluster_master_1_isolated)
    jids = [f"dryrun-{i:04d}" for i in range(20)]
    for jid in jids:
        cache.store("jobs/loads", jid, {"fun": "x"})

    # Create + route.
    _run_runner(
        cluster_master_1_isolated,
        "cluster.ring_create",
        "name=jobs_dry",
        f"voters={json.dumps(addrs)}",
    )
    _run_runner(
        cluster_master_1_isolated,
        "cluster.route_set",
        "data_type=jobs",
        "ring=jobs_dry",
    )

    def _ring_ready():
        log_path = cluster_master_1_isolated.config.get("log_file")
        try:
            with salt.utils.files.fopen(log_path) as fp:
                return "ring=jobs_dry status=active" in fp.read()
        except OSError:
            return False

    assert _wait_until(_ring_ready, timeout=45)

    # Dry-run shed.
    result = _run_runner(
        cluster_master_1_isolated,
        "cluster.shed_unowned",
        "ring=jobs_dry",
        "dry_run=True",
    )
    assert result["status"] == "ok"
    assert result["dry_run"] is True
    assert result["dropped"] > 0

    # Cache is untouched: every seeded JID is still present.
    assert set(cache.list("jobs/loads")) >= set(
        jids
    ), "dry_run shed_unowned dropped state it shouldn't have"

    # Cleanup.
    _run_runner(cluster_master_1_isolated, "cluster.route_clear", "data_type=jobs")
    _run_runner(cluster_master_1_isolated, "cluster.ring_destroy", "name=jobs_dry")
