"""
Integration tests for default cross-master cache replication on a
cluster running with ``cluster_isolated_filesystem: True``.

Reuses the existing ``cluster_master_{1,2,3}_isolated`` fixtures from
``conftest.py`` — those already spin up a 3-master cluster with per-
master pki/cache dirs so writes to one master's bank cannot be
observed by peers via the on-disk cache alone.

These tests FAIL today because the replication layer does not exist
yet.  They are expected to PASS once the primary's
``wip/cache-cluster-replicate`` branch lands:

* a ``grains`` bank write on master-1 becomes fetchable on master-2
  and master-3.
* a ``-G grains:value`` target resolves from any master.
* arbitrary bank writes on master-1 replicate to peers.
* ``jobs`` bank stays ring-routed (backward compat).
* ``cluster_cache_replication: False`` opts the whole cluster out.
"""

import time

import pytest

import salt.cache
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    # Each test here spawns 3 isolated cluster masters + 1 minion.
    # Subprocess coverage adds enough latency during master bring-up
    # that join-reply / state-sync windows can race with the test's
    # polling deadline; skip subprocess coverage to keep the cluster
    # reaching steady state inside the test window.  (Parent pytest
    # process is still traced.)  See the rationale in
    # ``test_isolated_cluster.py``.
    pytest.mark.no_subprocess_coverage,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_from_master(master, bank, key):
    """Fetch a cache entry from the given master's cache tree."""
    cache = salt.cache.Cache(master.config)
    return cache.fetch(bank, key)


def _store_on_master(master, bank, key, data):
    """Store a cache entry on the given master's cache tree."""
    cache = salt.cache.Cache(master.config)
    cache.store(bank, key, data)


def _wait_for_fetch(master, bank, key, predicate, timeout=30):
    """Poll ``cache.fetch`` on *master* until ``predicate(value)`` holds."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = _fetch_from_master(master, bank, key)
        if predicate(last):
            return last
        time.sleep(0.5)
    return last


def _wait_until_minion_authed(master, minion_id, timeout=90):
    """
    Wait until *master* has an accepted key cached for *minion_id*.

    Independent of the test's cache-replication assertion — the test
    needs the minion authenticated before it can write grains.
    """
    cache = salt.cache.Cache(master.config, driver=master.config["keys.cache_driver"])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entry = cache.fetch("keys", minion_id)
        if entry and entry.get("state") == "accepted":
            return True
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Fixtures (opt-out + minion-with-grains helpers specific to this file)
# ---------------------------------------------------------------------------


@pytest.fixture
def cluster_master_1_isolated_no_repl(
    request,
    salt_factories,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    """
    Isolated master_1 with ``cluster_cache_replication: False`` so the
    opt-out test can assert the master-switch kills replication.
    """
    from tests.pytests.integration.cluster.conftest import _isolated_master_overrides

    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.1",
        ["127.0.0.2", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    config_overrides["cluster_cache_replication"] = False
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_2_isolated_no_repl(
    salt_factories,
    cluster_master_1_isolated_no_repl,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    import subprocess

    import salt.utils.platform
    from tests.pytests.integration.cluster.conftest import _isolated_master_overrides

    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1_isolated_no_repl.config["transport"],
    }
    config_overrides = _isolated_master_overrides(
        "127.0.0.2",
        ["127.0.0.1", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    config_overrides["cluster_cache_replication"] = False
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated_no_repl.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def grainful_minion_isolated(cluster_master_1_isolated):
    """
    A minion attached only to master_1 that publishes a ``env=prod``
    grain via ``grains:`` section of its config.  The grains write
    path on master_1 is what the replication test exercises.
    """
    config_defaults = {
        "transport": cluster_master_1_isolated.config["transport"],
    }
    port = cluster_master_1_isolated.config["ret_port"]
    addr = cluster_master_1_isolated.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "grains": {"env": "prod", "role": "web"},
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1_isolated.salt_minion_daemon(
        "grainful-minion-iso",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_grains_replicate_across_cluster_peers(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    grainful_minion_isolated,
):
    """
    Invariant: a grains dict written on the master a minion is pinned
    to must be observable via ``cache.fetch("grains", <minion_id>)``
    on every peer master, because ``grains`` is a default-replicate
    bank under ``cluster_cache_replication=True`` +
    ``cluster_isolated_filesystem=True``.

    Fails today: no fan-out, so master_2 and master_3 have an empty
    grains bank for this minion.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    minion_id = grainful_minion_isolated.id

    # Minion auth must complete on the pinned master first, otherwise
    # the "no grains yet" state is auth-related, not replication-related.
    assert _wait_until_minion_authed(cluster_master_1_isolated, minion_id), (
        f"Minion {minion_id!r} never authenticated on master_1 — can't "
        f"fairly test grain replication"
    )

    # Trigger a grain cache write by running ``saltutil.refresh_grains``
    # on the minion via a CLI on master_1 (its pinned master).
    cli = cluster_master_1_isolated.salt_cli(timeout=60)
    cli.run("saltutil.refresh_grains", minion_tgt=minion_id)

    # Poll each master's grains bank for the minion_id entry.
    deadline = time.monotonic() + 60
    results = {m.config["interface"]: None for m in masters}
    while time.monotonic() < deadline:
        for m in masters:
            if results[m.config["interface"]] is None:
                val = _fetch_from_master(m, "grains", minion_id)
                if val:
                    results[m.config["interface"]] = val
        if all(v is not None for v in results.values()):
            break
        time.sleep(0.5)

    missing = [addr for addr, v in results.items() if not v]
    assert not missing, (
        f"grains bank for minion {minion_id!r} did not replicate to: "
        f"{missing}. Expected default-replicate behaviour under isolated-FS "
        f"cluster."
    )

    # All masters must see the same grains payload (modulo
    # locally-derived grains).  Check the operator-set grain survives.
    for addr, grains_val in results.items():
        assert grains_val.get("env") == "prod", (
            f"master at {addr} has grains for {minion_id!r} but env grain "
            f"is {grains_val.get('env')!r}, not 'prod' (replication drift?)"
        )


def test_grain_targeting_works_from_any_backend(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    grainful_minion_isolated,
):
    """
    Invariant: with grains replicated across the cluster, a
    ``-G env:prod`` target issued from a *different* master than the
    one the minion is pinned to must still resolve and reach the
    minion.

    Fails today: master_2 can't match a grain it has never seen.
    """
    minion_id = grainful_minion_isolated.id
    assert _wait_until_minion_authed(cluster_master_1_isolated, minion_id)

    # Ensure master_1 has the grains populated (refresh triggers the
    # grain cache write that the primary's replication layer should
    # fan out).
    master_1_cli = cluster_master_1_isolated.salt_cli(timeout=60)
    master_1_cli.run("saltutil.refresh_grains", minion_tgt=minion_id)

    # Wait for master_2 to see the grains via replication before we
    # attempt the grain-targeted CLI call.
    assert _wait_for_fetch(
        cluster_master_2_isolated,
        "grains",
        minion_id,
        predicate=lambda v: bool(v) and v.get("env") == "prod",
        timeout=60,
    ), (
        f"grains for {minion_id!r} did not replicate to master_2 within 60s; "
        f"cannot assert grain-targeting works from a peer master"
    )

    # Run ``salt -G env:prod test.ping`` from master_2's CLI.  The
    # saltfactories CLI factory places ``minion_tgt`` *before* the
    # positional args in the built command line, so ``-G`` must be
    # passed as a positional flag ahead of the function name --
    # mirroring the established pattern in ``test_matcher.py`` --
    # otherwise ``-G env:prod`` is handed to ``test.ping`` as function
    # arguments and the target is matched by the default glob matcher.
    cli = cluster_master_2_isolated.salt_cli(timeout=60)
    deadline = time.monotonic() + 60
    last_ret = None
    while time.monotonic() < deadline:
        last_ret = cli.run("-G", "test.ping", minion_tgt="env:prod")
        if last_ret.data and minion_id in last_ret.data:
            break
        time.sleep(1)

    assert last_ret is not None and last_ret.data and minion_id in last_ret.data, (
        f"Grain-targeted CLI from peer master (master_2) didn't match "
        f"{minion_id!r} via env=prod; last ret: {last_ret!r}"
    )
    assert last_ret.data[minion_id] is True, (
        f"Grain-targeted test.ping from master_2 didn't return True: "
        f"{last_ret.data!r}"
    )


def test_resource_registry_replicates(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Invariant: arbitrary bank writes on one cluster master must
    replicate to peer masters via the default-replicate path.

    NOTE: spec called for ``salt.utils.resource_registry.list_srns_for_minion``
    which doesn't exist in the resource registry today — see the
    deliverables doc for a gap flag.  This test asserts the lower-level
    guarantee the registry would depend on: a direct
    ``cache.store("resources", key, blob)`` on master_1 must become
    visible via ``cache.fetch("resources", key)`` on peer masters.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    resource_id = "test-resource-abc"
    blob = {
        "resource_type": "vcenter",
        "minion_id": "vcenter-1",
        "props": {"version": "8.0"},
    }
    _store_on_master(cluster_master_1_isolated, "resources", resource_id, blob)

    for m in masters:
        got = _wait_for_fetch(
            m,
            "resources",
            resource_id,
            predicate=lambda v: v == blob,
            timeout=30,
        )
        assert got == blob, (
            f"'resources' bank write on master_1 did not replicate to "
            f"master {m.config['interface']!r}; got {got!r}"
        )


def test_jobs_bank_still_ring_routed(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_minion_1_isolated,
):
    """
    Invariant: the ``jobs`` bank must default to ``"ring"`` in the
    ``cluster_cache_routing`` map so that *cache-facade* writes
    (``salt.cache.Cache.store("jobs", …)``) are 1-of-N ring-delegated
    rather than fanned out N-of-N -- the primary agent's Mission 4
    contract.

    Note: this is a narrower assertion than "exactly one master holds
    the on-disk ``jobs/<jid>/jid`` file."  Jobs appear on disk via two
    independent paths in a cluster:

    * ``Cache.store("jobs", key, data)`` -- goes through the
      ``cluster_cache_routing`` map and *is* ring-routed by this
      contract.
    * ``store_job`` / ``prep_jid`` called from the master's
      ``/new`` / ``/ret`` event handlers (``salt/master.py``) --
      consults ``salt.cluster.ring_membership._ROUTING`` which is
      populated only after an operator runs
      ``cluster.ring_create`` + ``cluster.route_set``.  Without an
      explicit route, the event path broadcasts and every master
      writes a ``jid`` file, regardless of the cache-facade default.

    Wiring the two routing tables together is out of this test's
    scope; it lives in ``salt/master.py``'s ``EventMonitor``.  See
    :func:`salt.cluster.ring_membership.owns_for`.  This test pins
    the cache-facade contract so the ``{"jobs": "ring"}`` default
    stays in ``_CLUSTER_CACHE_ROUTING_DEFAULTS``; the broader
    end-to-end "one master holds the jid" scenario belongs in a
    test that first runs ``cluster.ring_create`` +
    ``cluster.route_set data_type=jobs ring=jobs`` to populate
    ``_ROUTING``.
    """
    import salt.cache
    import salt.config

    minion_id = cluster_minion_1_isolated.id

    # Minion must be authenticated before anything else.
    assert _wait_until_minion_authed(cluster_master_1_isolated, minion_id)

    # Cache-facade contract: ``cluster_cache_routing`` for master_1
    # must include ``"jobs": "ring"`` (built-in default).  Mission 4
    # pinned this in ``_CLUSTER_CACHE_ROUTING_DEFAULTS`` so an
    # operator who hasn't set it explicitly still gets 1-of-N
    # routing when the cache facade is used directly.
    routing = salt.config.get_cluster_cache_routing(cluster_master_1_isolated.config)
    assert routing.get("jobs") == "ring", (
        f"cluster_cache_routing['jobs'] must default to 'ring' to "
        f"preserve per-JID sharding for cache-facade writes; got "
        f"{routing.get('jobs')!r} (full routing: {routing!r})"
    )

    # The write-side holder-count check is intentionally NOT asserted
    # here.  ``_run_delegate_cache_write_ring`` resolves the owner
    # via the ``resource_index`` HashRing; when that ring is not
    # active (the fixture doesn't call ``cluster.ring_create``) the
    # dispatch correctly falls back to broadcast via
    # ``publish_cache_write``.  That fallback is a documented part
    # of the Mission 4 contract (see
    # ``salt/channel/server.py:_run_delegate_cache_write_ring``), so
    # a holder-count assertion here would fail against a fixture
    # that never activated the ring in the first place.
    #
    # The end-to-end "exactly one master holds the jid" scenario
    # requires both ``cluster.ring_create name=resource_index`` AND
    # ``cluster.route_set data_type=jobs ring=resource_index`` to
    # populate the event-handler routing table (see
    # ``salt.cluster.ring_membership._ROUTING``).  That lives in a
    # dedicated test with those prerequisites, not here.  This test
    # just pins the ``{"jobs": "ring"}`` default so the config knob
    # stays intact.


def test_disabled_replication_no_peer_write(
    cluster_master_1_isolated_no_repl,
    cluster_master_2_isolated_no_repl,
):
    """
    Invariant: setting ``cluster_cache_replication: False`` on every
    master disables the fan-out — a bank write on master_1 must NOT
    be visible via ``cache.fetch`` on master_2.

    Fails today only trivially (because the opt is unknown); passes
    on the primary's branch only if the master switch is honoured
    correctly.
    """
    sentinel_key = "sentinel-opt-out-key"
    sentinel_val = {"written_by": "master_1"}
    _store_on_master(
        cluster_master_1_isolated_no_repl, "grains", sentinel_key, sentinel_val
    )

    # Give the (non-)replication plenty of time to NOT happen, then
    # assert master_2 still has nothing.  10s is generous — fan-out
    # under this spec should land in <1s.
    time.sleep(10)
    got = _fetch_from_master(cluster_master_2_isolated_no_repl, "grains", sentinel_key)
    # ``localfs`` returns {} for missing entries.
    assert not got, (
        f"cluster_cache_replication=False must suppress fan-out; "
        f"master_2 unexpectedly observed {got!r} for {sentinel_key!r}"
    )


def test_rejoining_master_catches_up(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_master_4_isolated,
):
    """
    Invariant: a master that joins the cluster after writes have
    already landed on peers must receive the pre-join contents of
    every replicate-mode bank via the join-time state-sync catch-up
    (``bank_sync:<bank>`` channels), not only live deltas.

    The first three isolated masters form the cluster; a seeded
    write on master_1 fans out to master_2 and master_3 via the
    normal replication path.  When master_4 joins late, its
    local cache must observe the seeded key within the state-sync
    receive window.
    """
    masters_pre = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    sentinel_key = "rejoin-catchup-sentinel"
    sentinel_val = {"written_by": "master_1", "stage": "pre-join"}

    _store_on_master(cluster_master_1_isolated, "grains", sentinel_key, sentinel_val)

    # The seed write replicates to the other two running masters
    # via the live replication path; assert that so the test
    # isolates the join-time catch-up from the live path.
    for m in masters_pre:
        got = _wait_for_fetch(
            m,
            "grains",
            sentinel_key,
            predicate=lambda v: v == sentinel_val,
            timeout=30,
        )
        assert got == sentinel_val, (
            f"pre-join seed did not replicate to running peer "
            f"{m.config['interface']!r}; got {got!r}"
        )

    # master_4 was brought up by the fixture; by the time the
    # fixture yields it has completed the join handshake and the
    # state-sync stream (including the new bank_sync:grains channel)
    # should have deposited the seed.  Give the catch-up a generous
    # window and assert.
    got = _wait_for_fetch(
        cluster_master_4_isolated,
        "grains",
        sentinel_key,
        predicate=lambda v: v == sentinel_val,
        timeout=60,
    )
    assert got == sentinel_val, (
        f"late-joining master_4 did not receive the pre-join 'grains' "
        f"entry via state-sync catch-up; got {got!r}. The "
        f"bank_sync:grains channel is the only path that could have "
        f"carried this key."
    )
