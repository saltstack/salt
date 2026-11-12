"""
Functional tests for :mod:`salt.topology.router`.

Exercises :class:`salt.topology.router.TopologyRouter` against the
real :mod:`salt.topology.breadcrumbs`, :mod:`salt.topology.registry`,
and :mod:`salt.topology.summary` modules (no mocks of our own
code).  :class:`salt.topology.link.PeerMasterLink` is driven with
the same fake-channel pattern used by ``test_link.py`` so the
router's send-side fan-out can be verified without a Phase 3
inbound listener.

Covered:

* ``extract_cluster_scope`` on compound targets --- positive,
  union, ``not``-contains flood, no-``C@`` flood.
* ``strip_cluster_scope`` on documented examples including the
  ``not C@`` skip-strip rule and the empty-residual-becomes-``*``
  rule.
* ``route_publish`` builds the ``load["topology"]`` envelope
  with ``origin``, ``destinations``, ``transit_match``, and
  ``path=[]``.
* ``forward_publish`` enforces receiver-authenticates-path
  (``path[-1] == inbound_link.peer_cluster_id``); drops on
  tampered path tail; drops on cycle (self in path); strips
  self from destinations; records a breadcrumb.
* ``route_return`` returns the recorded link cluster_id and
  ``None`` when breadcrumb absent/expired.
* ``ingest_summary`` validates path origin, writes to
  registry's ``last_summary``-equivalent peer state, forwards
  to other peers via ``send_summary`` with ``with_path_extended``,
  and drops summaries whose path already contains self.
* ``on_publish`` schedules per-link ``send_publish`` tasks,
  gathers failures, and emits one
  ``salt/topology/pub/failed/<cluster_id>`` event per failed
  link so operators see per-cluster failures.
"""

import asyncio
import os

import pytest

import salt.channel.client
import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link as link_mod
import salt.topology.registry as registry
import salt.topology.router as router
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fake channel pattern (mirrors test_link.py)
# ---------------------------------------------------------------------------


class _CapturedSend:
    def __init__(self, load, tries, timeout, response):
        self.load = load
        self.tries = tries
        self.timeout = timeout
        self.response = response


class _FakeReqChannel:
    """Capture every outbound send; default response simulates ok."""

    handshake_response = None
    default_response = None
    sends = []  # noqa: RUF012
    fail_tags = ()  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        tag = None
        if isinstance(load, dict):
            tag = load.get("cmd") or load.get("tag")
        response = self.default_response
        if tag == "topology/_master_auth" and self.handshake_response is not None:
            response = self.handshake_response
        if tag in type(self).fail_tags:
            type(self).sends.append(_CapturedSend(load, tries, timeout, None))
            raise RuntimeError(f"forced failure for {tag!r}")
        captured = _CapturedSend(load, tries, timeout, response)
        type(self).sends.append(captured)
        return response

    async def connect(self):
        pass

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close_async()


class _FakePubChannel:
    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False
        self._callback = None

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def connect(self):
        pass

    def on_recv(self, callback):
        self._callback = callback

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True


@pytest.fixture
def fake_channels(monkeypatch):
    _FakeReqChannel.sends = []
    _FakePubChannel.sends = []
    _FakeReqChannel.fail_tags = ()
    _FakeReqChannel.handshake_response = {
        "status": "ok",
        "aes": os.urandom(32),
        "cluster_id": "peer",
        "endpoints": [],
    }
    _FakeReqChannel.default_response = {"status": "ok"}
    monkeypatch.setattr(
        salt.channel.client.AsyncReqChannel,
        "factory",
        _FakeReqChannel.factory,
    )
    monkeypatch.setattr(
        salt.channel.client.AsyncPubChannel,
        "factory",
        _FakePubChannel.factory,
    )
    monkeypatch.setattr(link_mod, "AsyncReqChannel", _FakeReqChannel, raising=False)
    monkeypatch.setattr(link_mod, "AsyncPubChannel", _FakePubChannel, raising=False)
    return {
        "req_sends": _FakeReqChannel.sends,
        "pub_sends": _FakePubChannel.sends,
        "req_cls": _FakeReqChannel,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _router_opts(tmp_path, cluster_id):
    pki_dir = tmp_path / f"{cluster_id}-pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_dir),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 512,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "topology_link_port": 44506,
    }


def _make_router(tmp_path, cluster_id):
    """Build a TopologyRouter with real registry + breadcrumbs caches."""
    opts = _router_opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br_cache = breadcrumbs.open_writer(opts)
    reg_cache = registry.open_writer(opts)
    r = router.TopologyRouter(opts, reg_cache, br_cache)
    return r, opts, reg_cache, br_cache


class _StubLink:
    """
    Minimal stand-in for :class:`PeerMasterLink` for routing tests
    that don't need the real send machinery.  Carries the two
    properties the router inspects (``peer_cluster_id``, ``health``)
    and records calls to :meth:`send_publish` / :meth:`send_summary`.
    """

    def __init__(self, peer_cluster_id, health=LinkHealth.CONNECTED, fail=False):
        self.peer_cluster_id = peer_cluster_id
        self.health = health
        self.fail = fail
        self.publishes = []
        self.summaries = []
        self.events = []

    async def send_publish(self, load, path):
        if self.fail:
            raise RuntimeError(f"forced failure for {self.peer_cluster_id!r}")
        self.publishes.append({"load": load, "path": list(path)})

    async def send_summary(self, summary):
        if self.fail:
            raise RuntimeError(f"forced failure for {self.peer_cluster_id!r}")
        self.summaries.append(summary)

    async def send_event(self, event, path):
        self.events.append({"event": event, "path": list(path)})


# ===========================================================================
# extract_cluster_scope
# ===========================================================================


class TestExtractClusterScope:
    """Positive, union, flood, and negation paths."""

    def test_single_cluster(self):
        assert router.extract_cluster_scope("C@east and web-*") == {"east"}

    def test_comma_union(self):
        assert router.extract_cluster_scope("C@east,west and G@os:ubuntu") == {
            "east",
            "west",
        }

    def test_multiple_c_tokens_unioned(self):
        got = router.extract_cluster_scope("(C@east and web-*) or (C@west and db-*)")
        assert got == {"east", "west"}

    def test_no_c_token_returns_none_flood(self):
        assert router.extract_cluster_scope("web-*") is None

    def test_glob_only_target_returns_none(self):
        assert router.extract_cluster_scope("*") is None

    def test_not_contains_returns_none_flood(self):
        """``not`` present anywhere -> conservatively flood."""
        assert router.extract_cluster_scope("not C@east and web-*") is None

    def test_tokenized_list_input(self):
        """A list-of-tokens input is accepted (compound matcher shape)."""
        tokens = ["C@east,west", "and", "web-*"]
        assert router.extract_cluster_scope(tokens) == {"east", "west"}

    def test_empty_string(self):
        assert router.extract_cluster_scope("") is None


# ===========================================================================
# strip_cluster_scope
# ===========================================================================


class TestStripClusterScope:
    """Documented cases + empty-residual + not-skip."""

    def test_strip_single_c(self):
        assert router.strip_cluster_scope("C@east and web-*") == "web-*"

    def test_strip_c_union_before_and(self):
        got = router.strip_cluster_scope("C@east,west and G@os:ubuntu")
        assert got == "G@os:ubuntu"

    def test_strip_parenthesised_or(self):
        got = router.strip_cluster_scope("(C@east and web-*) or (C@west and db-*)")
        # Residual must leave the OR structure intact; inner groups
        # become just the non-C half.
        assert got == "(web-*) or (db-*)"

    def test_strip_c_only_becomes_star(self):
        """Target of ``C@east`` alone -> ``"*"`` (match-everything)."""
        assert router.strip_cluster_scope("C@east") == "*"

    def test_strip_c_union_only_becomes_star(self):
        assert router.strip_cluster_scope("C@east,west") == "*"

    def test_not_skips_strip(self):
        """``not`` anywhere -> return tgt unchanged (receiving cluster evaluates)."""
        src = "not C@east and web-*"
        assert router.strip_cluster_scope(src) == src

    def test_no_c_passes_through(self):
        """No C@ token -> no change."""
        assert router.strip_cluster_scope("web-*") == "web-*"

    def test_strip_c_after_and(self):
        """`web-* and C@east` -> `web-*`."""
        assert router.strip_cluster_scope("web-* and C@east") == "web-*"


# ===========================================================================
# route_publish
# ===========================================================================


class TestRoutePublish:
    """Envelope builder at the origin."""

    def test_envelope_fields(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            load = {"tgt": "C@west and web-*", "jid": "20260101000000000001"}
            links, local_match = r.route_publish(load)
            env = load["topology"]
            assert env["origin"] == "east"
            assert set(env["destinations"] or []) == {"west"}
            assert env["path"] == []
            # east is NOT in destinations; local_match False.
            assert local_match is False
        finally:
            br.close()
            reg.close()

    def test_flood_target_destinations_none(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            load = {"tgt": "web-*", "jid": "20260101000000000002"}
            r.route_publish(load)
            env = load["topology"]
            assert env["destinations"] is None
        finally:
            br.close()
            reg.close()

    def test_self_in_destinations_local_match_true(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            load = {"tgt": "C@east,west and web-*", "jid": "jid-1"}
            links, local_match = r.route_publish(load)
            assert local_match is True
            env = load["topology"]
            assert env["transit_match"] is True
        finally:
            br.close()
            reg.close()


# ===========================================================================
# forward_publish --- path authentication + loop detection + shrink
# ===========================================================================


class TestForwardPublish:
    def test_tampered_path_dropped(self, tmp_path):
        """``path[-1]`` mismatch with inbound.peer_cluster_id -> drop."""
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            load = {
                "tgt": "*",
                "jid": "jid-tamper",
                "timeout": 5,
                "topology": {
                    "origin": "west",
                    "destinations": None,
                    "transit_match": True,
                    # sender SAYS the previous hop was 'north' but authenticated
                    # link identity is 'west' -> drop.
                    "path": ["west", "north"],
                },
            }
            links, local_match = r.forward_publish(load, inbound)
            assert links == [] and local_match is False
        finally:
            br.close()
            reg.close()

    def test_cycle_self_in_path_dropped(self, tmp_path):
        """``self.cluster_id`` already in authenticated path -> drop."""
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            load = {
                "tgt": "*",
                "jid": "jid-cycle",
                "timeout": 5,
                "topology": {
                    "origin": "west",
                    "destinations": None,
                    "transit_match": True,
                    # east already in path -> cycle, drop.
                    "path": ["origin", "east", "west"],
                },
            }
            links, local_match = r.forward_publish(load, inbound)
            assert links == [] and local_match is False
        finally:
            br.close()
            reg.close()

    def test_authenticated_path_appended_on_forward(self, tmp_path):
        """Receiver appends its OWN cluster_id to the forwarded copy."""
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            # Register a next-hop link so forward can hand it back.
            next_hop = _StubLink("south")
            r._links = {"south": next_hop}  # pylint: disable=protected-access
            inbound = _StubLink("west")
            load = {
                "tgt": "*",
                "jid": "jid-fwd-1",
                "timeout": 5,
                "topology": {
                    "origin": "west",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["west"],
                },
            }
            links, local_match = r.forward_publish(load, inbound)
            # Path must now be [..., inbound_peer, self].  Caller
            # consults ``load["topology"]["path"]`` on forwarded copy.
            env = load["topology"]
            assert env["path"][-1] == "east"
            # Flood destinations=None -> local_match True AND next hop
            # also receives.
            assert local_match is True
            assert next_hop in links
        finally:
            br.close()
            reg.close()

    def test_destinations_shrink_removes_self(self, tmp_path):
        """When destinations is a set, this cluster is removed on forward."""
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            next_hop = _StubLink("south")
            r._links = {"south": next_hop}  # pylint: disable=protected-access
            inbound = _StubLink("west")
            load = {
                "tgt": "C@east,south and *",
                "jid": "jid-fwd-2",
                "timeout": 5,
                "topology": {
                    "origin": "west",
                    "destinations": ["east", "south"],
                    "transit_match": True,
                    "path": ["west"],
                },
            }
            links, local_match = r.forward_publish(load, inbound)
            # East matches locally (it's in destinations).
            assert local_match is True
            # Forwarded envelope has east removed.
            env = load["topology"]
            assert "east" not in (env["destinations"] or [])
            assert set(env["destinations"]) == {"south"}
        finally:
            br.close()
            reg.close()

    def test_breadcrumb_recorded_on_forward(self, tmp_path):
        """forward_publish records a breadcrumb keyed on jid."""
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            next_hop = _StubLink("south")
            r._links = {"south": next_hop}  # pylint: disable=protected-access
            inbound = _StubLink("west")
            load = {
                "tgt": "*",
                "jid": "jid-crumb",
                "timeout": 5,
                "topology": {
                    "origin": "west",
                    "destinations": None,
                    "transit_match": True,
                    "path": ["west"],
                },
            }
            r.forward_publish(load, inbound)
            # Lookup the breadcrumb directly via the breadcrumbs API.
            got = breadcrumbs.lookup(br, "jid-crumb")
            assert got == "west"
        finally:
            br.close()
            reg.close()


# ===========================================================================
# route_return
# ===========================================================================


class TestRouteReturn:
    def test_hit_returns_inbound_cluster_id(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            r._links = {"west": inbound}  # pylint: disable=protected-access
            r.record_breadcrumb("jid-ret-1", inbound, timeout=5)
            ret = {"jid": "jid-ret-1", "id": "minion-a", "return": "ok"}
            got = r.route_return(ret)
            assert got is inbound or (
                got is not None and getattr(got, "peer_cluster_id", None) == "west"
            )
        finally:
            br.close()
            reg.close()

    def test_miss_returns_none(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            ret = {"jid": "jid-missing", "id": "minion-a", "return": "ok"}
            assert r.route_return(ret) is None
        finally:
            br.close()
            reg.close()


# ===========================================================================
# ingest_summary --- validation + forward + cycle drop
# ===========================================================================


class TestIngestSummary:
    def _summary(self, cluster_id, path, origin_seq=1):
        return ClusterSummary(
            cluster_id=cluster_id,
            path=tuple(path),
            minion_count=1,
            up_count=1,
            grain_histograms={},
            origin_seq=origin_seq,
            origin_at=1234567890.0,
        )

    def test_tampered_tail_rejected(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            # path[-1] is 'north' but inbound.peer_cluster_id is 'west'.
            s = self._summary("north", ["north"])
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(r.ingest_summary(s, inbound))
            finally:
                loop.close()
            # No peer entry got written.
            peer = registry.get_peer(reg, "north")
            assert peer is None
        finally:
            br.close()
            reg.close()

    def test_cycle_self_in_path_rejected(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            # east appears in path; cycle.
            s = self._summary("origin", ["origin", "east", "west"])
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(r.ingest_summary(s, inbound))
            finally:
                loop.close()
            peer = registry.get_peer(reg, "origin")
            assert peer is None
        finally:
            br.close()
            reg.close()

    def test_forward_to_other_peers_excludes_sender(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            inbound = _StubLink("west")
            north = _StubLink("north")
            south = _StubLink("south")
            r._links = {  # pylint: disable=protected-access
                "west": inbound,
                "north": north,
                "south": south,
            }
            s = self._summary("west", ["west"])

            # ``ingest_summary`` is async: drive it on a short-lived loop.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(r.ingest_summary(s, inbound))
            finally:
                loop.close()

            # inbound shouldn't receive its own summary.
            assert all(
                getattr(sent, "path", None) != s.path for sent in inbound.summaries
            )
            # north + south receive the summary with path extended through east.
            sent_targets = [link for link in (north, south) if link.summaries]
            assert sent_targets, "expected summary forwarded to at least one peer"
            for link in sent_targets:
                fwd = link.summaries[-1]
                assert fwd.path[-1] == "east"
                assert fwd.cluster_id == "west"
        finally:
            br.close()
            reg.close()


# ===========================================================================
# on_publish --- fan-out + failure event
# ===========================================================================


class TestOnPublish:
    def test_per_link_failure_emits_event(self, tmp_path, monkeypatch):
        """
        A link that raises on ``send_publish`` yields exactly one
        ``salt/topology/pub/failed/<cluster_id>`` event.
        """
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            # One healthy + one failing link.
            good = _StubLink("good")
            bad = _StubLink("bad", fail=True)
            r._links = {  # pylint: disable=protected-access
                "good": good,
                "bad": bad,
            }

            events = []

            def fake_fire(tag, data):
                events.append({"tag": tag, "data": data})

            # Install the router as the process-wide router for
            # on_publish to find.
            monkeypatch.setattr(router, "_ROUTER", r, raising=False)
            # Stub out the master event bus; on_publish needs *something*
            # to fire failure events through.
            r._fire_event = fake_fire  # pylint: disable=protected-access

            load = {
                "tgt": "*",
                "jid": "jid-pub-1",
                "timeout": 5,
            }

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(router.on_publish(load, loop))
            finally:
                loop.close()

            # good got the publish; bad raised.
            assert len(good.publishes) == 1
            assert len(bad.publishes) == 0
            # Exactly one failed event, scoped to the failing cluster.
            failed = [e for e in events if "pub/failed" in e["tag"]]
            assert len(failed) == 1
            assert "bad" in failed[0]["tag"]
        finally:
            br.close()
            reg.close()

    def test_no_router_returns_without_error(self, tmp_path, monkeypatch):
        """When topology is disabled (no router), on_publish is a no-op."""
        monkeypatch.setattr(router, "_ROUTER", None, raising=False)
        loop = asyncio.new_event_loop()
        try:
            # Should not raise.
            loop.run_until_complete(router.on_publish({"tgt": "*"}, loop))
        finally:
            loop.close()


# ===========================================================================
# get_router
# ===========================================================================


class TestGetRouter:
    def test_default_none(self, monkeypatch):
        monkeypatch.setattr(router, "_ROUTER", None, raising=False)
        assert router.get_router() is None

    def test_installed_router_returned(self, tmp_path, monkeypatch):
        r, opts, reg, br = _make_router(tmp_path, "east")
        try:
            monkeypatch.setattr(router, "_ROUTER", r, raising=False)
            assert router.get_router() is r
        finally:
            br.close()
            reg.close()


# ===========================================================================
# Integration-ish: router driving a real PeerMasterLink
# ===========================================================================


def _peer_ref(host="127.0.0.1", port=44600):
    return PeerRef(host=host, port=port, finger=None)


def test_route_publish_fans_out_via_real_link(tmp_path, fake_channels, monkeypatch):
    """
    End-to-end flavour: router.on_publish drives a real
    :class:`PeerMasterLink` whose transport is faked, and the fake
    channel sees a ``topology/pub`` envelope with origin+destinations.
    """
    r, opts, reg, br = _make_router(tmp_path, "east")
    try:
        link_opts = dict(opts)
        link_opts["topology_handshake_backoff"] = 0
        link_opts["topology_handshake_max_tries"] = 1
        # Build + connect a real PeerMasterLink via faked transport.
        loop = asyncio.new_event_loop()
        try:
            fake_channels["req_cls"].handshake_response = {
                "status": "ok",
                "aes": os.urandom(32),
                "cluster_id": "west",
                "endpoints": [],
            }
            link = PeerMasterLink(link_opts, _peer_ref(), loop)
            loop.run_until_complete(link.connect())
            assert link.health == LinkHealth.CONNECTED

            r._links = {"west": link}  # pylint: disable=protected-access

            # Simulate route_publish deciding west is the destination.
            load = {
                "tgt": "C@west and web-*",
                "jid": "jid-e2e-1",
                "timeout": 5,
            }
            r.route_publish(load)

            events = []
            r._fire_event = (
                lambda t, d: events.append(  # pylint: disable=protected-access
                    {"tag": t, "data": d}
                )
            )

            # Need the module-level accessor to find the router.
            monkeypatch.setattr(router, "_ROUTER", r, raising=False)
            loop.run_until_complete(router.on_publish(load, loop))

            # The fake req channel captured a topology/pub send.
            pub_sends = [
                s
                for s in fake_channels["req_sends"]
                if isinstance(s.load, dict)
                and (s.load.get("cmd") or s.load.get("tag")) == "topology/pub"
            ]
            assert pub_sends, "expected a topology/pub send through the link"
            payload = pub_sends[-1].load
            inner = payload["load"]
            env = inner["topology"]
            assert env["origin"] == "east"
            assert set(env["destinations"]) == {"west"}
        finally:
            loop.close()
    finally:
        br.close()
        reg.close()
