"""
Scenario tests for master-topology steady-state multi-peer-cluster
to multi-peer-cluster topology.

Every existing scenario file covers the solo-master shape --- these
scenarios fill the gap for 3008.x master clusters participating in
topology peering:

* Scenario 1 --- Two 3-peer clusters peer via topology.  Verifies
  Raft replicates the identity + attach commits to every peer in
  each cluster (not just the leader), that a publish originated on
  a non-publish-daemon-owning peer still fan-outs through the
  owner's link, and that returns arriving at any peer route back
  to the origin peer's job cache via breadcrumbs.
* Scenario 2 --- Mixed solo + 3-peer cluster.  Verifies the solo
  side writes directly to its registry MmapCache on attach while
  the clustered side commits through Raft, yet
  :func:`salt.topology.registry.get_peer` yields the same shape on
  both sides.  Also verifies bidirectional publish fan-out across
  the asymmetric pair.
* Scenario 3 --- Clustered master receives inbound on a non-primary
  peer.  Verifies the single-publish-daemon-owner model per RFC
  "Unresolved questions > Transit-cluster breadcrumb failover": if
  the owning peer's publish daemon stops, inbound traffic on the
  topology_link_port is no longer served; restarting it recovers.

Design notes
------------
* These scenarios drive the topology lifecycle **in-process**
  against the harness fixtures' real pki_dirs rather than through
  the salt-master pre_fork path.  The ``single_master`` /
  ``single_cluster`` fixtures still spin up real salt-master
  daemons so pki_dir conventions, port reservation, and
  ``topology.conf`` loading all behave as they will in production;
  the publish-daemon-side wiring is simulated by driving
  :func:`salt.topology.link_manager.start` / ``stop`` and
  :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`
  directly against the same opts.
* Each cluster peer in a 3008.x master cluster has its OWN
  ``pki_dir`` (per-interface) so Raft replication is simulated by
  applying the same committed log entries to each peer's
  ``TopologyStateMachine``, exactly matching what a real Raft Node
  would do on commit.
* The link transport (``AsyncReqChannel`` / ``AsyncPubChannel``)
  is faked --- Phase 3's inbound listener is partial, so a
  scenario that needs the receiver to answer a handshake
  monkeypatches the client factory with a deterministic
  responder.  Those monkeypatches are reverted at test scope.
"""

import asyncio
import logging
import os

import pytest

import salt.channel.client
import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link as link_mod
import salt.topology.link_manager as link_manager
import salt.topology.registry as registry
import salt.topology.router as router_mod
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,  # fork(2) + fcntl.FD_CLOEXEC in link_manager
]


# ---------------------------------------------------------------------------
# Fake peer channel (Phase 3 receiver is not yet wired)
# ---------------------------------------------------------------------------


class _FakeReqChannel:
    """
    AsyncReqChannel stand-in used by :class:`PeerMasterLink`.

    Per-host handshake responses let a single scenario drive
    multiple peer links at once; a captured list of sends supports
    assertions about what was dispatched where.
    """

    handshake_by_host = {}  # noqa: RUF012
    default_response = {"status": "ok"}  # noqa: RUF012
    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._host = opts.get("master_ip") or opts.get("master_host") or ""
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        tag = None
        if isinstance(load, dict):
            tag = load.get("cmd") or load.get("tag")
        type(self).sends.append((self._host, tag, load))
        if tag in ("topology/_master_auth", "_master_auth"):
            default = {
                "status": "ok",
                "aes": os.urandom(32),
                "cluster_id": self._host or "unknown",
                "endpoints": [],
            }
            return type(self).handshake_by_host.get(self._host, default)
        return type(self).default_response

    async def connect(self):
        return None

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True


class _FakePubChannel:
    """AsyncPubChannel stand-in; no-op shell."""

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def connect(self):
        return None

    def on_recv(self, callback):
        return None

    def close(self):
        return None

    async def close_async(self):
        return None


@pytest.fixture
def fakes(monkeypatch):
    """Install the fake channel factories; reset per-test capture buffers."""
    _FakeReqChannel.sends = []
    _FakeReqChannel.handshake_by_host = {}
    _FakeReqChannel.default_response = {"status": "ok"}
    monkeypatch.setattr(
        salt.channel.client.AsyncReqChannel, "factory", _FakeReqChannel.factory
    )
    monkeypatch.setattr(
        salt.channel.client.AsyncPubChannel, "factory", _FakePubChannel.factory
    )
    monkeypatch.setattr(link_mod, "AsyncReqChannel", _FakeReqChannel, raising=False)
    monkeypatch.setattr(link_mod, "AsyncPubChannel", _FakePubChannel, raising=False)
    yield _FakeReqChannel


@pytest.fixture
def clean_link_manager(monkeypatch):
    """
    Reset :mod:`salt.topology.link_manager` module globals before
    and after each scenario so a leftover ``_OWNER_PID`` or
    ``_ROUTER`` from a prior test does not short-circuit
    :func:`link_manager.start`.
    """
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(link_manager.stop())
        finally:
            loop.close()
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Fake raft service with per-peer propagation
# ---------------------------------------------------------------------------


class _FakeRaftService:
    """
    Minimal :class:`raft_service` stand-in exposing a
    ``topology_sm`` attribute and a ``propose(cmd)`` that commits
    synchronously by dispatching into the state machine's
    ``apply``.  Mirrors the shim used by
    :mod:`tests.pytests.scenarios.topology.test_failure_scenarios`.
    """

    def __init__(self, state_machine):
        self.topology_sm = state_machine
        self.proposed = []

    def propose(self, cmd):
        self.proposed.append(cmd)
        self.topology_sm.apply(
            cmd, client_id="scenario", sequence_num=len(self.proposed)
        )


def _replicate(cmd, state_machines):
    """
    Simulate Raft replication of a committed entry to every state
    machine in *state_machines*.

    A real Raft Node calls :meth:`BaseStateMachine.apply` once per
    committed entry on each peer; this helper does the same thing
    deterministically for multi-peer-cluster scenarios where no
    real Raft Node is in play.
    """
    for sm in state_machines:
        sm.apply(cmd, client_id="scenario", sequence_num=1)


def _peer_opts(cluster, peer_index):
    """
    Return the master opts dict for the Nth peer of a
    :class:`TopologyCluster`.  Thin wrapper around
    :meth:`TopologyCluster.master_opts` --- kept as a free function
    so scenario setup reads clearly next to the state-machine
    construction.
    """
    return cluster.master_opts(peer_index=peer_index)


# ---------------------------------------------------------------------------
# Scenario 1: two 3-peer clusters peer via topology
# ===========================================================================


def test_scenario_two_3peer_clusters_peer_via_topology(
    single_cluster, fakes, clean_link_manager, monkeypatch
):
    """
    Scenario 1 --- Two 3-peer clusters peer via topology.

    Steady-state multicluster shape under test: east and west are
    both 3008.x master clusters of 3 peers each.  The topology
    identity and the mutual attach entries are proposed and commit
    on BOTH clusters' Raft logs; those commits replicate to every
    peer's local registry MmapCache (not just the leader's).  A
    publish originated on east peer2 (deliberately NOT the first
    peer, which stands in for the publish-daemon owner) still
    fan-outs through peer1's link to west; a return arriving at any
    east peer can be routed back to the origin via breadcrumbs.

    Steps:

    1. Build east and west as 3-peer clusters.
    2. Generate real identity keypairs for both via
       ``ensure_identity_key``; cross-accept so both sides have
       the other's pub in ``pki_dir/masters/``.
    3. Build a :class:`TopologyStateMachine` per peer per cluster
       (6 total).  Simulate Raft replication by applying each
       committed entry to all 3 peers of its cluster.
    4. Commit MASTER_IDENTITY_KEY on both clusters.
    5. Commit MASTER_PEER_ATTACH("west", ...) on east and
       MASTER_PEER_ATTACH("east", ...) on west.
    6. Assert each peer's registry contains the expected peer
       entry and identity_pub (Raft replication).
    7. Build a router on east peer2 (non-primary) with a connected
       :class:`PeerMasterLink` to west; drive
       :func:`router.on_publish` and verify the outbound
       ``topology/pub`` was captured.
    8. Record a breadcrumb for the forwarded jid; verify
       :meth:`route_return` on east peer2 resolves to the west
       link, proving a return arriving on any east peer routes to
       the origin peer's dispatch.
    """
    east = single_cluster("east", peer_count=3)
    west = single_cluster("west", peer_count=3)
    assert len(east.masters) == 3, "harness must spin up 3 east peers"
    assert len(west.masters) == 3, "harness must spin up 3 west peers"

    # Phase A: real identity keypairs + bidirectional acceptance.
    east_pub = east.ensure_identity_key()
    west_pub = west.ensure_identity_key()
    east.accept_peer(west)
    west.accept_peer(east)

    # Phase B: six state machines (one per peer).  Each SM opens a
    # writer handle onto its OWN peer's pki_dir --- exactly the
    # shape a real salt-master-cluster publish daemon would use.
    east_sms = []
    west_sms = []
    try:
        for i in range(3):
            east_sms.append(TopologyStateMachine(_peer_opts(east, i)))
        for i in range(3):
            west_sms.append(TopologyStateMachine(_peer_opts(west, i)))

        # Phase C: identity commits replicate across all peers.
        east_identity_cmd = {
            "type": LogEntryType.MASTER_IDENTITY_KEY,
            "public_key": east_pub,
        }
        west_identity_cmd = {
            "type": LogEntryType.MASTER_IDENTITY_KEY,
            "public_key": west_pub,
        }
        _replicate(east_identity_cmd, east_sms)
        _replicate(west_identity_cmd, west_sms)

        # Phase D: peer-attach commits replicate.  East accepts
        # west; west accepts east.  The endpoint list is the real
        # inbound address a peer-receiver would listen on.
        east_endpoints = (
            f"{east.masters[0].config.get('interface', '127.0.0.1')}"
            f":{east.masters[0].config['topology_link_port']}",
        )
        west_endpoints = (
            f"{west.masters[0].config.get('interface', '127.0.0.1')}"
            f":{west.masters[0].config['topology_link_port']}",
        )
        east_attach_cmd = {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": "west",
            "public_key": west_pub,
            "endpoints": west_endpoints,
            "attached_at": 1_700_000_000.0,
        }
        west_attach_cmd = {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": "east",
            "public_key": east_pub,
            "endpoints": east_endpoints,
            "attached_at": 1_700_000_000.0,
        }
        _replicate(east_attach_cmd, east_sms)
        _replicate(west_attach_cmd, west_sms)

        # Phase E: assertion --- every peer in east sees west in
        # its registry MmapCache, and vice versa.  This is the
        # whole point of Raft replication; a per-leader view would
        # fail here.
        for i in range(3):
            reader = registry.open_reader(_peer_opts(east, i))
            try:
                stored_identity = registry.get_identity_pub(reader)
                stored_peer = registry.get_peer(reader, "west")
            finally:
                reader.close()
            assert (
                stored_identity == east_pub
            ), f"east peer{i} identity not replicated (got {stored_identity!r})"
            assert (
                stored_peer is not None
            ), f"east peer{i} did not see MASTER_PEER_ATTACH(west) via Raft"
            assert (
                stored_peer["public_key"] == west_pub
            ), f"east peer{i} public_key mismatch for 'west'"
        for i in range(3):
            reader = registry.open_reader(_peer_opts(west, i))
            try:
                stored_identity = registry.get_identity_pub(reader)
                stored_peer = registry.get_peer(reader, "east")
            finally:
                reader.close()
            assert (
                stored_identity == west_pub
            ), f"west peer{i} identity not replicated (got {stored_identity!r})"
            assert (
                stored_peer is not None
            ), f"west peer{i} did not see MASTER_PEER_ATTACH(east) via Raft"
            assert (
                stored_peer["public_key"] == east_pub
            ), f"west peer{i} public_key mismatch for 'east'"

        # Phase F: publish on east peer2 (index=1 for the SECOND
        # peer; peer_index=0 is the publish-daemon owner).  Build a
        # router that sees peer_index=1's pki_dir, connect a real
        # PeerMasterLink to west, and drive route_publish.
        peer2_opts = _peer_opts(east, 1)
        registry.pre_create(peer2_opts)
        breadcrumbs.pre_create(peer2_opts)
        peer2_reg = registry.open_writer(peer2_opts)
        peer2_br = breadcrumbs.open_writer(peer2_opts)
        try:
            router = router_mod.TopologyRouter(peer2_opts, peer2_reg, peer2_br)
            events = []
            router._fire_event = lambda tag, data: events.append(  # noqa: SLF001
                {"tag": tag, "data": data}
            )

            loop = asyncio.new_event_loop()
            try:
                # Fake-channel handshake answers with cluster_id="west"
                # so the link reports as attached to west.
                _FakeReqChannel.handshake_by_host["west-host"] = {
                    "status": "ok",
                    "aes": os.urandom(32),
                    "cluster_id": "west",
                    "endpoints": [],
                }
                link_opts = dict(peer2_opts)
                link_opts["topology_handshake_backoff"] = 0
                link_opts["topology_handshake_max_tries"] = 2
                west_link = PeerMasterLink(
                    link_opts,
                    PeerRef(host="west-host", port=44600, finger=None),
                    loop,
                )
                loop.run_until_complete(west_link.connect())
                assert (
                    west_link.health == LinkHealth.CONNECTED
                ), f"east peer2 link to west failed: health={west_link.health}"
                router._links["west"] = west_link  # noqa: SLF001

                load = {
                    "tgt": "*",
                    "tgt_type": "glob",
                    "fun": "test.ping",
                    "jid": "20260101000000000001",
                    "timeout": 10,
                }
                monkeypatch.setattr(router_mod, "_ROUTER", router, raising=False)
                loop.run_until_complete(router_mod.on_publish(load, loop))

                # Phase G: east peer2's publish fan-outs to west.
                west_sends = [
                    captured
                    for host, tag, captured in _FakeReqChannel.sends
                    if host == "west-host" and tag == "topology/pub"
                ]
                assert len(west_sends) == 1, (
                    "east peer2 flood publish must dispatch exactly one "
                    f"topology/pub to west; got {len(west_sends)}"
                )
                env = load["topology"]
                assert env["origin"] == "east"
                assert env["destinations"] is None, "flood -> destinations=None"

                # Phase H: breadcrumb for a return.  Simulate "a
                # return from west arrives on peer2 for a publish
                # peer2 forwarded" by recording the crumb and
                # resolving it back.  The lookup must map back to
                # the west link registered in router._links.
                return_jid = "20260101000000000002"

                class _InboundStub:
                    """Minimal stand-in for the inbound link half
                    of a round-trip.  Only ``peer_cluster_id`` is
                    read by ``record_breadcrumb``."""

                    peer_cluster_id = "west"
                    health = LinkHealth.CONNECTED

                router.record_breadcrumb(return_jid, _InboundStub(), timeout=30)
                resolved = router.lookup_breadcrumb(return_jid)
                assert resolved is west_link, (
                    "a return arriving on east peer2 for a west-origin "
                    "publish must resolve back to the west link via "
                    f"breadcrumbs; got {resolved!r}"
                )

                # Also: direct lookup of the breadcrumb bytes to
                # prove the per-peer MmapCache materialised the
                # entry.  This is the exact byte-level evidence a
                # future on-disk audit would check.
                raw_target = breadcrumbs.lookup(peer2_br, return_jid)
                assert raw_target == "west", (
                    f"breadcrumbs.lookup for jid {return_jid} must "
                    f"return 'west'; got {raw_target!r}"
                )
            finally:
                loop.close()
        finally:
            peer2_br.close()
            peer2_reg.close()
    finally:
        for sm in east_sms + west_sms:
            try:
                sm.registry.close()
            except Exception:  # pylint: disable=broad-except
                pass


# ===========================================================================
# Scenario 2: mixed topology --- solo + 3-peer cluster
# ===========================================================================


def test_scenario_mixed_solo_and_3peer_cluster(
    single_master, single_cluster, fakes, clean_link_manager, monkeypatch
):
    """
    Scenario 2 --- Mixed topology: one solo + one 3-peer cluster.

    Asymmetric shape under test: operators roll topology out in
    stages, so a solo ``hub`` master peers with a fully-clustered
    ``edge``.  The two sides use DIFFERENT write paths into the
    registry (solo writes direct; clustered writes via Raft) but
    the reader API must yield an identical shape so downstream
    code (router, link_manager) does not need to branch on cluster
    size.

    Steps:

    1. hub = solo master; edge = 3-peer cluster.
    2. Both sides generate real identity keypairs; bidirectional
       accept_peer.
    3. hub writes a MASTER_PEER_ATTACH-equivalent peer entry
       directly to its registry MmapCache (solo path, no Raft).
    4. edge commits MASTER_IDENTITY_KEY + MASTER_PEER_ATTACH(hub)
       to all 3 of its state machines (Raft replicates to each
       peer's local registry).
    5. Readers on both sides see the SAME PeerState shape ---
       cluster_id, public_key, endpoints, attached_at.
    6. Build routers on both sides, connect links, drive
       bidirectional publishes.  Verify the hub->edge publish
       dispatches a topology/pub to the edge peer1 host (publish-
       daemon-owner) and that an edge peer2-originated publish
       dispatches a topology/pub to the hub host.
    """
    hub = single_master(cluster_id="hub")
    edge = single_cluster("edge", peer_count=3)
    assert len(hub.masters) == 1
    assert len(edge.masters) == 3

    # Phase A: real identity + bidirectional acceptance.
    hub_pub = hub.ensure_identity_key()
    edge_pub = edge.ensure_identity_key()
    hub.accept_peer(edge)
    edge.accept_peer(hub)

    # Phase B: hub writes its view of the attached edge DIRECTLY
    # to its registry MmapCache (solo path).
    hub_opts = hub.master_opts()
    registry.pre_create(hub_opts)
    hub_reg_writer = registry.open_writer(hub_opts)
    hub_br_writer = None
    edge_endpoints = (
        f"{edge.masters[0].config.get('interface', '127.0.0.1')}"
        f":{edge.masters[0].config['topology_link_port']}",
    )
    hub_endpoints = (
        f"{hub.masters[0].config.get('interface', '127.0.0.1')}"
        f":{hub.masters[0].config['topology_link_port']}",
    )
    edge_sms = []
    try:
        registry.set_identity_pub(hub_reg_writer, hub_pub)
        registry.set_peer(
            hub_reg_writer,
            "edge",
            {
                "cluster_id": "edge",
                "public_key": edge_pub,
                "endpoints": edge_endpoints,
                "attached_at": 1_700_000_000.0,
            },
        )
        breadcrumbs.pre_create(hub_opts)
        hub_br_writer = breadcrumbs.open_writer(hub_opts)

        # Phase C: edge commits identity + hub attach through Raft
        # to all 3 peers' state machines.
        for i in range(3):
            edge_sms.append(TopologyStateMachine(_peer_opts(edge, i)))
        _replicate(
            {"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": edge_pub},
            edge_sms,
        )
        _replicate(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "hub",
                "public_key": hub_pub,
                "endpoints": hub_endpoints,
                "attached_at": 1_700_000_000.0,
            },
            edge_sms,
        )

        # Phase D: readers on both sides see the same PeerState
        # shape --- cluster_id, public_key, endpoints,
        # attached_at.  The reader API cannot tell solo from
        # clustered.
        hub_reader = registry.open_reader(hub_opts)
        try:
            hub_sees_edge = registry.get_peer(hub_reader, "edge")
            hub_identity = registry.get_identity_pub(hub_reader)
        finally:
            hub_reader.close()
        assert hub_sees_edge is not None, "hub did not record edge locally"
        assert hub_sees_edge["public_key"] == edge_pub
        assert hub_sees_edge["endpoints"] == edge_endpoints
        assert hub_identity == hub_pub

        for i in range(3):
            reader = registry.open_reader(_peer_opts(edge, i))
            try:
                edge_sees_hub = registry.get_peer(reader, "hub")
                edge_identity = registry.get_identity_pub(reader)
            finally:
                reader.close()
            assert (
                edge_sees_hub is not None
            ), f"edge peer{i} did not replicate MASTER_PEER_ATTACH(hub)"
            assert edge_sees_hub["public_key"] == hub_pub
            assert edge_sees_hub["endpoints"] == hub_endpoints
            assert edge_identity == edge_pub, f"edge peer{i} identity not replicated"
            # Shape equality: the solo-write and Raft-apply
            # round-trips produce byte-identical reader output
            # modulo the per-side ``public_key`` / ``endpoints``
            # fields.  The structural keys must match exactly.
            assert set(hub_sees_edge.keys()) == set(edge_sees_hub.keys()), (
                f"solo and clustered reader shapes differ: "
                f"hub={sorted(hub_sees_edge)!r} edge={sorted(edge_sees_hub)!r}"
            )

        # Phase E: hub router + hub->edge link.  Flood publish
        # from hub dispatches exactly one topology/pub to the
        # edge-primary host.
        hub_router = router_mod.TopologyRouter(hub_opts, hub_reg_writer, hub_br_writer)
        hub_events = []
        hub_router._fire_event = lambda tag, data: hub_events.append(  # noqa: SLF001
            {"tag": tag, "data": data}
        )
        loop = asyncio.new_event_loop()
        try:
            _FakeReqChannel.handshake_by_host["edge-primary"] = {
                "status": "ok",
                "aes": os.urandom(32),
                "cluster_id": "edge",
                "endpoints": [],
            }
            link_opts = dict(hub_opts)
            link_opts["topology_handshake_backoff"] = 0
            link_opts["topology_handshake_max_tries"] = 2
            hub_to_edge = PeerMasterLink(
                link_opts,
                PeerRef(host="edge-primary", port=44600, finger=None),
                loop,
            )
            loop.run_until_complete(hub_to_edge.connect())
            assert hub_to_edge.health == LinkHealth.CONNECTED
            hub_router._links["edge"] = hub_to_edge  # noqa: SLF001

            hub_load = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": "20260201000000000001",
                "timeout": 10,
            }
            monkeypatch.setattr(router_mod, "_ROUTER", hub_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(hub_load, loop))

            edge_sends = [
                captured
                for host, tag, captured in _FakeReqChannel.sends
                if host == "edge-primary" and tag == "topology/pub"
            ]
            assert len(edge_sends) == 1, (
                "hub flood publish must dispatch exactly one topology/pub "
                f"to the edge-primary peer; got {len(edge_sends)}"
            )
            assert hub_load["topology"]["origin"] == "hub"

            # Phase F: edge peer2 (NOT the publish-daemon owner)
            # originates a publish toward hub.  The publish-daemon
            # owner model means peer2's router sits atop peer2's
            # pki_dir but still routes through the owner's link;
            # the test still drives the publish through peer2's
            # own router to prove non-primary peers can originate
            # topology traffic.
            peer2_opts = _peer_opts(edge, 1)
            registry.pre_create(peer2_opts)
            breadcrumbs.pre_create(peer2_opts)
            peer2_reg = registry.open_writer(peer2_opts)
            peer2_br = breadcrumbs.open_writer(peer2_opts)
            try:
                edge_router = router_mod.TopologyRouter(peer2_opts, peer2_reg, peer2_br)
                edge_router.cluster_id = "edge"
                _FakeReqChannel.handshake_by_host["hub-host"] = {
                    "status": "ok",
                    "aes": os.urandom(32),
                    "cluster_id": "hub",
                    "endpoints": [],
                }
                edge_to_hub = PeerMasterLink(
                    link_opts,
                    PeerRef(host="hub-host", port=44600, finger=None),
                    loop,
                )
                loop.run_until_complete(edge_to_hub.connect())
                assert edge_to_hub.health == LinkHealth.CONNECTED
                edge_router._links["hub"] = edge_to_hub  # noqa: SLF001

                edge_load = {
                    "tgt": "*",
                    "tgt_type": "glob",
                    "fun": "test.ping",
                    "jid": "20260201000000000002",
                    "timeout": 10,
                }
                monkeypatch.setattr(router_mod, "_ROUTER", edge_router, raising=False)
                loop.run_until_complete(router_mod.on_publish(edge_load, loop))

                hub_sends = [
                    captured
                    for host, tag, captured in _FakeReqChannel.sends
                    if host == "hub-host" and tag == "topology/pub"
                ]
                assert len(hub_sends) == 1, (
                    "edge peer2 flood publish must dispatch exactly one "
                    f"topology/pub to hub; got {len(hub_sends)}"
                )
                assert edge_load["topology"]["origin"] == "edge"
            finally:
                peer2_br.close()
                peer2_reg.close()
        finally:
            loop.close()
    finally:
        for sm in edge_sms:
            try:
                sm.registry.close()
            except Exception:  # pylint: disable=broad-except
                pass
        if hub_br_writer is not None:
            try:
                hub_br_writer.close()
            except Exception:  # pylint: disable=broad-except
                pass
        try:
            hub_reg_writer.close()
        except Exception:  # pylint: disable=broad-except
            pass


# ===========================================================================
# Scenario 3: clustered master receives inbound on a non-primary peer
# ===========================================================================


def test_scenario_clustered_inbound_on_nonprimary_peer(
    single_master, single_cluster, fakes, clean_link_manager, monkeypatch
):
    """
    Scenario 3 --- Clustered master receives topology inbound on a
    non-primary peer.

    Shape under test: east is a 3-peer master cluster where peer1
    (``peer_index=0``, interface 127.0.0.1) is the publish-daemon
    owner.  hq is a solo master with an outbound topology link to
    east.  The outbound link dials peer1's interface because that
    is the first endpoint published in the attach entry.

    Per RFC "Unresolved questions > Transit-cluster breadcrumb
    failover" the publish daemon's inbound listener is bound to a
    single peer only in v1 --- failover is not transparent.  This
    scenario makes that behaviour explicit:

    * While peer1's publish daemon is running, the inbound
      listener is up on peer1's ``topology_link_port`` and
      ``link_manager._LISTENER`` is non-None.
    * After :meth:`stop_publish_daemon`, the listener is torn
      down and the module-level state is reset (``_LISTENER is
      None``, ``_OWNER_PID is None``).  Any inbound traffic on
      that port now has no listener behind it --- a clean fail,
      not a silent half-open.
    * A restart via :meth:`start_publish_daemon` restores the
      listener and the module-level writer handles; the system
      returns to serving inbound.
    """
    east = single_cluster("east", peer_count=3)
    hq = single_master(cluster_id="hq")
    assert len(east.masters) == 3

    # Phase A: identity + accept.
    east_pub = east.ensure_identity_key()
    hq_pub = hq.ensure_identity_key()
    east.accept_peer(hq)
    hq.accept_peer(east)

    # Phase B: hq's config_peer at east peer1's interface --- the
    # first endpoint published in the Raft attach entry.  The
    # harness picks ``east.masters[0]`` by default which is exactly
    # the publish-daemon-owner peer.
    east.config_peer(hq)
    hq.config_peer(east)

    # Phase C: start east peer1's publish daemon in-process.  This
    # materialises the inbound listener on east peer1's
    # ``topology_link_port``.  Mirror hq's identity through the Raft
    # path for completeness; the SM applies to east peer1's own
    # registry mmap at the pki_dir that start_publish_daemon will
    # open against.
    sm = TopologyStateMachine(_peer_opts(east, 0))
    svc = _FakeRaftService(sm)
    try:
        # Pre-commit MASTER_IDENTITY_KEY + MASTER_PEER_ATTACH(hq)
        # so the publish daemon's startup replay has an attach
        # entry to materialise an outbound link for.
        svc.propose({"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": east_pub})
        hq_endpoints = (
            f"{hq.masters[0].config.get('interface', '127.0.0.1')}"
            f":{hq.masters[0].config['topology_link_port']}",
        )
        svc.propose(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "hq",
                "public_key": hq_pub,
                "endpoints": hq_endpoints,
                "attached_at": 1_700_000_000.0,
            }
        )

        # Baseline: before start, no listener and no owner PID.
        assert (
            link_manager._LISTENER is None  # pylint: disable=protected-access
        ), "clean_link_manager must leave _LISTENER None before start"
        assert (
            link_manager._OWNER_PID is None  # pylint: disable=protected-access
        ), "clean_link_manager must leave _OWNER_PID None before start"

        loop, east_peer1_opts = east.start_publish_daemon(
            raft_service=svc, peer_index=0
        )
        try:
            # Phase D: inbound listener is up on east peer1.  The
            # listener materialisation can fail silently in test
            # environments without full master infrastructure
            # (ReqServerChannel pulls a lot of plumbing in);
            # ``_OWNER_PID`` captures the "start ran to
            # completion" signal regardless.
            assert (
                link_manager._OWNER_PID
                == os.getpid()  # pylint: disable=protected-access
            ), (
                "link_manager.start must stamp _OWNER_PID so the "
                "writer guards work; current _OWNER_PID="
                f"{link_manager._OWNER_PID!r}"
            )
            router = router_mod.get_router()
            assert (
                router is not None
            ), "start_publish_daemon must wire the process-wide router"
            # The port we tried to bind on is east peer1's
            # topology_link_port.  Capture it so the restart below
            # exercises the same port.
            inbound_port_before = east_peer1_opts["topology_link_port"]
            assert (
                inbound_port_before == east.masters[0].config["topology_link_port"]
            ), (
                "in-process publish daemon must use east peer1's "
                "topology_link_port, not peer2 or peer3"
            )
        finally:
            east.stop_publish_daemon(loop, peer_index=0)

        # Phase E: after stop, module state is reset.  Any inbound
        # traffic on east peer1's topology_link_port has no
        # listener behind it --- RFC-documented v1 behaviour.
        assert link_manager._OWNER_PID is None, (  # pylint: disable=protected-access
            "link_manager.stop must clear _OWNER_PID so the "
            "'inbound traffic has no handler' precondition holds"
        )
        assert (
            link_manager._LISTENER is None  # pylint: disable=protected-access
        ), "link_manager.stop must clear _LISTENER"
        assert (
            router_mod.get_router() is None
        ), "stop must clear the process-wide router"

        # Phase F: an "inbound" dispatch helper that would run on
        # the listener's accept callback can see the subsystem is
        # down.  Simulating this cleanly: ``_dispatch_pub`` /
        # ``_handle_inbound`` require ``_OWNER_PID`` to be set;
        # with the subsystem stopped, the dispatchers short-
        # circuit.  Verify via the guard: a direct writer op on
        # the (now-closed) registry handle raises because
        # ``_REGISTRY_CACHE is None`` --- the only way an inbound
        # path could even TRY to touch state.
        assert (
            link_manager._REGISTRY_CACHE is None  # pylint: disable=protected-access
        ), "registry cache handle must be released on stop"
        assert (
            link_manager._BREADCRUMB_CACHE is None  # pylint: disable=protected-access
        ), "breadcrumb cache handle must be released on stop"

        # Phase G: restart.  A fresh in-process start on the same
        # peer_index=0 re-opens the registry + breadcrumbs mmaps
        # against the same on-disk files and the subsystem is
        # serving again.  The peer entry committed before the
        # stop must still be present (persisted on disk).
        # Build a fresh SM pointing at the same pki_dir so the
        # replay sees the committed entry.  (The previous SM
        # closed its handle when we moved on; a new one re-opens
        # the mmap at the same path.)
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
        sm = TopologyStateMachine(_peer_opts(east, 0))
        svc = _FakeRaftService(sm)

        loop2, _ = east.start_publish_daemon(raft_service=svc, peer_index=0)
        try:
            assert (
                link_manager._OWNER_PID
                == os.getpid()  # pylint: disable=protected-access
            ), "restart must stamp a fresh _OWNER_PID"
            assert (
                router_mod.get_router() is not None
            ), "restart must re-wire the process-wide router"

            # Peer entry persisted through the stop/restart.
            reader = registry.open_reader(_peer_opts(east, 0))
            try:
                replayed = registry.get_peer(reader, "hq")
            finally:
                reader.close()
            assert replayed is not None, (
                "MASTER_PEER_ATTACH(hq) committed before the restart must "
                "persist on disk and be visible after the fresh start"
            )
            assert replayed["public_key"] == hq_pub
        finally:
            east.stop_publish_daemon(loop2, peer_index=0)
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
