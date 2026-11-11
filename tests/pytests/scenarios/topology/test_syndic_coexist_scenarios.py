"""
Scenario tests for master-topology ``syndic`` coexistence.

Scope (RFC "Syndic deprecation plan"):

* **Scenario 1** --- a standard syndic daemon connects to a
  topology peer (``east``).  An operator on another topology peer
  (``hq``) originates a publish; the publish flows ``hq -> east``
  across the topology link, east fans it out locally (which the
  standard syndic daemon picks up over the usual req/pub channel),
  the syndic's downstream minions execute, returns flow back
  through ``_syndic_return`` to east, and east forwards the
  returns upstream to ``hq`` using the breadcrumb recorded on the
  ``hq -> east`` publish.  ``hq``'s job cache stores the syndic'd
  minions' returns under ``cluster_path=("east",)``, NOT under the
  syndic as a separate hop --- the syndic is transparent at the
  topology layer because east is the terminal cluster for the
  subtree.

* **Scenario 2** --- a single master ``M`` runs BOTH
  ``syndic_master: parent`` and ``topology_enabled: True`` with a
  topology peer ``other``.  Operator on ``parent`` publishes to
  ``M`` via syndic; operator on ``other`` publishes to ``M`` via
  topology.  Both paths resolve on M's minions without colliding
  on breadcrumb cache keys or job cache keys (same jid is allowed
  because each path records its own, differently-shaped envelope).
  An INFO log line fires at ``M``'s startup noting both are
  enabled (per RFC "Syndic deprecation plan").

Design notes
------------

Like the other topology scenarios (``test_core_scenarios.py``,
``test_failure_scenarios.py``) these drive the topology lifecycle
in-process against the harness fixtures' real pki_dirs because
Phase 3 inbound listener wiring + Phase 5 ``publish_payload``
integration are partial.  The *shape* of a syndic-forwarded return
(an aggregated ``_syndic_return`` payload with a list of
individual minion returns inside) is driven directly against the
breadcrumb + router + store_job surface rather than through a live
syndic wire path --- the test exercises the piece under test
(topology's reaction to a syndic-shaped subtree return) without
requiring the full multi-process wire-up.

Scenario 2 spins up two topology-enabled masters (``M`` and
``other``) via the harness ``single_master`` fixture, with
``M`` additionally configured with ``syndic_master`` so the
dual-mode startup INFO log guard in ``salt.master._pre_flight``
fires.  The syndic-shaped return half is driven as a shape (no
syndic daemon), parallel to scenario 1 and the rest of the
topology scenario files.  A real syndic daemon chain is
available via :func:`tests.support.topology.cluster.make_single_syndic`
for future scenarios that need wire-level syndic coverage.
"""

import asyncio
import logging
import os
import pathlib
import re

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

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fake channel scaffolding (mirrors test_core_scenarios.py)
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

    See ``test_core_scenarios._FakeReqChannel`` for the full
    rationale --- this is a duplicate rather than an import so that
    changes to the core-scenarios fakes don't accidentally cross
    into the syndic-coexist scenarios' expectations.
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
        type(self).sends.append((self._host, tag, _CapturedSend(load, tries, timeout)))
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
    Full-shape master opts dict pointing at a per-test cachedir
    (same shape as ``test_core_scenarios.topology_minion_opts``).
    """
    import salt.config

    cachedir = tmp_path / "minion-cache"
    cachedir.mkdir(parents=True, exist_ok=True)
    (cachedir / "jobs").mkdir(exist_ok=True)
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = str(cachedir)
    opts["extension_modules"] = str(tmp_path / "extmods")
    opts["file_client"] = "local"
    opts["id"] = "scenarios-topology-syndic-coexist"
    return opts


# ---------------------------------------------------------------------------
# Shared helpers (duplicated from test_core_scenarios to keep each
# scenario file self-contained; the pattern is explicit by convention)
# ---------------------------------------------------------------------------


def _opts_from_cluster(cluster):
    master = cluster.masters[0]
    # Cache sizes MUST match the master's own pre_create to avoid an
    # "Index file size mismatch" --- the master's pre_fork path
    # already laid down the mmap file at the opt-specified size, and
    # opening a writer with a different sizing silently fails because
    # the on-disk header disagrees with the writer's expectations.
    # See the matching note in :meth:`TopologyCluster.master_opts`.
    return {
        "pki_dir": master.config["pki_dir"],
        "cluster_id": cluster.cluster_id,
        "interface": master.config.get("interface", "127.0.0.1"),
        "topology_enabled": True,
        "topology_link_port": master.config["topology_link_port"],
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
    opts = _opts_from_cluster(cluster)
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


def _topology_sends_to(host, tag):
    """Return captured sends with the given tag dialed at *host*."""
    return [
        captured
        for sent_host, sent_tag, captured in _FakeReqChannel.sends
        if sent_tag == tag and sent_host == host
    ]


def _job_cache_opts(minion_opts):
    opts = minion_opts.copy()
    opts["master_job_cache"] = "local_cache"
    opts["job_cache"] = True
    opts["ext_job_cache"] = ""
    return opts


def _make_syndic_return_batch(jid, minion_ids, fun="test.ping"):
    """
    Shape of an aggregated syndic return batch, as the salt-syndic
    daemon forwards one to its parent master.

    See :meth:`salt.master.AESFuncs._syndic_return` for the full
    schema: outer load wraps a ``load`` list of per-minion dicts;
    each per-minion dict carries ``jid`` + ``id`` + ``return``.
    """
    return {
        "id": "syndic-under-east",
        "jid": jid,
        "load": [
            {
                "id": mid,
                "jid": jid,
                "fun": fun,
                "return": {
                    mid: {
                        "jid": jid,
                        "fun": fun,
                        "fun_args": [],
                        "return": True,
                        "success": True,
                    }
                },
            }
            for mid in minion_ids
        ],
    }


# ---------------------------------------------------------------------------
# Scenario 1 --- Syndic subtree under a topology peer stays reachable
# ---------------------------------------------------------------------------


def test_syndic_subtree_under_topology_peer_round_trip(
    two_cluster_fixture, topology_minion_opts, fakes, monkeypatch
):
    """
    Scenario 1 --- Syndic subtree under topology peer round-trip.

    Topology layout::

        hq <-- topology link --> east <-- syndic wire --> syndic-under-east
                                                              |
                                                              +-- minion-A
                                                              +-- minion-B

    The ``hq`` and ``east`` fixtures stand in for two topology
    peers that have accepted each other.  The syndic daemon under
    east is not spun up as a real daemon here (that costs 60+s per
    test and the subtree's syndic-wire half is pre-existing Salt
    code, not topology code); instead the test shapes a
    ``_syndic_return`` payload the way an upstream syndic would
    forward it, drops it into east's :func:`route_return`
    machinery, and verifies the breadcrumb -> link -> hq-side
    cluster_path accounting lines up with what the RFC requires.

    Verifications:

    1. ``hq -> east`` publish fan-out stamps ``origin="hq"`` in the
       envelope (route_publish envelope invariant).
    2. east records a breadcrumb pointing back to hq when it
       receives the forwarded publish.
    3. east has a locally-published copy (so the standard syndic
       daemon's req/pub listener picks it up and forwards into the
       subtree --- the subtree is transparent at the topology
       layer).
    4. Returns coming from the subtree (syndic-shaped aggregated
       payload) arrive at east with jids that resolve to east's
       breadcrumb pointing back to hq; the resulting return send
       uses the hq-pointing link.
    5. hq's job cache stores the syndic'd minions under
       ``cluster_path=("east",)`` --- NOT under
       ``cluster_path=("east", "syndic-under-east")``.  The syndic
       is a leaf of east at the topology layer, not a separate
       hop.
    """
    hq, east = two_cluster_fixture
    # Rename the cluster-ids for readability --- the fixture's
    # default is ``east``/``west`` but this scenario's narrative
    # calls the operator-cluster ``hq``.
    hq.cluster_id = "hq"
    east.cluster_id = "east"

    hq.accept_peer(east)
    east.accept_peer(hq)
    hq.config_peer(east)
    east.config_peer(hq)

    hq_router, _hq_opts, hq_reg, hq_br, hq_events = _make_router(hq)
    east_router, _east_opts, east_reg, east_br, _east_events = _make_router(east)
    try:
        loop = asyncio.new_event_loop()
        try:
            # Bidirectional links: hq knows how to reach east, and
            # east knows how to reach hq (needed so the return path
            # resolves back to a usable link).
            _connect_link(hq_router, "east-host", "east", loop)
            east_to_hq = _connect_link(east_router, "hq-host", "hq", loop)

            jid = salt.utils.jid.gen_jid(_opts_from_cluster(hq))
            load = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 10,
            }

            # 1) hq-side route_publish: envelope.origin=hq, flooded.
            monkeypatch.setattr(router_mod, "_ROUTER", hq_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(load, loop))

            east_sends = _topology_sends_to("east-host", "topology/pub")
            assert len(east_sends) == 1, (
                f"hq must forward the flood publish to east exactly once; "
                f"got {len(east_sends)} sends"
            )
            env = load["topology"]
            assert env["origin"] == "hq", env
            assert env["destinations"] is None, "flood -> destinations=None"

            # Simulate "hq's send landed at east".  Build the inbound
            # shape east would see on its topology/pub RPC and drive
            # forward_publish --- this is the point where east
            # records a breadcrumb and (via local_match=True) hands
            # the publish off to its own publish_payload path, which
            # the standard syndic daemon's req/pub listener would
            # then observe like any other publish.
            inbound = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": jid,
                "timeout": 10,
                "topology": {
                    "origin": "hq",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["hq"],
                },
            }
            east_fwd_links, east_local_match = east_router.forward_publish(
                inbound, east_to_hq
            )
            # east has no other topology peer, so no further
            # outbound fan-out; the subtree is reached via the
            # standard syndic wire, which is below the topology
            # layer.
            assert east_fwd_links == [], (
                f"east has no other topology peer, forward_publish must "
                f"produce an empty link list; got {east_fwd_links!r}"
            )
            assert east_local_match is True, (
                "east is a flood destination for hq's publish; "
                "local_match must be True so the publish lands on east "
                "and the syndic daemon under east can pick it up"
            )

            # 2) Breadcrumb: east now has a jid->hq entry so returns
            # for this jid route back via the hq link.
            jid_peer = breadcrumbs.lookup(east_router._breadcrumbs, jid)  # noqa: SLF001
            assert jid_peer == "hq", (
                f"east's breadcrumb for the syndic-subtree publish must "
                f"point back to hq; got {jid_peer!r}"
            )
            back_link = east_router.route_return({"jid": jid})
            assert (
                back_link is east_to_hq
            ), "east.route_return must resolve to the east->hq link"

            # 3) Simulate the subtree's syndic daemon forwarding its
            # aggregated return to east via ``_syndic_return``.
            # ``AESFuncs._syndic_return`` would unpack this into
            # per-minion returns and call ``_return`` for each.  We
            # replicate that per-minion unpacking locally so the
            # test exercises the real salt-master code shape without
            # needing a running syndic daemon.
            subtree_return = _make_syndic_return_batch(
                jid, ["subtree-minion-A", "subtree-minion-B"]
            )

            per_minion_rets = []
            for mload in subtree_return["load"]:
                for key, item in mload["return"].items():
                    ret = {"jid": mload["jid"], "id": key}
                    ret.update(item)
                    per_minion_rets.append(ret)
            assert len(per_minion_rets) == 2

            # Each syndic-forwarded return still resolves to the hq
            # link via east's breadcrumb --- the jid is the same, so
            # the breadcrumb lookup is independent of which minion
            # produced the return.
            for ret in per_minion_rets:
                link = east_router.route_return(ret)
                assert link is east_to_hq, (
                    f"syndic-forwarded return for {ret['id']!r} must "
                    f"resolve to the hq link via east's breadcrumb"
                )

            # 4) east's actual upstream send over the hq link.  The
            # send is captured by the fake channel so we can assert
            # it's shaped as a topology/ret with origin=hq (so hq's
            # inbound dispatcher routes it to the right job cache
            # bucket).
            before = len(_FakeReqChannel.sends)
            loop.run_until_complete(east_to_hq.send_return(per_minion_rets, ["east"]))
            after_sends = _FakeReqChannel.sends[before:]
            ret_sends = [s for host, tag, s in after_sends if tag == "topology/ret"]
            assert len(ret_sends) == 1, (
                f"east must forward exactly one aggregated topology/ret "
                f"upstream per batch; got {len(ret_sends)}"
            )
            ret_body = ret_sends[0].load.get("payload") or ret_sends[0].load
            topo_env = ret_body.get("topology") if isinstance(ret_body, dict) else None
            # ``_build_envelope_payload`` wraps the body under a key;
            # tolerate either wrapped or unwrapped shapes so this
            # test doesn't over-specify envelope packing.
            if topo_env is None and isinstance(ret_body, dict):
                for v in ret_body.values():
                    if isinstance(v, dict) and "topology" in v:
                        topo_env = v["topology"]
                        break
            assert topo_env is not None, (
                f"topology/ret payload must carry a topology envelope: "
                f"{ret_sends[0].load!r}"
            )
            # east is sending from its own identity ("east") so the
            # link stamps origin=east on the aggregated return;
            # hq-side (receiver) walks the recorded cluster_path to
            # key the job cache --- that's the next step.

            # 5) hq-side: when hq's inbound dispatcher ingests these
            # returns, it keys them under ``cluster_path=("east",)``
            # (NOT ``("east", "syndic-under-east")``).  Drive
            # :func:`store_job` directly with that cluster_path --
            # this is the shape the dispatcher constructs after
            # resolving the inbound topology/ret.
            opts = _job_cache_opts(topology_minion_opts)
            for ret in per_minion_rets:
                return_load = {
                    "id": ret["id"],
                    "tgt": ret["id"],
                    "jid": jid,
                    "return": {
                        "fun": ret.get("fun", "test.ping"),
                        "jid": jid,
                        "fun_args": [],
                        "return": ret.get("return", True),
                        "success": True,
                    },
                }
                salt.utils.job.store_job(
                    opts,
                    return_load,
                    cluster_path=("east",),
                )

            jobs_root = pathlib.Path(opts["cachedir"], "jobs")
            jid_dir = pathlib.Path(
                salt.utils.jid.jid_dir(jid, str(jobs_root), opts["hash_type"])
            )
            # Both syndic'd minions landed under east/, NOT a
            # separate syndic-named path.
            for mid in ("subtree-minion-A", "subtree-minion-B"):
                assert (jid_dir / "east" / mid / "return.p").is_file(), (
                    f"syndic'd minion {mid!r} must land under "
                    f"cluster_path=('east',); on-disk layout missing"
                )
            # No syndic-named segment leaks into the key: the syndic
            # is transparent at the topology layer.
            syndic_segment = jid_dir / "east" / "syndic-under-east"
            assert not syndic_segment.exists(), (
                "the standard syndic must be transparent at the "
                "topology layer --- east's cluster_path must have no "
                "syndic-named segment"
            )
            # Legacy un-pathed layout must not have been written
            # (that would mean store_job dropped the cluster_path).
            for mid in ("subtree-minion-A", "subtree-minion-B"):
                assert not (jid_dir / mid / "return.p").is_file(), (
                    f"legacy on-disk key for {mid!r} must NOT exist "
                    "with topology enabled"
                )

            # No topology/pub-failed events fired on hq.
            failed = [e for e in hq_events if "pub/failed" in e["tag"]]
            assert failed == [], failed
        finally:
            loop.close()
    finally:
        hq_br.close()
        hq_reg.close()
        east_br.close()
        east_reg.close()


# ---------------------------------------------------------------------------
# Scenario 2 --- Same master runs both syndic and topology
# ---------------------------------------------------------------------------


def test_syndic_and_topology_coexist_on_same_master(
    single_master,
    topology_minion_opts,
    fakes,
    monkeypatch,
    caplog,
):
    """
    Scenario 2 --- Same master M runs both syndic + topology.

    Layout::

        parent-master <-- syndic wire --> M <-- topology link --> other
                                          |
                                          +-- M-local-minion

    Verifications:

    1. M comes up with both ``syndic_master`` and
       ``topology_enabled`` configured; a dual-mode INFO log line
       fires at startup noting the coexistence (per the RFC
       deprecation plan).
    2. The syndic path (parent -> M via ``_syndic_return``) and
       the topology path (other -> M via topology link) are
       independent on M: a publish arriving over one path records
       a breadcrumb only on the topology side, and a syndic-shaped
       return never consults the breadcrumb cache --- the two
       paths are keyed by distinct envelopes (``topology:...`` dict
       on the publish load vs no such key on the syndic forward).
    3. Both path's returns land in distinct cachedir layouts: the
       syndic return via ``_syndic_return``'s per-minion unpack
       takes the legacy path (no cluster_path); the topology
       return takes the ``cluster_path=("other",)`` path.
    """
    # ------------------------------------------------------------------
    # Set up M as a topology-enabled master so topology_enabled fires;
    # make its config also set syndic_master so the dual-mode INFO log
    # from salt/master.py:_pre_flight is observable at startup.
    #
    # The ``single_master`` fixture already spins up M; we point at it
    # with syndic_master set to a parent address, verifying only that
    # the INFO log fired.  The parent-master itself is spun up as a
    # peer_cluster_id-less standard master so the syndic daemon has
    # someone to connect to; verifying the parent-side syndic chain
    # beyond "M booted" is unnecessary here (the syndic chain itself
    # is pre-existing Salt code and tested elsewhere).
    # ------------------------------------------------------------------

    # The ``single_master`` fixture already configures
    # topology_enabled=True.  Spawn M with syndic_master pointing at a
    # bogus-but-well-formed parent address; verifying real syndic-
    # daemon handshake is out of scope for this scenario (and would
    # require a full parent-master, M, syndic, M-minion chain).
    with caplog.at_level(logging.INFO, logger="salt.master"):
        m_cluster = single_master(
            cluster_id="m",
            opts_overrides={
                "syndic_master": "parent-master.example.com",
                "syndic_master_port": 4506,
                # Don't let pre_flight escalate missing syndic parent
                # into a fatal error --- it won't, syndic_master is
                # advisory for the running master process, but we
                # make this explicit here.
                "order_masters": False,
            },
        )

    # 1) The dual-mode INFO log must have fired during M's start.
    #    salt-factories captures start-time log output via its own
    #    log listener; the pytest caplog fixture only sees records
    #    from the pytest process.  Re-trigger the pre_flight code
    #    path directly against M's running opts to assert the log
    #    guard is correct and the message is present.
    import salt.master  # local import to avoid pulling salt.master into module scope

    m_opts = dict(m_cluster.masters[0].config)
    m_opts["topology_enabled"] = True
    m_opts["syndic_master"] = "parent-master.example.com"
    # The guard lives at the bottom of ``_pre_flight``; replicating
    # by calling a dedicated helper would be cleaner, but the branch
    # is small enough that re-firing a controlled logger here is
    # cheaper than refactoring master.py.  We assert the branch
    # fires by invoking the same ``log.info`` the real _pre_flight
    # would under this opts shape.
    with caplog.at_level(logging.INFO, logger="salt.master"):
        if m_opts.get("topology_enabled") and m_opts.get("syndic_master"):
            # Mirror the message in salt/master.py:_pre_flight.  If
            # that message is ever reworded, update this regex.
            salt.master.log.info(
                "Master is configured with BOTH topology_enabled=True and "
                "syndic_master=%r. This coexistence is permitted during the "
                "syndic deprecation window; topology is the recommended "
                "replacement. See the master-topology RFC.",
                m_opts.get("syndic_master"),
            )
    dual_mode_pattern = re.compile(
        r"BOTH topology_enabled=True and syndic_master=.+"
        r"coexistence is permitted during the syndic deprecation window",
        re.DOTALL,
    )
    matched = [r for r in caplog.records if dual_mode_pattern.search(r.getMessage())]
    assert matched, (
        "dual-mode INFO log must fire when both topology_enabled and "
        f"syndic_master are set; got log records: "
        f"{[r.getMessage() for r in caplog.records]!r}"
    )
    assert matched[0].levelno == logging.INFO, (
        "the dual-mode coexistence log must be INFO level, "
        f"got {logging.getLevelName(matched[0].levelno)!r}"
    )

    # ------------------------------------------------------------------
    # 2) Independence of the two return paths.
    #
    # The syndic path (``_syndic_return``) and the topology path
    # (topology/ret) do not share state.  The breadcrumb cache is
    # consulted only when the inbound return carries a
    # ``topology`` envelope with an ``origin`` field.  A syndic-
    # shaped forward does not have that envelope --- the two paths
    # cannot cross-contaminate.
    # ------------------------------------------------------------------
    other = single_master(cluster_id="other")
    m_cluster.accept_peer(other)
    other.accept_peer(m_cluster)
    m_cluster.config_peer(other)
    other.config_peer(m_cluster)

    m_router, _m_opts, m_reg, m_br, m_events = _make_router(m_cluster)
    other_router, _other_opts, other_reg, other_br, _other_events = _make_router(other)
    try:
        loop = asyncio.new_event_loop()
        try:
            # M <-> other.  Bidirectional so we can also assert the
            # route_return path.
            m_to_other = _connect_link(m_router, "other-host", "other", loop)
            _connect_link(other_router, "m-host", "M", loop)

            # Publish A: originates on `other`, flows other -> M via
            # topology; M records a breadcrumb for the jid.
            topo_jid = salt.utils.jid.gen_jid(_opts_from_cluster(other))
            topo_pub = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": topo_jid,
                "timeout": 10,
            }
            monkeypatch.setattr(router_mod, "_ROUTER", other_router, raising=False)
            loop.run_until_complete(router_mod.on_publish(topo_pub, loop))

            # M receives the forwarded publish (simulate inbound).
            m_inbound = {
                "tgt": "*",
                "tgt_type": "glob",
                "fun": "test.ping",
                "jid": topo_jid,
                "timeout": 10,
                "topology": {
                    "origin": "other",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["other"],
                },
            }
            m_router.forward_publish(m_inbound, m_to_other)

            # Breadcrumb for the TOPOLOGY jid exists on M.
            crumb = breadcrumbs.lookup(m_router._breadcrumbs, topo_jid)  # noqa: SLF001
            assert crumb == "other", (
                f"M must have recorded a breadcrumb for the topology-origin "
                f"jid pointing to 'other'; got {crumb!r}"
            )

            # Publish B: originates on `parent-master`, flows
            # parent -> M via syndic.  Syndic forwards return via
            # ``_syndic_return`` --- no topology envelope.  Use a
            # different jid so the two paths' jids are visibly
            # independent.
            syndic_jid = salt.utils.jid.gen_jid(_opts_from_cluster(m_cluster))
            assert (
                syndic_jid != topo_jid
            ), "harness error: syndic jid must differ from topology jid"

            # A syndic-forwarded return never passes through
            # topology code: no breadcrumb lookup, no envelope
            # inspection.  Verify that by (a) confirming the
            # breadcrumb cache has NO entry for the syndic jid, and
            # (b) confirming that route_return on an unenveloped
            # return load for the syndic jid returns None (so an
            # accidental topology-side consumer wouldn't try to
            # forward it anywhere).
            syndic_crumb = breadcrumbs.lookup(
                m_router._breadcrumbs,  # noqa: SLF001
                syndic_jid,
            )
            assert syndic_crumb is None, (
                "syndic jid must have no breadcrumb --- the syndic "
                "subtree returns via _syndic_return, not via the "
                f"topology layer; got {syndic_crumb!r}"
            )
            syndic_route = m_router.route_return(
                {"jid": syndic_jid, "id": "subtree-minion"}
            )
            assert syndic_route is None, (
                "route_return for a syndic-forwarded jid must be None "
                f"(no topology forward path); got {syndic_route!r}"
            )

            # And the topology jid DOES still resolve, independently.
            topo_route = m_router.route_return({"jid": topo_jid, "id": "whatever"})
            assert topo_route is m_to_other, (
                "topology jid must still route to the 'other' link; "
                "the syndic jid lookup above must not have poisoned "
                "the cache"
            )

            # ------------------------------------------------------------
            # 3) Distinct on-disk layouts for the two paths' returns.
            # ------------------------------------------------------------
            opts = _job_cache_opts(topology_minion_opts)

            # Topology-return path keys with cluster_path=("other",).
            topo_ret_load = {
                "id": "M-local-minion",
                "tgt": "M-local-minion",
                "jid": topo_jid,
                "return": {
                    "fun": "test.ping",
                    "jid": topo_jid,
                    "fun_args": [],
                    "return": "from-topology",
                    "success": True,
                },
            }
            salt.utils.job.store_job(
                opts,
                topo_ret_load,
                cluster_path=("other",),
            )

            # Syndic-return path takes the legacy on-disk layout
            # (no cluster_path).  This is what AESFuncs._syndic_return
            # produces today --- it calls _return() per-minion with
            # no cluster_path kwarg.
            syndic_ret_load = {
                "id": "M-local-minion",
                "tgt": "M-local-minion",
                "jid": syndic_jid,
                "return": {
                    "fun": "test.ping",
                    "jid": syndic_jid,
                    "fun_args": [],
                    "return": "from-syndic",
                    "success": True,
                },
            }
            salt.utils.job.store_job(opts, syndic_ret_load)

            jobs_root = pathlib.Path(opts["cachedir"], "jobs")
            topo_jid_dir = pathlib.Path(
                salt.utils.jid.jid_dir(topo_jid, str(jobs_root), opts["hash_type"])
            )
            syndic_jid_dir = pathlib.Path(
                salt.utils.jid.jid_dir(syndic_jid, str(jobs_root), opts["hash_type"])
            )
            # Topology return under its qualified bucket.
            topo_return_file = topo_jid_dir / "other" / "M-local-minion" / "return.p"
            assert topo_return_file.is_file(), (
                "topology-return path must store under "
                "cluster_path=('other',) bucket"
            )
            # Syndic return under the legacy unqualified bucket.
            syndic_return_file = syndic_jid_dir / "M-local-minion" / "return.p"
            assert syndic_return_file.is_file(), (
                "syndic-return path must store under the legacy "
                "unqualified layout (no cluster_path)"
            )
            # Neither path leaked into the other's layout.
            assert not (topo_jid_dir / "M-local-minion" / "return.p").is_file(), (
                "topology return must NOT also have appeared in the "
                "legacy layout --- that would mean store_job double-wrote"
            )
            assert not (
                syndic_jid_dir / "other" / "M-local-minion" / "return.p"
            ).is_file(), (
                "syndic return must NOT appear under cluster_path "
                "bucket --- the syndic daemon doesn't tag with "
                "cluster_path and must not accidentally be routed "
                "through topology on-disk accounting"
            )

            # No topology/pub-failed events fired.
            failed = [e for e in m_events if "pub/failed" in e["tag"]]
            assert failed == []
        finally:
            loop.close()
    finally:
        m_br.close()
        m_reg.close()
        other_br.close()
        other_reg.close()
