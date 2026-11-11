"""
End-to-end scenario tests for the master-topology feature.

Each scenario is a complete operator-workflow trace through the
topology stack: real masters spun up by the harness fixtures,
real :mod:`salt.topology.registry` and :mod:`salt.topology.breadcrumbs`
MmapCaches on disk, a real :class:`salt.topology.router.TopologyRouter`
driving a real :class:`salt.topology.link.PeerMasterLink`.

The link's transport (``AsyncReqChannel`` / ``AsyncPubChannel``)
is faked --- the full :class:`salt.channel.server.ReqServerChannel`
inbound listener is not yet exercised through the harness because
the harness's placeholder identity-pub key would not pass the real
``topology/_master_auth`` handshake.  Capturing the on-the-wire
``topology/pub``, ``topology/ret``, and ``topology/evt`` envelopes
at the fake channel still exercises every topology module beyond
the single-process transport boundary: :mod:`salt.topology.router`
decides what to send, :mod:`salt.topology.link` builds and
authenticates the envelope, :mod:`salt.topology.breadcrumbs`
records return paths, :mod:`salt.topology.registry` carries
accepted-peer state read by :func:`salt.topology.migration` on
startup, and :func:`salt.utils.job.store_job` applies the
``cluster_path`` disambiguation on the receiving-origin side.

Scenarios covered:

* ``test_scenario_scoped_publish_via_c_token`` --- bidirectional
  east/west peering; ``salt -C 'C@east and web-*' test.ping``
  from east fans out to east-local only; west sees nothing;
  return lands in east's job cache keyed by
  ``cluster_path=("east",)``.
* ``test_scenario_flood_publish_three_cluster_transit`` ---
  east<->west<->south line (no east<->south direct);
  ``salt '*' test.ping`` from east floods; south returns transit
  via west; loop detection drops the reflected
  south->west->east->... publish.
* ``test_scenario_directional_trust_east_accepts_west_not_vice_versa``
  --- east accepts west, west does not accept east; west->east
  publishes succeed, east->west handshakes park in
  PENDING_ACCEPT and fire ``salt/topology/pub/failed/west``.
* ``test_scenario_duplicate_minion_id_disambiguated_by_cluster_path``
  --- east and west both have a minion named ``web-01``;
  flooded ``salt 'web-01' test.ping`` from east stores both
  returns distinguishably in east's job cache by
  ``cluster_path`` suffix on the on-disk key.
"""

import asyncio
import os

import pytest

import salt.channel.client
import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link as link_mod
import salt.topology.registry as registry
import salt.topology.router as router_mod
import salt.utils.jid
import salt.utils.job
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fake channel scaffolding
# ---------------------------------------------------------------------------


class _CapturedSend:
    """One captured outbound send."""

    def __init__(self, load, tries, timeout):
        self.load = load
        self.tries = tries
        self.timeout = timeout


class _FakeReqChannel:
    """
    AsyncReqChannel stand-in used by :class:`PeerMasterLink`.

    Per-cluster scenarios index the per-link captures by the
    peer_cluster_id reported in the handshake response; see
    :func:`_install_fakes`.
    """

    #: Dict configured per-peer-host before each test:
    #: ``{host: {"status": "ok"|"retry"|..., "aes": ..., "cluster_id": peer, ...}}``.
    #: Keyed by the host the link is dialing so each outbound link gets
    #: the right handshake response.
    handshake_by_host = {}  # noqa: RUF012

    #: Default response for non-handshake sends.
    default_response = {"status": "ok"}  # noqa: RUF012

    #: Captured sends across all instances for the current test.
    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        # Which host does this instance target?  Needed to pick the
        # right handshake response and to tag each captured send.
        self._host = opts.get("master_ip") or opts.get("master_host") or ""
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        tag = None
        if isinstance(load, dict):
            tag = load.get("cmd") or load.get("tag")
        type(self).sends.append((self._host, tag, _CapturedSend(load, tries, timeout)))
        if tag in ("topology/_master_auth", "_master_auth"):
            # Default: ok with a stand-in cluster_id derived from host.
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
    """Install fake channel factories; reset per-test capture buffers."""
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
def topology_minion_opts(tmp_path):
    """
    Full-shape master opts dict pointing at a per-test cachedir.

    Scenarios drive :func:`salt.utils.job.store_job` directly against
    the ``local_cache`` returner, which needs a full master opts
    shape to load the ``MasterMinion`` returner module.  The
    functional-tests ``minion_opts`` fixture is scoped to
    ``tests/pytests/functional`` and isn't visible here; this
    replacement keeps the scenarios self-contained.
    """
    import salt.config

    cachedir = tmp_path / "minion-cache"
    cachedir.mkdir(parents=True, exist_ok=True)
    (cachedir / "jobs").mkdir(exist_ok=True)
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(cachedir)
    opts["extension_modules"] = str(tmp_path / "extmods")
    opts["file_client"] = "local"
    opts["id"] = "scenarios-topology-minion"
    return opts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opts_from_cluster(cluster):
    """
    Return a minimal opts dict pointing at the running master's
    on-disk pki_dir, so the registry/breadcrumb MmapCaches we open
    in the test share bytes with the master process when (and if)
    it eventually populates them.

    Cache sizes must mirror the master's own pre_create or the
    test-opened writer sees an "Index file size mismatch" --- the
    master's pre_fork path already materialised the mmap at the
    opt-specified size.  See the matching note in
    :meth:`TopologyCluster.master_opts`.
    """
    master = cluster.masters[0]
    return {
        "pki_dir": master.config["pki_dir"],
        "cluster_id": cluster.cluster_id,
        "interface": master.config.get("interface", "127.0.0.1"),
        "topology_enabled": True,
        "topology_link_port": master.config["topology_link_port"],
        "topology_peers": list(master.config.get("topology_peers") or []),
        "topology_event_subscriptions": master.config.get(
            "topology_event_subscriptions"
        ),
        "topology_breadcrumb_grace": master.config.get("topology_breadcrumb_grace", 2),
        "topology_breadcrumb_max_age": master.config.get(
            "topology_breadcrumb_max_age", 60
        ),
        "topology_breadcrumb_cache_size": master.config.get(
            "topology_breadcrumb_cache_size", 1_000_000
        ),
        "topology_breadcrumb_cache_key_size": master.config.get(
            "topology_breadcrumb_cache_key_size", 64
        ),
        "topology_registry_cache_size": master.config.get(
            "topology_registry_cache_size", 10_000
        ),
        "topology_registry_cache_key_size": master.config.get(
            "topology_registry_cache_key_size", 64
        ),
    }


def _make_router(cluster):
    """
    Build a real :class:`TopologyRouter` on top of the running
    master's on-disk MmapCaches.

    Returns ``(router, opts, registry_cache, breadcrumbs_cache,
    events)``.  ``events`` is a list that captures every
    operator-visible event the router fires.
    """
    opts = _opts_from_cluster(cluster)
    # pre_create is idempotent --- the mmap files may or may not
    # already exist depending on whether the master process has
    # touched them.
    registry.pre_create(opts)
    breadcrumbs.pre_create(opts)
    reg = registry.open_writer(opts)
    br = breadcrumbs.open_writer(opts)
    r = router_mod.TopologyRouter(opts, reg, br)
    events = []
    r._fire_event = lambda tag, data: events.append(  # noqa: SLF001
        {"tag": tag, "data": data}
    )
    return r, opts, reg, br, events


def _connect_link(router_a, host_target, peer_cluster_id, loop, aes=None):
    """
    Build a real :class:`PeerMasterLink` on ``router_a`` whose
    seed endpoint targets *host_target* (the host used as the
    index into :attr:`_FakeReqChannel.handshake_by_host`), and
    whose fake handshake returns *peer_cluster_id*.  Register
    under ``peer_cluster_id`` so routing by destination works.
    """
    link_opts = dict(router_a.opts)
    link_opts["topology_handshake_backoff"] = 0
    link_opts["topology_handshake_max_tries"] = 2
    _FakeReqChannel.handshake_by_host[host_target] = {
        "status": "ok",
        "aes": aes if aes is not None else os.urandom(32),
        "cluster_id": peer_cluster_id,
        "endpoints": [],
    }
    link = PeerMasterLink(
        link_opts, PeerRef(host=host_target, port=44600, finger=None), loop
    )
    loop.run_until_complete(link.connect())
    assert (
        link.health == LinkHealth.CONNECTED
    ), f"link to {peer_cluster_id!r} failed to connect: health={link.health}"
    router_a._links[peer_cluster_id] = link  # noqa: SLF001
    return link


def _topology_pub_sends_to(host):
    """Return captured ``topology/pub`` sends dialed at *host*."""
    return [
        captured
        for sent_host, tag, captured in _FakeReqChannel.sends
        if tag == "topology/pub" and sent_host == host
    ]


def _topology_pub_sends_all():
    """Return every captured ``topology/pub`` send regardless of host."""
    return [
        (sent_host, captured)
        for sent_host, tag, captured in _FakeReqChannel.sends
        if tag == "topology/pub"
    ]


def _make_minion_load(minion_id, jid, fun="test.ping", payload=True):
    """Shape of a minion return load as consumed by store_job."""
    return {
        "id": minion_id,
        "tgt": minion_id,
        "jid": jid,
        "return": {
            "fun": fun,
            "jid": jid,
            "fun_args": [],
            "return": payload,
            "success": True,
        },
    }


def _job_cache_opts(minion_opts):
    """Prime a minion opts dict so local_cache is the master job cache."""
    opts = minion_opts.copy()
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["ext_job_cache"] = ""
    return opts


# ---------------------------------------------------------------------------
# Scenario 1 --- Scoped publish via C@
# ---------------------------------------------------------------------------


def test_scenario_scoped_publish_via_c_token(
    two_cluster_fixture, attach_minion, topology_minion_opts, fakes, monkeypatch
):
    """
    Scoped publish: ``salt -C 'C@east and web-*' test.ping`` from east.

    Workflow exercised:

    1. Harness brings up two real masters (east, west) with
       ``topology_enabled: True``.
    2. Both sides accept each other's identity (``accept_peer``)
       and both ``config_peer`` so the topology.conf lists the
       other side --- real :mod:`salt.topology.registry`
       materialises the accepted-peer entries on disk.
    3. The test instantiates real
       :class:`salt.topology.router.TopologyRouter` instances per
       cluster against those real MmapCaches.
    4. East's router gets a real :class:`PeerMasterLink` to west
       installed in ``_links``.
    5. :func:`salt.topology.router.on_publish` runs on the
       operator's ``C@east and web-*`` publish load.
    6. Assertions: east's web-* minion gets the publish locally
       (``route_publish`` reports ``local_match=True``), the
       outbound fake-channel sees NO ``topology/pub`` send to
       west (scoping worked), AND an east-side return stored via
       :func:`salt.utils.job.store_job` with
       ``cluster_path=("east",)`` lands at the expected on-disk
       key.
    """
    east, west = two_cluster_fixture
    # Bidirectional key acceptance.
    east.accept_peer(west)
    west.accept_peer(east)
    # Bidirectional config-level peering.
    east.config_peer(west)
    west.config_peer(east)

    # Harness-level sanity: registries show the peer.
    east_reg = east.inspect_registry()
    west_reg = west.inspect_registry()
    assert west.cluster_id in east_reg["peers"], east_reg
    assert east.cluster_id in west_reg["peers"], west_reg

    # Attach a real minion to east (web-01).  This proves the
    # fixture + minion lifecycle plays nicely with topology-enabled
    # masters even before the router is wired.
    minion = attach_minion(east, minion_id="web-01")
    assert minion.is_running()

    # Build real routers + a real link east -> west.
    east_router, _east_opts, east_reg_cache, east_br_cache, east_events = _make_router(
        east
    )
    west_router, _west_opts, west_reg_cache, west_br_cache, _west_events = _make_router(
        west
    )
    try:
        loop = asyncio.new_event_loop()
        try:
            # Point east's link at a stable fake host string; the
            # fake-channel keys handshake responses by host.
            _connect_link(east_router, "west-host", "west", loop)

            # The operator's publish load (as the publish daemon sees it).
            jid = salt.utils.jid.gen_jid(_opts_from_cluster(east))
            load = {
                "tgt": "C@east and web-*",
                "tgt_type": "compound",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 5,
            }

            # Expose east_router as the module-level router for on_publish.
            monkeypatch.setattr(router_mod, "_ROUTER", east_router, raising=False)

            # Drive the publish-side router entry point --- the exact
            # function :class:`MasterPubServerChannel.publish_payload`
            # calls.
            loop.run_until_complete(router_mod.on_publish(load, loop))

            # Scoping: destinations must be {"east"} only.  East is the
            # origin and the only scoped destination; no outbound
            # topology/pub to west should have been emitted.
            west_sends = _topology_pub_sends_to("west-host")
            assert not west_sends, (
                f"C@east should NOT cross to west; got {len(west_sends)} sends: "
                f"{west_sends}"
            )

            # route_publish independently should report local_match for
            # east (origin), empty link list, dest=["east"].
            links, local_match = east_router.route_publish(dict(load))
            assert local_match is True
            assert links == []
            env = load["topology"]
            assert env["origin"] == "east"
            assert env["destinations"] == ["east"]

            # No topology/pub-failed events were fired (links=[]).
            failed = [e for e in east_events if "pub/failed" in e["tag"]]
            assert failed == [], failed

            # Return path: east-origin publish, east-local minion ->
            # store_job with cluster_path=("east",) hits the
            # cluster-path-qualified on-disk key, proving the end-to-end
            # (jid, cluster_path, id) coordinate the RFC specifies.
            opts = _job_cache_opts(topology_minion_opts)
            ret_load = _make_minion_load("web-01", jid)
            salt.utils.job.store_job(opts, ret_load, cluster_path=("east",))

            import pathlib

            jobs_root = pathlib.Path(opts["cachedir"], "jobs")
            jid_dir = pathlib.Path(
                salt.utils.jid.jid_dir(jid, str(jobs_root), opts["hash_type"])
            )
            assert (
                jid_dir / "east" / "web-01" / "return.p"
            ).is_file(), (
                "store_job(cluster_path=('east',)) must land under east/web-01/"
            )
            # Legacy unqualified minion dir must NOT exist (no clobber).
            assert not (jid_dir / "web-01" / "return.p").is_file()
        finally:
            loop.close()
    finally:
        east_br_cache.close()
        east_reg_cache.close()
        west_br_cache.close()
        west_reg_cache.close()


# ---------------------------------------------------------------------------
# Scenario 2 --- Flood publish, three-cluster line, transit returns
# ---------------------------------------------------------------------------


def test_scenario_flood_publish_three_cluster_transit(
    single_master, fakes, monkeypatch
):
    """
    Flood publish via a three-cluster line: east<->west<->south.

    East has a direct link to west; south has a direct link to
    west only.  East has NO direct link to south.  The operator
    runs flood ``salt '*' test.ping`` on east.

    Verifications:

    * East's :meth:`TopologyRouter.route_publish` returns ONE
      outbound link (to west; south not reachable directly).
    * West, acting as transit, receives the publish via
      :meth:`TopologyRouter.forward_publish`; the receiver
      appends its own authenticated ``cluster_id`` to
      ``path`` and forwards onward to south (not back to east
      --- inbound link is excluded).
    * The breadcrumb for the forwarded jid lands in west's real
      breadcrumbs MmapCache; :func:`route_return` on west
      resolves it back to the east-pointing link.
    * Loop detection: a reflected publish arriving at east from
      west with ``path=["east", "west"]`` is dropped (origin
      sees itself in path).
    """
    # Named clusters so route_publish envelope.origin reflects
    # the operator-facing cluster_id instead of the harness's
    # three_cluster_fixture a/b/c defaults.
    east = single_master(cluster_id="east")
    west = single_master(cluster_id="west")
    south = single_master(cluster_id="south")
    # Chain acceptance + config: east<->west, west<->south.
    east.accept_peer(west)
    west.accept_peer(east)
    east.config_peer(west)
    west.config_peer(east)

    west.accept_peer(south)
    south.accept_peer(west)
    west.config_peer(south)
    south.config_peer(west)
    # NO east<->south direct peering --- the test depends on it.

    east_router, _, east_reg, east_br, east_events = _make_router(east)
    west_router, _, west_reg, west_br, _ = _make_router(west)
    south_router, _, south_reg, south_br, _ = _make_router(south)
    try:
        loop = asyncio.new_event_loop()
        try:
            # East has one outbound link: to west.
            east_to_west = _connect_link(east_router, "west-host", "west", loop)
            # West has outbound links to both east and south.
            west_to_east = _connect_link(west_router, "east-host", "east", loop)
            west_to_south = _connect_link(west_router, "south-host", "south", loop)
            # South has an outbound link to west.
            _connect_link(south_router, "west-host-s", "west", loop)

            jid = salt.utils.jid.gen_jid(_opts_from_cluster(east))
            load = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 10,
            }

            # Drive east's publish fan-out through on_publish.
            monkeypatch.setattr(router_mod, "_ROUTER", east_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(load, loop))

            # East dispatched to exactly west; south is unreachable
            # directly.
            west_sends = _topology_pub_sends_to("west-host")
            assert len(west_sends) == 1, (
                f"flood publish must fan out to the one direct peer, got "
                f"{len(west_sends)} sends to west"
            )
            env = load["topology"]
            assert env["origin"] == "east"
            assert env["destinations"] is None, "flood scope -> destinations=None"

            # Transit: west receives the forwarded publish.  Its
            # inbound-link stand-in is west_to_east (that's who it
            # thinks the publish came from).  Build the inbound-shaped
            # load with path=["east"] so the receive-side path check
            # passes.
            inbound_load = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 10,
                "topology": {
                    "origin": "east",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["east"],
                },
            }
            forward_links, local_match = west_router.forward_publish(
                inbound_load, west_to_east
            )
            # West itself matched locally (flood).
            assert local_match is True
            # West re-forwarded to its OTHER peer (south), not back to east.
            fwd_cluster_ids = [
                getattr(ln, "peer_cluster_id", None) for ln in forward_links
            ]
            assert "south" in fwd_cluster_ids
            assert "east" not in fwd_cluster_ids

            # Breadcrumb lifecycle: west recorded a crumb pointing back
            # to east.  route_return on west resolves to the east-link.
            dummy_ret = {"jid": jid, "id": "web-01"}
            back_link = west_router.route_return(dummy_ret)
            assert (
                back_link is west_to_east
            ), "west's breadcrumb must point the return back to east"

            # Loop detection: a reflected publish arriving at east with
            # east in path is dropped.  Build the inbound shape as if
            # west were echoing it back.
            east_inbound_link = PeerMasterLink(
                dict(east_router.opts),
                PeerRef(host="west-host-echo", port=44600, finger=None),
                loop,
            )
            east_inbound_link._peer_cluster_id = "west"  # noqa: SLF001
            east_inbound_link._health = LinkHealth.CONNECTED  # noqa: SLF001
            reflected = {
                "tgt": "*",
                "jid": jid,
                "timeout": 10,
                "topology": {
                    "origin": "east",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["east", "west"],
                },
            }
            dropped_links, dropped_local = east_router.forward_publish(
                reflected, east_inbound_link
            )
            assert dropped_links == []
            assert dropped_local is False

            # Also: path-tampering drop.  An inbound whose path tail
            # does not match the authenticated peer_cluster_id gets
            # dropped.
            tampered = {
                "tgt": "*",
                "jid": jid,
                "timeout": 10,
                "topology": {
                    "origin": "south",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["south"],
                },
            }
            tamper_links, tamper_local = west_router.forward_publish(
                tampered, west_to_east
            )
            assert tamper_links == []
            assert tamper_local is False

            # No pub-failure events fired on east.
            failed = [e for e in east_events if "pub/failed" in e["tag"]]
            assert failed == []
        finally:
            loop.close()
    finally:
        east_br.close()
        east_reg.close()
        west_br.close()
        west_reg.close()
        south_br.close()
        south_reg.close()


# ---------------------------------------------------------------------------
# Scenario 3 --- Directional trust
# ---------------------------------------------------------------------------


def test_scenario_directional_trust_east_accepts_west_not_vice_versa(
    two_cluster_fixture, fakes, monkeypatch
):
    """
    Directional trust: east has accepted west in its ``pki_dir/masters/``,
    but west has NOT accepted east.

    Workflow:

    * west->east publish succeeds (east has west in masters/):
      verified by driving ``_handle_master_auth`` with a
      west-presenting cluster_id against east's pki_dir.
    * east->west publish fails at the handshake with
      PENDING_ACCEPT on east's outbound link to west.
      :func:`router.on_publish` surfaces this as a
      :exc:`LinkUnavailable` from the link's send machinery, which
      :func:`on_publish` catches and converts into a
      ``salt/topology/pub/failed/west`` event.
    """
    east, west = two_cluster_fixture
    # east accepts west; west does NOT accept east.
    east.accept_peer(west)
    assert west.cluster_id in east.inspect_registry()["peers"]
    assert east.cluster_id not in west.inspect_registry()["peers"]

    # Drive west->east handshake via east's real _handle_master_auth
    # (no master process involvement beyond pki_dir layout).  east's
    # masters/<west>.pub exists -> status=ok.
    import salt.topology.link_manager as link_manager

    link_manager._reset_module_state()  # noqa: SLF001
    try:
        east_opts_for_lm = _opts_from_cluster(east)
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(link_manager.start(east_opts_for_lm, loop))
            try:
                reply = loop.run_until_complete(
                    link_manager._handle_master_auth(  # noqa: SLF001
                        {"cmd": "_master_auth", "cluster_id": "west"}
                    )
                )
                assert reply["status"] == "ok", (
                    f"east should accept west handshake since west is in "
                    f"east's masters/: {reply}"
                )
                assert reply["cluster_id"] == "east"
            finally:
                loop.run_until_complete(link_manager.stop())
        finally:
            loop.close()
    finally:
        link_manager._reset_module_state()  # noqa: SLF001

    # Now the east->west side.  west has NOT accepted east: so when
    # east's PeerMasterLink dials west, the fake handshake returns
    # ``retry`` (modelling the real west's "pending_accept" response),
    # the link parks in PENDING_ACCEPT, and any send on it raises
    # LinkUnavailable, which router.on_publish turns into a
    # pub/failed/west event.

    east_router, _, east_reg, east_br, east_events = _make_router(east)
    try:
        loop = asyncio.new_event_loop()
        try:
            link_opts = dict(east_router.opts)
            link_opts["topology_handshake_backoff"] = 0
            link_opts["topology_handshake_max_tries"] = 1
            _FakeReqChannel.handshake_by_host["west-host"] = {
                "status": "retry",
                "cluster_id": "west",
            }
            link = PeerMasterLink(
                link_opts, PeerRef(host="west-host", port=44600, finger=None), loop
            )
            loop.run_until_complete(link.connect())
            assert link.health == LinkHealth.PENDING_ACCEPT, (
                f"west not-accepting-east should park the link in "
                f"PENDING_ACCEPT; got {link.health!r}"
            )
            # Even though handshake didn't yield peer_cluster_id, we
            # register under 'west' so route_publish can target it
            # by name.  (Real link_manager would do this via its
            # provisional-key path --- we simulate the terminal state
            # after a user-visible accept would land.)
            link._peer_cluster_id = "west"  # noqa: SLF001
            east_router._links["west"] = link  # noqa: SLF001

            jid = salt.utils.jid.gen_jid(_opts_from_cluster(east))
            load = {
                "tgt": "C@west and *",
                "tgt_type": "compound",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 5,
            }
            monkeypatch.setattr(router_mod, "_ROUTER", east_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(load, loop))

            # on_publish surfaces per-link failure via
            # salt/topology/pub/failed/<peer>.
            failed = [
                e for e in east_events if e["tag"] == "salt/topology/pub/failed/west"
            ]
            assert (
                failed
            ), f"expected pub/failed event for west, got events: {east_events!r}"
            assert failed[0]["data"]["cluster_id"] == "west"
            assert failed[0]["data"]["jid"] == jid
            assert "LinkUnavailable" in failed[0]["data"]["error"]
        finally:
            loop.close()
    finally:
        east_br.close()
        east_reg.close()


# ---------------------------------------------------------------------------
# Scenario 4 --- Duplicate minion id across clusters
# ---------------------------------------------------------------------------


def test_scenario_duplicate_minion_id_disambiguated_by_cluster_path(
    two_cluster_fixture, topology_minion_opts, fakes, monkeypatch
):
    """
    Duplicate ``web-01`` minion id on east AND west.  Operator on east
    runs flooded ``salt 'web-01' test.ping``.

    Verifications:

    * East's :meth:`TopologyRouter.route_publish` fans the publish
      to west (flood target, no C@ scope).  Both masters execute
      locally.
    * Returns from both minions land in east's job cache (east is
      the origin).  The east-local return uses
      ``cluster_path=("east",)``; the west-origin return uses
      ``cluster_path=("west",)``.  Both on-disk files exist and
      their contents differ --- no clobber.
    * The ``cluster_path`` field appears on the fired job event
      payload, so :mod:`salt-run jobs.lookup_jid` would surface
      both returns distinguishably when it reads the on-disk
      layout.
    """
    east, west = two_cluster_fixture
    east.accept_peer(west)
    west.accept_peer(east)
    east.config_peer(west)
    west.config_peer(east)

    east_router, _, east_reg, east_br, east_events = _make_router(east)
    west_router, _, west_reg, west_br, _ = _make_router(west)
    try:
        loop = asyncio.new_event_loop()
        try:
            _connect_link(east_router, "west-host", "west", loop)
            _connect_link(west_router, "east-host", "east", loop)

            jid = salt.utils.jid.gen_jid(_opts_from_cluster(east))
            load = {
                "tgt": "web-01",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 10,
            }
            monkeypatch.setattr(router_mod, "_ROUTER", east_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(load, loop))

            # Flood -> east dispatched to west, no failures.
            west_sends = _topology_pub_sends_to("west-host")
            assert len(west_sends) == 1, (
                f"flooded 'web-01' publish must dispatch to the one peer "
                f"(west); got {len(west_sends)}"
            )
            failed = [e for e in east_events if "pub/failed" in e["tag"]]
            assert failed == []

            # Simulate both minions returning.  The east-local return
            # (origin's own minion) stores with cluster_path=("east",);
            # the west-origin return (received by east over the link
            # and demuxed) stores with cluster_path=("west",).  The
            # local_cache returner is driven directly via store_job to
            # exercise the (jid, cluster_path, id) coordinate.
            opts = _job_cache_opts(topology_minion_opts)

            class _CapturingEvent:
                def __init__(self):
                    self.events = []
                    self.ret_loads = []

                def fire_event(self, load_, tag):
                    self.events.append((tag, load_))

                def fire_ret_load(self, load_):
                    self.ret_loads.append(load_)

            east_event_sink = _CapturingEvent()

            east_ret = _make_minion_load("web-01", jid, payload="from-east")
            west_ret = _make_minion_load("web-01", jid, payload="from-west")

            salt.utils.job.store_job(
                opts,
                east_ret,
                event=east_event_sink,
                cluster_path=("east",),
            )
            salt.utils.job.store_job(
                opts,
                west_ret,
                event=east_event_sink,
                cluster_path=("west",),
            )

            # Both returns on disk, distinguishable, no clobber.
            import pathlib

            jobs_root = pathlib.Path(opts["cachedir"], "jobs")
            jid_dir = pathlib.Path(
                salt.utils.jid.jid_dir(jid, str(jobs_root), opts["hash_type"])
            )
            east_file = jid_dir / "east" / "web-01" / "return.p"
            west_file = jid_dir / "west" / "web-01" / "return.p"
            assert east_file.is_file()
            assert west_file.is_file()
            assert east_file.read_bytes() != west_file.read_bytes()
            # Unqualified path never created.
            assert not (jid_dir / "web-01" / "return.p").is_file()

            # The fired events carry cluster_path --- so a job-lookup
            # subscriber (salt-run jobs.lookup_jid is the canonical
            # one) can distinguish the two returns.
            fired_paths = [
                tuple(load_.get("cluster_path") or ())
                for _tag, load_ in east_event_sink.events
            ]
            assert ("east",) in fired_paths
            assert ("west",) in fired_paths
        finally:
            loop.close()
    finally:
        east_br.close()
        east_reg.close()
        west_br.close()
        west_reg.close()
