"""
Scenario tests for publish-daemon ownership failover WITHIN a
3008.x master cluster.

Scope
-----
Both scenarios here exercise a 3-peer 3008.x cluster (``east``) and
a solo master (``hq``), with bidirectional peering.  Operator on
``hq`` originates publishes targeted at ``east``; the publish is
forwarded through the single peer in ``east`` that currently owns
the publish-daemon role.  The scenarios then move or restart that
ownership and observe where breadcrumb state ends up.

These tests are DIFFERENT from the solo-master restart test in
``test_failure_scenarios.py::test_publish_daemon_restart_preserves_breadcrumbs``:

* That test restarts the publish daemon on a *solo* master and
  verifies that the on-disk mmap survives one Python-process
  lifetime boundary --- a correctness property that holds
  regardless of cluster topology.
* The scenarios here operate on a *multi-peer* cluster.  Scenario
  1 moves the publish-daemon role between peers; scenario 2
  restarts the role on the same peer in a clustered deployment to
  show that the stickiness/recovery guarantee is not accidentally
  broken by Raft wiring.

RFC decision pinned by scenario 1
---------------------------------
The RFC's "Unresolved questions > Transit-cluster breadcrumb
failover (DECISION NEEDED)" lists three candidate behaviors for
what happens when a transit cluster's publish-daemon owner dies
mid-flight:

* **(mA) Batched Raft breadcrumbs on transit** --- every
  breadcrumb is both written locally AND enqueued to a batched
  Raft propose, so a new owner replays committed entries into its
  cache.
* **(mB) Peer-shared breadcrumb mmap via file_sync** ---
  breadcrumbs stay per-process writer but the on-disk file is
  replicated between peers (naturally when
  ``cluster_isolated_filesystem: False``, or via
  :mod:`salt.cluster.file_sync`).
* **(mC) Document as known limitation** --- accept transit-
  failover parity with syndic.  Operator can retrieve returns
  that landed at the transit cluster via
  ``salt-run jobs.lookup_jid`` on that cluster.

**Scenario 1 asserts the CURRENT observed behavior is (mC)**:
in a cluster with isolated per-peer ``pki_dir`` (the mode the
functional harness provisions via ``make_cluster`` and the mode
production deployments use with
``cluster_isolated_filesystem: True``), the breadcrumb written at
peer1 is not visible to peer2 after failover.  No Raft replication
of breadcrumbs (mA), no file_sync replication (mB).  The post-
failover owner has an empty cache.

Scenario 2 is topology-independent in the sense that the same
guarantee (on-disk mmap survives a Python-process boundary) is
expected to hold in both solo and clustered modes; the clustered
version is tested here to catch Raft wiring regressions that
could invalidate the restart-recovery claim for a clustered
master.

Harness notes
-------------
* Phase 5 wiring from
  :class:`salt.channel.server.MasterPubServerChannel._publish_daemon`
  to :func:`salt.topology.link_manager.start` is partial, so the
  scenarios drive :mod:`salt.topology.link_manager` in-process
  against the harness fixtures' real pki_dirs rather than through
  the salt-master pre_fork path.  The ``single_cluster`` fixture
  still spins up real salt-master daemons so pki_dir conventions,
  port reservation, and ``topology.conf`` loading all behave
  exactly as they will in production; the publish-daemon-side
  wiring is simulated by calling
  :func:`salt.topology.link_manager.start` / ``stop`` directly
  against each peer's opts.
* Only ONE in-process link_manager is wired at a time.  Both
  scenarios ``stop`` on the current peer before ``start`` on the
  failover peer, so the ``_OWNER_PID`` module guard remains
  satisfied.  In production the publish-daemon role is likewise
  held by a single peer at a time; this simulation is faithful.
* The harness extensions used here (``master_opts(peer_index)``,
  ``inspect_breadcrumbs(peer_index)``,
  ``breadcrumb_mmap_paths(peer_index)``) all default
  ``peer_index=0`` so prior callers of
  :class:`TopologyCluster` are unaffected.
"""

import logging

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod
from salt.topology.link import LinkHealth

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,  # fork(2) + fcntl.FD_CLOEXEC in link_manager
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _StubInboundLink:
    """
    Minimal :class:`PeerMasterLink` stand-in for breadcrumb recording.

    The router's :meth:`record_breadcrumb` only reads
    ``peer_cluster_id`` off the inbound link; this lightweight stub
    keeps the test boundary at the breadcrumb lifecycle without
    needing a full handshake handshake machinery.  Mirrors the
    stub used by ``test_failure_scenarios`` scenario 1.
    """

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = LinkHealth.CONNECTED


@pytest.fixture
def clean_link_manager(monkeypatch):
    """
    Reset :mod:`salt.topology.link_manager` and
    :mod:`salt.topology.router` module globals before and after
    each scenario so a leftover ``_OWNER_PID`` or ``_ROUTER`` from
    a prior test does not short-circuit the sequence of
    ``start`` / ``stop`` cycles these scenarios perform.
    """
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    # Best-effort final stop; if a scenario errored mid-stream the
    # module state must still return to a known-clean baseline.
    try:
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(link_manager.stop())
        finally:
            loop.close()
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


# ===========================================================================
# Scenario 1: publish-daemon ownership moves peer1 -> peer2 mid-flight
# ===========================================================================


def test_publish_daemon_ownership_moves_mid_flight_pins_mC(
    single_cluster, single_master, clean_link_manager, monkeypatch
):
    """
    Scenario 1 --- Publish-daemon ownership failover mid-flight.

    Setup: 3-peer cluster ``east`` + solo master ``hq``, with
    bidirectional peering.  The operator on ``hq`` originates
    ``salt '*' test.ping`` targeted at ``east``; the publish is
    forwarded from ``hq`` to ``east``'s publish-daemon owner
    (peer1).  ``east`` peer1 writes a breadcrumb for the inbound
    jid --- the hint that a future return from an ``east`` minion
    must be forwarded back upstream to ``hq`` rather than consumed
    locally.

    Mid-flight (after the publish is received at ``east`` peer1
    but before ``east``'s minions return), ``east`` peer1's
    publish daemon is stopped.  ``east``'s cluster fails over the
    publish-daemon role to peer2.  Returns from ``east``'s minions
    will now arrive at peer2's publish daemon.

    This test pins the CURRENT observed behavior of the three
    options documented in the RFC's "Transit-cluster breadcrumb
    failover (DECISION NEEDED)" section:

    * **(mA) Batched Raft breadcrumbs on transit** --- NOT
      observed.  There is no breadcrumb replication through the
      Raft log in the current implementation.  If (mA) were
      active, peer2's breadcrumb cache after failover would
      contain the jid recorded at peer1 (modulo a <=100ms gap).
    * **(mB) Peer-shared breadcrumb mmap via file_sync** --- NOT
      observed.  The functional harness provisions each peer with
      its own ``pki_dir``; breadcrumbs live under
      ``pki_dir/master/topology_breadcrumbs.mmap`` which is
      per-peer.  No file_sync replication of this file is in
      the implementation.
    * **(mC) Document as known limitation** --- observed.  The
      breadcrumb written at peer1 remains on peer1's disk but is
      invisible to peer2 after failover; a return arriving at
      peer2 would be stored locally with no upstream forwarding.
      This matches syndic parity.

    Verification steps:

    1. Spin up a 3-peer ``east`` cluster and a solo ``hq``.
    2. Peer them bidirectionally (``accept_peer`` both ways).
    3. Drive the in-process publish daemon on ``east`` peer1 and
       record a breadcrumb for the inbound ``hq`` -> ``east``
       publish --- this is the "peer1 is the publish-daemon
       owner, hq just forwarded jid X" state.
    4. Snapshot peer1's breadcrumb cache (shows the entry) and
       peer2's breadcrumb cache (empty --- peer2 is not the
       owner).
    5. Stop peer1's publish daemon.  Peer1's on-disk mmap file
       must persist (RFC-documented restart-recovery guarantee).
    6. Start the in-process publish daemon on ``east`` peer2
       (the failover target).
    7. Snapshot peer2's breadcrumb cache again --- it is STILL
       empty.  This is the key assertion that pins (mC).
    8. Attempt a breadcrumb lookup on peer2 for the pre-failover
       jid --- returns ``None``.  A return arriving at peer2
       cannot be routed back to ``hq`` using the breadcrumb
       table alone.
    9. Snapshot peer1's breadcrumb cache (via its on-disk mmap)
       --- the pre-failover entry is still there, but peer1's
       publish daemon is down so no return can land at peer1
       either.  The entry is effectively orphaned until operator
       intervention (RFC's ``jobs.lookup_jid`` recommendation).

    If the implementation later adopts (mA) or (mB), this test
    will FAIL in a loud and obvious way at step 7 (peer2's cache
    is no longer empty).  Update the assertion to match the new
    behavior AND update the RFC's "Unresolved questions" section
    to record which option was chosen.
    """
    east = single_cluster("east", peer_count=3)
    hq = single_master(cluster_id="hq")

    # Bidirectional peering: hq accepts east, east accepts hq.
    # In the harness, ``accept_peer`` drops the peer's identity
    # pub into the acceptor's ``masters/`` dir.  For a 3-peer
    # cluster this ``masters/`` dir is per-peer (not shared);
    # ``accept_peer`` writes to peer0's dir only.  That is
    # sufficient for this test because the breadcrumb path never
    # crosses the ``masters/`` acceptance check.
    east.accept_peer(hq)
    hq.accept_peer(east)

    # Phase 1: east peer1 is the publish-daemon owner.  Drive the
    # in-process link_manager against peer1's pki_dir and record
    # a breadcrumb for the in-flight hq -> east publish.
    jid = "20260101000000000001"

    loop1, _opts1 = east.start_publish_daemon(peer_index=1)
    try:
        router1 = router_mod.get_router()
        assert router1 is not None, (
            "start_publish_daemon(peer_index=1) must wire the router "
            "against east peer1's pki_dir"
        )
        router1.record_breadcrumb(jid, _StubInboundLink("hq"), timeout=30)

        # Peer1 sees the breadcrumb it just wrote.
        peer1_before = east.inspect_breadcrumbs(peer_index=1)
        assert any(
            c["jid"] == jid and c["link_cluster_id"] == "hq" for c in peer1_before
        ), (f"peer1 must see its own just-written breadcrumb; got " f"{peer1_before!r}")

        # Peer2 does NOT see the breadcrumb --- it is not the
        # publish-daemon owner at this point and has no breadcrumb
        # file of its own yet.  This part of the assertion is the
        # "pre-failover baseline" that pins the per-peer file
        # observation.
        peer2_pre_failover = east.inspect_breadcrumbs(peer_index=2)
        assert not any(c["jid"] == jid for c in peer2_pre_failover), (
            f"peer2 must NOT see peer1's breadcrumb before failover "
            f"(per-peer pki_dir, no cross-peer breadcrumb replication); "
            f"got {peer2_pre_failover!r}"
        )
    finally:
        east.stop_publish_daemon(loop1)

    # Phase 2: peer1's on-disk mmap files MUST persist across the
    # stop.  Breadcrumbs are per-peer-pki_dir and tied to on-disk
    # files, not to the Python-process lifetime.
    peer1_paths = east.breadcrumb_mmap_paths(peer_index=1)
    for key in ("index", "heap", "roster"):
        assert peer1_paths[key].exists(), (
            f"peer1 breadcrumb {key} file missing after stop_publish_daemon; "
            f"restart-recovery guarantee broken"
        )

    # Document which breadcrumb files peer2 has BEFORE failover.
    # Each peer's salt-master runs ``link_manager.pre_fork`` on
    # startup which pre-creates ``topology_breadcrumbs.mmap`` on
    # that peer's ``pki_dir``.  So on the current harness the file
    # EXISTS on peer2 even before peer2 ever owned the publish
    # daemon --- but the file is EMPTY (no entries).  That matters
    # for the (mC) pin below: we assert on cache CONTENTS, not on
    # file existence.
    peer2_paths = east.breadcrumb_mmap_paths(peer_index=2)
    peer2_pki_dir = peer2_paths["index"].parent
    peer1_pki_dir = peer1_paths["index"].parent
    assert peer2_pki_dir != peer1_pki_dir, (
        f"test harness has silently become shared-pki_dir "
        f"(peer1 pki_dir {peer1_pki_dir!r} == peer2 pki_dir "
        f"{peer2_pki_dir!r}); the (mC) assertion below is only "
        f"meaningful on isolated per-peer pki_dirs --- scope the "
        f"test or update it to match the new harness shape"
    )
    log.info(
        "scenario 1: pre-failover file layout confirmed per-peer "
        "(peer1 pki_dir=%s, peer2 pki_dir=%s); peer2 breadcrumb "
        "index exists=%s (pre_create materialises an empty file "
        "regardless of publish-daemon ownership)",
        peer1_pki_dir,
        peer2_pki_dir,
        peer2_paths["index"].exists(),
    )

    # Phase 3: failover.  East cluster elects peer2 as the new
    # publish-daemon owner.  Simulate by resetting module state
    # and starting the in-process link_manager against peer2's
    # pki_dir.
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)

    loop2, _opts2 = east.start_publish_daemon(peer_index=2)
    try:
        router2 = router_mod.get_router()
        assert router2 is not None, (
            "start_publish_daemon(peer_index=2) must wire the router "
            "against east peer2's pki_dir after failover"
        )

        # Phase 3a: peer2's breadcrumb cache is EMPTY of the pre-
        # failover jid.  This is the (mC) pin: no Raft
        # replication, no file_sync, no cross-peer visibility.
        peer2_after_failover = east.inspect_breadcrumbs(peer_index=2)
        peer2_has_pre_failover_jid = any(c["jid"] == jid for c in peer2_after_failover)
        assert peer2_has_pre_failover_jid is False, (
            f"scenario 1 pins (mC): peer2's breadcrumb cache after "
            f"failover must NOT contain the pre-failover jid; the "
            f"current implementation has no cross-peer breadcrumb "
            f"replication.  If this test fails, the implementation "
            f"has grown (mA) or (mB) behavior --- update the RFC's "
            f"'Transit-cluster breadcrumb failover' section to "
            f"record the chosen option and update this test "
            f"accordingly.  peer2 breadcrumbs after failover: "
            f"{peer2_after_failover!r}"
        )

        # Phase 3b: an inbound return at peer2 cannot be routed
        # back to hq using the breadcrumb table.  Confirm via the
        # module-level lookup.
        resolved_at_peer2 = breadcrumbs.lookup(
            router2._breadcrumbs,  # pylint: disable=protected-access
            jid,
        )
        assert resolved_at_peer2 is None, (
            f"scenario 1 pins (mC): peer2.lookup({jid!r}) must "
            f"return None after failover (no inherited breadcrumb); "
            f"got {resolved_at_peer2!r}.  A non-None result "
            f"indicates mA or mB has been implemented."
        )
    finally:
        east.stop_publish_daemon(loop2)

    # Phase 4: peer1's breadcrumb entry is still on disk even
    # though peer1's publish daemon is stopped.  Operator-driven
    # recovery (``salt-run jobs.lookup_jid`` on east peer1 host)
    # is the (mC) escape hatch; nothing in the test exercises
    # that CLI, but the on-disk evidence must be present for the
    # recovery path to work.
    for key in ("index", "heap", "roster"):
        assert peer1_paths[key].exists(), (
            f"peer1 breadcrumb {key} file disappeared after peer2 "
            f"failover; (mC) recovery depends on this file surviving"
        )


# ===========================================================================
# Scenario 2: clustered publish-daemon restart recovers breadcrumbs
# ===========================================================================


def test_clustered_publish_daemon_restart_preserves_breadcrumbs(
    single_cluster, single_master, clean_link_manager, monkeypatch
):
    """
    Scenario 2 --- Clustered publish-daemon restart recovers
    breadcrumbs via on-disk MmapCache.

    This is the within-same-peer version of the solo-master
    restart test (``test_publish_daemon_restart_preserves_breadcrumbs``
    in ``test_failure_scenarios.py``) but driven on a 3-peer
    cluster.  The point is to show that Raft wiring in the
    clustered start path does not accidentally invalidate the
    on-disk restart-recovery guarantee: breadcrumbs live in a
    per-process :class:`MmapCache` on the publish daemon
    (``pki_dir/master/topology_breadcrumbs.mmap``) and that file
    persists across a Python-process boundary.

    This test must pass regardless of the (mA)/(mB)/(mC) choice
    for cross-peer failover because it exercises the SAME peer
    across the restart, with the same ``pki_dir``, so the
    recovery path is purely "re-open the same file".

    Setup: 3-peer ``east`` cluster + solo ``hq``; bidirectional
    peering; ``east`` peer1 is the publish-daemon owner.

    Steps:

    1. east.start_publish_daemon(peer_index=1).  Record a
       breadcrumb for an in-flight hq -> east publish.
    2. east.stop_publish_daemon(peer_index=1) --- simulates peer1
       crashing.  Peer1's publish daemon is gone; the mmap file
       stays on disk.
    3. Assert the mmap files for peer1 exist.
    4. east.start_publish_daemon(peer_index=1) --- same peer
       takes the publish-daemon role again on restart (ownership
       stickiness; in-process this means we re-use the same
       pki_dir).
    5. Assert the restarted router finds the pre-crash breadcrumb
       by jid.
    6. Assert ``breadcrumbs.lookup`` on the restarted router
       returns the inbound-link cluster id --- late-arriving
       returns from east's minions still route back to hq.
    """
    east = single_cluster("east", peer_count=3)
    hq = single_master(cluster_id="hq")

    # Bidirectional peering (same mechanics as scenario 1; the
    # route back to hq only uses the breadcrumb for the inbound
    # cluster id).
    east.accept_peer(hq)
    hq.accept_peer(east)

    jid = "20260101000000000002"

    # Phase 1: peer1 is the publish-daemon owner; record a
    # breadcrumb and confirm it is visible.
    loop1, _opts1 = east.start_publish_daemon(peer_index=1)
    try:
        router1 = router_mod.get_router()
        assert (
            router1 is not None
        ), "start_publish_daemon(peer_index=1) must wire the router"
        router1.record_breadcrumb(jid, _StubInboundLink("hq"), timeout=30)

        peer1_before = east.inspect_breadcrumbs(peer_index=1)
        assert any(
            c["jid"] == jid and c["link_cluster_id"] == "hq" for c in peer1_before
        ), f"peer1 breadcrumb not recorded before crash: {peer1_before!r}"
    finally:
        east.stop_publish_daemon(loop1)

    # Phase 2: the mmap files for peer1 persist across the stop.
    peer1_paths = east.breadcrumb_mmap_paths(peer_index=1)
    for key in ("index", "heap", "roster"):
        assert peer1_paths[key].exists(), (
            f"peer1 breadcrumb {key} file missing after shutdown; "
            f"restart-recovery guarantee broken on a clustered master"
        )

    # Phase 3: restart --- same peer takes the publish-daemon role
    # again.  Breadcrumb must still be visible and routable.
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)

    loop2, _opts2 = east.start_publish_daemon(peer_index=1)
    try:
        router2 = router_mod.get_router()
        assert router2 is not None, "restarted publish daemon must re-wire the router"

        peer1_after = east.inspect_breadcrumbs(peer_index=1)
        assert any(
            c["jid"] == jid and c["link_cluster_id"] == "hq" for c in peer1_after
        ), (
            f"restarted breadcrumb lookup missed pre-crash entry on "
            f"clustered peer1: {peer1_after!r}"
        )

        # Verify the restarted router's module-level lookup
        # resolves the pre-crash jid to its inbound-link cluster
        # id.  Mirrors the solo-master restart test's final
        # assertion; the clustered start path adds Raft wiring
        # between ``open_writer`` and the router construction,
        # and that wiring must not invalidate the lookup path.
        resolved = breadcrumbs.lookup(
            router2._breadcrumbs,  # pylint: disable=protected-access
            jid,
        )
        assert resolved == "hq", (
            f"breadcrumbs.lookup after clustered-peer restart "
            f"returned {resolved!r}; expected 'hq' (the pre-crash "
            f"inbound-link cluster id)"
        )
    finally:
        east.stop_publish_daemon(loop2)
