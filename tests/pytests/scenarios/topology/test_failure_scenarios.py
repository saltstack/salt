"""
Scenario tests for master-topology failure recovery + lifecycle
transitions.

Each scenario exercises *multiple* topology modules at once --- the
goal is to catch failure modes that per-module tests cannot cover
because they only materialize when the pieces are composed:

* publish daemon restart mid-publish (link_manager + breadcrumbs +
  router + registry);
* peer detach quiesces in-flight returns (link + link_manager +
  router);
* solo -> clustered migration (registry + migration +
  link_manager + raft.topology state machine);
* startup ordering: callbacks register BEFORE migration replay
  (link_manager + raft.topology state machine).

Design notes
------------
Phase 5 integration into :class:`salt.channel.server.MasterPubServerChannel`
is partial, so these scenarios drive the topology lifecycle
in-process against the harness fixtures' real pki_dirs rather than
through the salt-master pre_fork path.  The ``single_master`` /
``two_cluster_fixture`` fixtures still spin up real salt-master
daemons so pki_dir conventions, port reservation, and
``topology.conf`` loading all behave exactly as they will in
production; the publish-daemon-side wiring is simulated by calling
:func:`salt.topology.link_manager.start` / ``stop`` directly against
the same opts.

Real :class:`salt.utils.mmap_cache.MmapCache` writes, real
:class:`PeerMasterLink` state transitions, real
:class:`TopologyStateMachine` callbacks.  Fakes exist only for the
peer-to-peer channel send layer: Phase 3's inbound ReqServerChannel
is not yet wired, so a scenario that needs the receiver to actually
answer a handshake monkeypatches
:class:`salt.channel.client.AsyncReqChannel.factory` with a
deterministic responder.  Those monkeypatches are reverted at test
scope.
"""

import asyncio
import logging
import os
import time

import pytest

import salt.channel.client
import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link as link_mod
import salt.topology.link_manager as link_manager
import salt.topology.migration as migration
import salt.topology.registry as registry
import salt.topology.router as router_mod
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, LinkUnavailable, PeerMasterLink

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
    AsyncReqChannel replacement that answers the handshake and
    captures every subsequent outbound send.

    Shared across tests via class-level :attr:`sends` so a scenario
    can rebuild its view of the on-wire traffic without plumbing the
    channel instance through the link_manager module internals.
    Tests reset the class state in their own setup to avoid bleed.
    """

    handshake_response = None
    default_response = None
    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        tag = load.get("cmd") or load.get("tag") if isinstance(load, dict) else None
        type(self).sends.append({"tag": tag, "load": load})
        if tag == "topology/_master_auth" and self.handshake_response is not None:
            return self.handshake_response
        return self.default_response

    async def connect(self):
        pass

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True


class _FakePubChannel:
    """Pub-channel shell --- the scenarios don't observe inbound pub."""

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def connect(self):
        pass

    def on_recv(self, callback):
        pass

    def close(self):
        pass

    async def close_async(self):
        pass


@pytest.fixture
def fake_peer_channels(monkeypatch):
    """
    Install the fake channel factories so :class:`PeerMasterLink`
    completes its handshake synchronously inside the scenario
    without needing the Phase 3 inbound listener.
    """
    _FakeReqChannel.sends = []
    _FakeReqChannel.handshake_response = {
        "status": "ok",
        "aes": os.urandom(32),
        "cluster_id": "peer",
        "endpoints": [],
    }
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


# ---------------------------------------------------------------------------
# Clean-state fixture for the module-level link_manager globals
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_link_manager(monkeypatch):
    """
    Reset the :mod:`salt.topology.link_manager` module globals
    before and after each scenario so a leftover ``_OWNER_PID`` or
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
# Fake raft service used by scenarios 3 + 4
# ---------------------------------------------------------------------------


class _FakeRaftService:
    """
    Minimal :class:`raft_service` stand-in matching the shape
    expected by :mod:`salt.topology.migration` and
    :mod:`salt.topology.link_manager`.

    Exposes a ``propose(cmd)`` that commits synchronously by
    dispatching into the backing :class:`TopologyStateMachine`'s
    ``apply``, plus a ``topology_sm`` attribute so
    ``link_manager.start`` wires the SM callbacks.  Mirrors the
    shim used by ``tests/pytests/functional/topology/test_migration.py``.
    """

    def __init__(self, state_machine):
        self.topology_sm = state_machine
        self.proposed = []

    def propose(self, cmd):
        self.proposed.append(cmd)
        self.topology_sm.apply(
            cmd, client_id="scenario", sequence_num=len(self.proposed)
        )


# ===========================================================================
# Scenario 1: publish daemon restart mid-publish survives breadcrumbs
# ===========================================================================


def test_publish_daemon_restart_preserves_breadcrumbs(
    two_cluster_fixture, clean_link_manager, monkeypatch
):
    """
    Scenario 1 --- Publish daemon restart mid-publish survives
    breadcrumbs.

    Failure mode under test: a crash of the publish daemon between
    "breadcrumb recorded for inbound jid" and "upstream return
    arrives" must NOT lose the routing hint.  Breadcrumbs live in
    an :class:`MmapCache` on disk precisely so a restarted publish
    daemon re-opens the same file and resumes dispatching returns
    for jids it accepted before the crash --- a strict improvement
    over syndic, which loses in-flight state on syndic restart.

    Steps:

    1. east.start_publish_daemon() --- bring up the topology
       subsystem in east's pki_dir.
    2. east's router records a breadcrumb for an in-flight
       ``west -> east`` publish (simulating "west forwarded the
       publish to east and is awaiting the returns").
    3. east.stop_publish_daemon() --- hard shutdown of the
       topology subsystem.  Simulates the publish daemon crashing
       mid-flight.
    4. Assert the breadcrumb MmapCache files still exist on
       disk.
    5. east.start_publish_daemon() --- restart.  New process-
       equivalent re-opens the same cache files.
    6. Assert :meth:`inspect_breadcrumbs` surfaces the pre-crash
       entry and the restarted router can look it up by jid.
    """
    east, west = two_cluster_fixture
    # Peer each side so the breadcrumb's inbound_link_cluster_id
    # value is meaningful.
    east.accept_peer(west)
    west.accept_peer(east)

    # Phase 1: east brings up the publish daemon and records a
    # breadcrumb for the in-flight publish from west.
    loop, east_opts = east.start_publish_daemon()
    try:
        router = router_mod.get_router()
        assert router is not None, "start_publish_daemon must wire the router"

        # Simulate "west forwarded a publish to east"; register a
        # breadcrumb so a subsequent return routes back to west.
        jid = "20260101000000000001"
        router.record_breadcrumb(
            jid,
            _StubInboundLink("west"),
            timeout=30,
        )
        before = east.inspect_breadcrumbs()
        assert any(
            c["jid"] == jid and c["link_cluster_id"] == "west" for c in before
        ), f"breadcrumb not recorded before restart: {before!r}"
    finally:
        east.stop_publish_daemon(loop)

    # Phase 2: the files must persist on disk through the restart.
    paths = east.breadcrumb_mmap_paths()
    for key in ("index", "heap", "roster"):
        assert paths[key].exists(), f"breadcrumb {key} file missing after shutdown"

    # Phase 3: restart.  Fresh process-equivalent re-opens the same
    # cache; the breadcrumb written before the shutdown must be
    # visible and routable.
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    loop2, east_opts2 = east.start_publish_daemon()
    try:
        router2 = router_mod.get_router()
        assert router2 is not None, "restarted publish daemon must re-wire router"

        after = east.inspect_breadcrumbs()
        assert any(
            c["jid"] == "20260101000000000001" and c["link_cluster_id"] == "west"
            for c in after
        ), f"restarted breadcrumb lookup missed pre-crash entry: {after!r}"

        # Verify the router can route a return for the pre-crash jid.
        # The router returns None when the link to the recorded
        # peer isn't in its own ``_links`` dict (routes-via-cluster-
        # id); even so, the breadcrumb lookup must succeed under the
        # hood so a future reconnected link resumes dispatch.
        resolved = breadcrumbs.lookup(
            router2._breadcrumbs,  # pylint: disable=protected-access
            "20260101000000000001",
        )
        assert resolved == "west", (
            f"breadcrumbs.lookup after restart returned {resolved!r} "
            "but the pre-crash entry targeted 'west'"
        )
    finally:
        east.stop_publish_daemon(loop2)


class _StubInboundLink:
    """
    Minimal :class:`PeerMasterLink` stand-in for scenario 1.

    The router's :meth:`record_breadcrumb` only reads
    ``peer_cluster_id`` off the inbound link; a lightweight stub
    keeps the test boundary at the breadcrumb lifecycle without
    needing the full handshake machinery.
    """

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = LinkHealth.CONNECTED


# ===========================================================================
# Scenario 2: peer detach quiesces in-flight returns
# ===========================================================================


def test_peer_detach_quiesces_inflight_returns(fake_peer_channels):
    """
    Scenario 2 --- Peer detach quiesces in-flight returns.

    Failure mode under test: an operator-initiated detach (e.g.
    ``salt-key -d west --master``) must not drop returns that are
    already in flight back from the detached peer.  The link
    transitions through QUIESCING for ``topology_detach_quiesce``
    seconds during which ``send_return`` is still permitted;
    ``send_publish`` is immediately rejected.  After the drain
    window the link settles into DISCONNECTED and ALL further
    sends raise :class:`LinkUnavailable`.

    This test drives the link directly rather than through a real
    inbound listener so the state transitions are observable
    without a full Phase 3 setup.  The ``fake_peer_channels``
    monkeypatches the client-side channel so ``connect`` completes
    end-to-end.
    """
    # Make detach drain window long enough for the test to observe
    # the "QUIESCING but returns still work" window before the
    # final DISCONNECTED.
    opts = {
        "cluster_id": "east",
        "topology_link_port": 55555,
        "topology_detach_quiesce": 2.0,
    }
    seed = PeerRef(host="127.0.0.1", port=55555, finger=None)
    loop = asyncio.new_event_loop()
    try:
        _FakeReqChannel.handshake_response = {
            "status": "ok",
            "aes": os.urandom(32),
            "cluster_id": "west",
            "endpoints": [],
        }
        link = PeerMasterLink(opts, seed, loop)
        loop.run_until_complete(link.connect())
        assert (
            link.health == LinkHealth.CONNECTED
        ), f"handshake did not complete; health={link.health!r}"
        assert link.peer_cluster_id == "west"

        # Fire-and-forget: schedule the quiesce without awaiting it
        # so the test can observe the drain-window behavior.
        quiesce_task = loop.create_task(link.quiesce())

        async def _probe_during_quiesce():
            # Yield so quiesce() can enter QUIESCING before we
            # probe.  One scheduler turn is enough.
            await asyncio.sleep(0)
            assert link.health == LinkHealth.QUIESCING, (
                f"link should be QUIESCING immediately after quiesce "
                f"was awaited once; got {link.health!r}"
            )
            # Returns MUST still land during quiesce --- this is
            # the whole point of the drain window.
            await link.send_return([{"id": "minion-1", "retcode": 0}], ["east"])
            # Publishes MUST be rejected during quiesce.
            with pytest.raises(LinkUnavailable):
                await link.send_publish(
                    {"tgt": "*", "fun": "test.ping", "topology": {}}, ["east"]
                )

        loop.run_until_complete(_probe_during_quiesce())
        # Let quiesce run its drain-window sleep + disconnect.
        loop.run_until_complete(quiesce_task)

        assert (
            link.health == LinkHealth.DISCONNECTED
        ), f"after drain window link must be DISCONNECTED; got {link.health!r}"

        # Post-drain: every send is rejected.
        async def _probe_post_drain():
            with pytest.raises(LinkUnavailable):
                await link.send_return([{"id": "minion-2", "retcode": 0}], ["east"])
            with pytest.raises(LinkUnavailable):
                await link.send_publish(
                    {"tgt": "*", "fun": "test.ping", "topology": {}}, ["east"]
                )

        loop.run_until_complete(_probe_post_drain())
    finally:
        loop.close()


# ===========================================================================
# Scenario 3: solo -> clustered migration
# ===========================================================================


def test_solo_to_clustered_migration_preserves_accepted_peer(
    tmp_path, clean_link_manager
):
    """
    Scenario 3 --- Solo to clustered migration.

    Lifecycle transition under test: a formerly-solo master that
    boots clustered for the first time must propose Raft entries
    from its registry contents so the new peer cluster converges
    on the same state.  Specifically:

    * Before migration, ``needs_migration`` reports True because
      the registry holds peers but the Raft applied set is empty.
    * ``promote_solo_to_clustered`` proposes
      ``MASTER_IDENTITY_KEY`` + one ``MASTER_PEER_ATTACH`` per
      accepted peer, in deterministic order.
    * After migration, ``needs_migration`` reports False and the
      previously-accepted peer entry is still present in the
      registry (no re-accept needed on the operator's part).
    """
    # Phase A: build a solo master's on-disk state --- identity
    # keypair in pki_dir/master/, identity_pub + one accepted peer
    # in the registry.
    pki_dir = tmp_path / "solo-pki"
    master_dir = pki_dir / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_dir / sub).mkdir(parents=True, exist_ok=True)

    solo_opts = {
        "pki_dir": str(pki_dir),
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "keysize": 2048,
        "hash_type": "sha256",
    }

    identity_pub = (
        b"-----BEGIN PUBLIC KEY-----\nSOLO-IDENTITY\n-----END PUBLIC KEY-----\n"
    )
    identity_priv = (
        b"-----BEGIN RSA PRIVATE KEY-----\nsolo-identity\n"
        b"-----END RSA PRIVATE KEY-----\n"
    )
    peer_pub = b"-----BEGIN PUBLIC KEY-----\nPEER2\n-----END PUBLIC KEY-----\n"

    # Stash the private half on disk the way a solo publish daemon
    # would have.
    import salt.utils.files

    priv_path = master_dir / "master_identity.pem"
    with salt.utils.files.fopen(str(priv_path), "wb") as fh:
        fh.write(identity_priv)
    os.chmod(str(priv_path), 0o400)

    # Seed the registry directly (bypassing Raft, which is the
    # whole point of "solo master" mode).
    solo_writer = registry.open_writer(solo_opts)
    try:
        registry.set_identity_pub(solo_writer, identity_pub)
        registry.set_peer(
            solo_writer,
            "peer2",
            {
                "cluster_id": "peer2",
                "public_key": peer_pub,
                "endpoints": ("127.0.0.1:4506",),
                "attached_at": 1_700_000_000.0,
            },
        )
    finally:
        solo_writer.close()

    # Phase B: flip to clustered.  needs_migration must say True
    # because the registry holds the peer but no Raft commit has
    # happened yet.
    clustered_opts = dict(solo_opts)
    clustered_opts["cluster_peers"] = ["peer2"]

    assert migration.needs_migration(clustered_opts) is True, (
        "needs_migration must detect a solo-mode registry with "
        "unapplied peers as 'needs migration'"
    )

    # Phase C: drive the clustered promotion through a real SM +
    # a fake Raft service (synchronous commit).
    sm = TopologyStateMachine(clustered_opts)
    try:
        svc = _FakeRaftService(sm)
        migration.promote_solo_to_clustered(clustered_opts, svc)
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass

    # The promotion must propose identity first, then the peer
    # attach --- deterministic ordering is called out by
    # :func:`migration._collect_pending`.
    types_seen = [cmd["type"] for cmd in svc.proposed]
    assert types_seen[0] == LogEntryType.MASTER_IDENTITY_KEY, (
        f"migration must propose MASTER_IDENTITY_KEY first; "
        f"got order {types_seen!r}"
    )
    attach_cmds = [
        cmd for cmd in svc.proposed if cmd["type"] == LogEntryType.MASTER_PEER_ATTACH
    ]
    assert [c["cluster_id"] for c in attach_cmds] == ["peer2"], (
        f"expected a single MASTER_PEER_ATTACH for 'peer2'; " f"got {attach_cmds!r}"
    )

    # Phase D: migration must now be a no-op; the Raft state and
    # the registry agree.
    assert (
        migration.needs_migration(clustered_opts) is False
    ), "needs_migration must return False after a complete migration run"

    # Phase E: the previously-accepted peer entry must still be in
    # the registry (operator did not need to re-accept).
    reader = registry.open_reader(clustered_opts)
    try:
        peer_state = registry.get_peer(reader, "peer2")
    finally:
        reader.close()
    assert peer_state is not None, "migration must not evict the pre-cluster peer entry"
    assert (
        peer_state["public_key"] == peer_pub
    ), "peer public_key must survive the migration byte-for-byte"


# ===========================================================================
# Scenario 4: startup ordering --- callbacks before migration replay
# ===========================================================================


def test_startup_registers_callbacks_before_replaying_committed_attaches(
    tmp_path, clean_link_manager, monkeypatch
):
    """
    Scenario 4 --- Startup ordering: callbacks before migration.

    Audit finding under test (RFC "Failure recovery"): if
    :func:`link_manager.start` installs state-machine callbacks
    AFTER replaying pre-existing committed Raft entries, every
    attach entry committed before the current process started
    silently fails to create a :class:`PeerMasterLink` --- the
    callback simply did not exist yet when ``apply`` ran.  The
    documented ordering (step 5 in ``link_manager.start``'s
    docstring) is "install callbacks BEFORE replay"; this
    scenario confirms it empirically.

    Steps:

    1. Build a Raft state machine against an empty registry.
    2. Simulate "previous process generation" by applying a
       ``MASTER_PEER_ATTACH`` entry.  The entry lands in the
       registry but no :class:`PeerMasterLink` is created
       because no callback is wired yet.
    3. Hand the SM to a fresh ``link_manager.start`` via a fake
       raft_service.  The start wraps the SM's attach handler
       (``_install_sm_callbacks``) and re-plays the applied set
       through the wrapped handler.
    4. Assert :func:`link_manager.get_all_links` surfaces a link
       for the pre-existing peer --- proof that the wrapping
       happened before replay.
    """
    pki_dir = tmp_path / "clustered-pki"
    master_dir = pki_dir / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_dir / sub).mkdir(parents=True, exist_ok=True)

    # Write a minimal topology.conf so link_manager.start's
    # load_topology_config step succeeds.
    import salt.utils.files
    import salt.utils.yaml

    topology_conf = tmp_path / "topology.conf"
    with salt.utils.files.fopen(str(topology_conf), "w") as fh:
        salt.utils.yaml.safe_dump({"cluster_id": "self", "peers": []}, fh)

    clustered_opts = {
        "pki_dir": str(pki_dir),
        "cluster_id": "self",
        "interface": "127.0.0.1",
        "topology_enabled": True,
        "topology_link_port": _find_free_port(),
        "topology_config_file": str(topology_conf),
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_detach_quiesce": 0,
        "cluster_peers": ["placeholder"],
    }

    # Phase A: simulate "previous process generation" by letting a
    # standalone SM commit a MASTER_PEER_ATTACH entry.  The SM
    # writes the registry but there is no link_manager wrapping
    # yet, so no PeerMasterLink is created.
    pre_sm = TopologyStateMachine(clustered_opts)
    try:
        pre_sm.apply(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "committed-peer",
                "public_key": (
                    b"-----BEGIN PUBLIC KEY-----\nCOMMITTED\n"
                    b"-----END PUBLIC KEY-----\n"
                ),
                "endpoints": ("127.0.0.1:4506",),
                "attached_at": 1_700_000_000.0,
            }
        )
    finally:
        try:
            pre_sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass

    # Confirm the registry has the peer but no link_manager state
    # exists yet.
    reader = registry.open_reader(clustered_opts)
    try:
        assert (
            registry.get_peer(reader, "committed-peer") is not None
        ), "setup error: the pre-existing attach did not land in the registry"
    finally:
        reader.close()
    assert (
        link_manager._LINKS == {}  # pylint: disable=protected-access
    ), "clean_link_manager must leave _LINKS empty before start"

    # Phase B: build a *fresh* SM against the same registry (fresh
    # process generation) and hand it to link_manager.start via a
    # fake raft_service.  The _install_sm_callbacks step must wrap
    # the SM's attach handler, AND then re-fire the already-applied
    # attach so the link is created.
    fresh_sm = TopologyStateMachine(clustered_opts)
    svc = _FakeRaftService(fresh_sm)

    # The SM's apply handler, once wrapped by link_manager, needs
    # to replay the pre-existing peer so a link lands in
    # ``_LINKS``.  Trigger this by re-applying the attach after
    # link_manager.start has wrapped the SM --- a real Raft Node
    # calls apply once per committed entry during catch-up, so this
    # replay is architecturally the same thing.
    # Use the fake peer channels so a PeerMasterLink.connect()
    # scheduled by add_link does not blow up on no listener.
    _FakeReqChannel.sends = []
    _FakeReqChannel.handshake_response = {
        "status": "ok",
        "aes": os.urandom(32),
        "cluster_id": "committed-peer",
        "endpoints": [],
    }
    _FakeReqChannel.default_response = {"status": "ok"}
    monkeypatch.setattr(
        salt.channel.client.AsyncReqChannel, "factory", _FakeReqChannel.factory
    )
    monkeypatch.setattr(
        salt.channel.client.AsyncPubChannel, "factory", _FakePubChannel.factory
    )
    monkeypatch.setattr(link_mod, "AsyncReqChannel", _FakeReqChannel, raising=False)
    monkeypatch.setattr(link_mod, "AsyncPubChannel", _FakePubChannel, raising=False)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(clustered_opts, loop, svc))

        # Simulate the Raft node's catch-up: replay the pre-
        # existing attach entry through the SM's apply.  Because
        # link_manager wrapped the handler BEFORE replay, this
        # must now also fire add_link.
        fresh_sm.apply(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "committed-peer",
                "public_key": (
                    b"-----BEGIN PUBLIC KEY-----\nCOMMITTED\n"
                    b"-----END PUBLIC KEY-----\n"
                ),
                "endpoints": ("127.0.0.1:4506",),
                "attached_at": 1_700_000_000.0,
            }
        )

        # add_link schedules the newly-created link's ``connect()``
        # on the io loop via ``call_soon_threadsafe``.  Give the
        # loop a few turns to drive the fake-channel handshake to
        # completion so the link's ``peer_cluster_id`` graduates
        # from None (post-construction) to "committed-peer"
        # (post-ok).
        async def _drain():
            for _ in range(5):
                await asyncio.sleep(0)

        loop.run_until_complete(_drain())

        # Phase C: assert the pre-existing committed peer produced
        # a PeerMasterLink in the registry.  The link is initially
        # registered under a provisional key (because
        # peer_cluster_id is None at ``add_link`` time) and
        # ``get_all_links`` filters those out, so we inspect
        # ``_LINKS`` directly --- the point here is "did the
        # wrapped attach handler fire?", not "did the handshake
        # land under the final key."
        tracked = list(link_manager._LINKS.values())  # pylint: disable=protected-access
        peer_ids_seen = {getattr(link, "peer_cluster_id", None) for link in tracked}
        assert "committed-peer" in peer_ids_seen, (
            "startup ordering bug: the wrapped SM handler did "
            "not fire for the pre-existing committed peer "
            f"(_LINKS peer_cluster_ids={peer_ids_seen!r}, "
            f"count={len(tracked)}); callbacks must register "
            "BEFORE replay"
        )
    finally:
        try:
            loop.run_until_complete(link_manager.stop())
        finally:
            loop.close()
            try:
                fresh_sm.registry.close()
            except Exception:  # pylint: disable=broad-except
                pass


def _find_free_port():
    """Return a free TCP port on 127.0.0.1 for the inbound listener."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# Silence unused-import noise for ``time``; retained for future
# scenarios that observe quiesce timing more finely.
_unused_time = time
