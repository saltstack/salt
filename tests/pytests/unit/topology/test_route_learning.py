"""
Regression tests for the "Route learning (gossip)" claims in
``doc/topics/master-topology/index.md``.

These pin the shapes the documentation makes promises about so
future refactors can't silently drift the wire payload, the routing
table, or the flood-on-unresolved log line.

Covered:

* ``topology/sum`` summary carries the three fields the docs claim
  (``cluster_id``, minion counts, authenticated ``path``) --- enforced
  via :func:`salt.topology.summary.serialize` on a ``ClusterSummary``
  built by :func:`salt.topology.summary.collect`.
* After :meth:`TopologyRouter.ingest_summary` the routing table has
  the documented shape ``destination_cluster_id ->
  (next_hop_peer_id, hop_count)``.
* Non-adjacent scoped publish via a learned route returns only the
  transit-hop link.
* Flood-on-unresolved is active in :meth:`TopologyRouter.route_publish`
  with the exact WARNING log line text the docs quote.
* The same policy (flood when any destination is unresolved) is
  active in :meth:`TopologyRouter.forward_publish`.
"""

import asyncio
import logging

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router
import salt.topology.summary as summary_mod
from salt.topology.summary import ClusterSummary

# ---------------------------------------------------------------------------
# Helpers (mirror test_router.py)
# ---------------------------------------------------------------------------


def _opts(tmp_path, cluster_id):
    pki_dir = tmp_path / f"{cluster_id}-pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_dir),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
        "topology_breadcrumb_cache_size": 256,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 256,
        "topology_registry_cache_key_size": 64,
    }


def _make_router(tmp_path, cluster_id):
    opts = _opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br = breadcrumbs.open_writer(opts)
    reg = registry.open_writer(opts)
    r = router.TopologyRouter(opts, reg, br)
    return r, opts, reg, br


class _Link:
    """Stand-in for :class:`salt.topology.link.PeerMasterLink`."""

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = "connected"

    async def send_summary(self, summary):
        # Capture-only; the route_publish/forward_publish tests don't
        # actually invoke this.
        return None


def _summary(cluster_id, path, origin_seq=1, minion_count=1, up_count=1):
    return ClusterSummary(
        cluster_id=cluster_id,
        path=tuple(path),
        minion_count=minion_count,
        up_count=up_count,
        grain_histograms={},
        origin_seq=origin_seq,
        origin_at=1_700_000_000.0,
    )


def _ingest(r, summary, link):
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(r.ingest_summary(summary, link))
    finally:
        loop.close()


# ===========================================================================
# 1. topology/sum summary wire shape
# ===========================================================================


class TestSummaryWireShape:
    """
    The docs claim: "Each master periodically sends a `topology/sum`
    summary to every peer link containing its own `cluster_id`,
    minion counts, and the authenticated `path` the summary traversed."
    """

    def test_serialize_includes_cluster_id_counts_and_path(self):
        s = _summary(
            "east",
            path=("east",),
            minion_count=42,
            up_count=37,
        )
        wire = summary_mod.serialize(s)
        # Documented fields.
        assert wire["cluster_id"] == "east"
        assert wire["minion_count"] == 42
        assert wire["up_count"] == 37
        assert wire["path"] == ["east"]
        # Path authentication prerequisite: path ends at the sender,
        # starts at the origin.
        assert wire["path"][0] == "east"
        assert wire["path"][-1] == "east"

    def test_with_path_extended_grows_path_only(self):
        s = _summary("east", path=("east",))
        extended = summary_mod.with_path_extended(s, "mid")
        assert extended.path == ("east", "mid")
        # Counts + origin are preserved (only path mutates on forward).
        assert extended.cluster_id == s.cluster_id
        assert extended.minion_count == s.minion_count
        assert extended.origin_seq == s.origin_seq

    def test_collect_seeds_path_with_own_cluster_id(self, tmp_path):
        """At origin, ``path`` is a one-tuple ``(cluster_id,)``."""
        opts = _opts(tmp_path, "origin")
        s = summary_mod.collect(opts)
        assert s.cluster_id == "origin"
        assert s.path == ("origin",)


# ===========================================================================
# 2. Routing table entry shape after ingest_summary
# ===========================================================================


class TestRoutingTableShape:
    """
    Docs: "Receiving peers record `(destination_cluster_id ->
    (next_hop_peer_id, hop_count))` in an in-process routing table."
    """

    def test_ingest_populates_routing_table_with_documented_shape(self, tmp_path):
        """
        Chain ``a <-> b <-> c``.  ``b`` ingests ``c``'s summary; its
        routing table should map ``c -> (c, 1)`` because ``c`` is a
        direct peer.  Then ``a`` ingests the same summary forwarded
        via ``b`` (path ``(c, b)``); its routing table should map
        ``c -> (b, 2)``.
        """
        # First hop: b learns c directly.
        r_b, _opts_b, reg_b, br_b = _make_router(tmp_path, "b")
        try:
            c_link = _Link("c")
            r_b._links = {"c": c_link}
            s_from_c = _summary("c", path=("c",), origin_seq=1)
            _ingest(r_b, s_from_c, c_link)

            assert "c" in r_b._routes
            entry = r_b._routes["c"]
            # Documented shape: tuple ``(next_hop_peer_id, hop_count)``.
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            next_hop, hop_count = entry
            assert next_hop == "c"
            assert isinstance(hop_count, int)
            # Path at receiver has length 1 (just the origin), so
            # the stored hop count is 1 (len(path)).
            assert hop_count == 1
        finally:
            br_b.close()
            reg_b.close()

        # Second hop: a learns c via b.
        r_a, _opts_a, reg_a, br_a = _make_router(tmp_path, "a")
        try:
            b_link = _Link("b")
            r_a._links = {"b": b_link}
            # b has forwarded c's summary; path is (c, b).
            s_via_b = _summary("c", path=("c", "b"), origin_seq=2)
            _ingest(r_a, s_via_b, b_link)

            assert "c" in r_a._routes
            next_hop, hop_count = r_a._routes["c"]
            assert next_hop == "b"  # direct peer to use as transit
            assert hop_count == 2  # len(path) == 2 clusters traversed
        finally:
            br_a.close()
            reg_a.close()

    def test_ingest_does_not_route_self(self, tmp_path):
        """A summary from the origin itself must not create a self-route."""
        r, _opts, reg, br = _make_router(tmp_path, "a")
        try:
            # ``a`` would never ingest its own summary via the
            # tamper-rejection path (path starts at origin == self),
            # but we exercise the explicit ``origin_id != self`` guard.
            b_link = _Link("b")
            r._links = {"b": b_link}
            s = _summary("b", path=("b",), origin_seq=1)
            _ingest(r, s, b_link)
            assert "a" not in r._routes
            assert "b" in r._routes
        finally:
            br.close()
            reg.close()


# ===========================================================================
# 3. route_publish uses learned routes for non-adjacent destinations
# ===========================================================================


class TestRoutePublishConsultsTable:
    def test_non_adjacent_destination_resolved_via_transit_hop(self, tmp_path):
        """
        Docs: "When `route_publish` is asked to send to a non-adjacent
        cluster, it consults this table to pick the correct transit peer."

        Chain ``a <-> b <-> c``, operator on ``a`` publishes to
        ``C@c``.  ``route_publish`` must return ``[b_link]``, not
        a flood.
        """
        r, _opts, reg, br = _make_router(tmp_path, "a")
        try:
            b_link = _Link("b")
            r._links = {"b": b_link}
            # Learn c via b from gossip.
            r._routes = {"c": ("b", 2)}

            load = {"tgt": "C@c and web-*", "jid": "j-non-adj"}
            links, local_match = r.route_publish(load)

            assert links == [b_link]
            assert local_match is False
            # Envelope marked correctly.
            assert load["topology"]["origin"] == "a"
            assert load["topology"]["destinations"] == ["c"]
        finally:
            br.close()
            reg.close()


# ===========================================================================
# 4. Flood-on-unresolved in route_publish, WARNING log text
# ===========================================================================


class TestRoutePublishFloodOnUnresolved:
    def test_unknown_destination_floods_with_documented_warning(self, tmp_path, caplog):
        """
        Docs claim the exact WARNING line:

            topology: route_publish flooding --- no known route for
            destination(s) ['east-sub'] (known routes: [])

        A scoped publish to ``east-sub`` (not a direct peer, no learned
        route) must flood every peer link AND emit the quoted warning.
        """
        r, _opts, reg, br = _make_router(tmp_path, "origin")
        try:
            # Two direct peers, neither of which is east-sub.
            west = _Link("west")
            north = _Link("north")
            r._links = {"west": west, "north": north}
            # Routing table empty: no gossip yet for east-sub.
            assert r._routes == {}

            load = {"tgt": "C@east-sub and web-*", "jid": "j-unresolved"}
            with caplog.at_level(logging.WARNING, logger="salt.topology.router"):
                links, _ = r.route_publish(load)

            # Flood -> both direct peers are returned.
            assert set(links) == {west, north}

            # Documented log substring, exactly as rendered.
            expected = (
                "topology: route_publish flooding --- no known route for "
                "destination(s) ['east-sub'] (known routes: [])"
            )
            messages = [rec.getMessage() for rec in caplog.records]
            assert expected in messages, (
                "route_publish WARNING line did not match the documented "
                f"string.\n expected: {expected!r}\n got: {messages!r}"
            )
        finally:
            br.close()
            reg.close()

    def test_mixed_resolved_and_unresolved_still_floods(self, tmp_path, caplog):
        """
        If ANY destination lacks a route, the whole publish floods
        (not just the unresolved subset).  This pins the
        ``flood_outbound = destinations is None or bool(unresolved)``
        branch.
        """
        r, _opts, reg, br = _make_router(tmp_path, "origin")
        try:
            west = _Link("west")
            north = _Link("north")
            r._links = {"west": west, "north": north}
            # ``west`` is adjacent; ``mystery`` is unknown.
            load = {"tgt": "C@west,mystery", "jid": "j-mixed"}
            with caplog.at_level(logging.WARNING, logger="salt.topology.router"):
                links, _ = r.route_publish(load)
            # Flood -> both links, including north which is in neither
            # the resolved set nor the destination set.
            assert set(links) == {west, north}
            flood_msgs = [
                rec.getMessage()
                for rec in caplog.records
                if "route_publish flooding" in rec.getMessage()
            ]
            assert flood_msgs, "expected flood warning on mixed destinations"
            # ``mystery`` must be named in the warning; ``west``
            # (resolved) must not.
            assert "'mystery'" in flood_msgs[0]
            assert "'west'" not in flood_msgs[0]
        finally:
            br.close()
            reg.close()


# ===========================================================================
# 5. forward_publish applies the same flood-on-unresolved rule
# ===========================================================================


class TestForwardPublishSameRule:
    """
    Docs: "...and matches the policy at transit hops (`forward_publish`
    uses the same rule)."
    """

    def test_transit_hop_floods_when_destination_unresolved(self, tmp_path, caplog):
        """
        Chain ``a -> b (-> ???)``.  ``b`` receives a publish from ``a``
        scoped to ``C@far`` where ``b`` has no route to ``far``.  The
        policy: forward to every non-inbound peer (flood) rather than
        silently drop.
        """
        r, _opts, reg, br = _make_router(tmp_path, "b")
        try:
            a_link = _Link("a")
            c_link = _Link("c")
            r._links = {"a": a_link, "c": c_link}
            # No route to "far" learned.
            assert r._routes == {}

            load = {
                "tgt": "C@far",
                "jid": "j-fwd-unresolved",
                "topology": {
                    "origin": "a",
                    "destinations": ["far"],
                    "transit_match": False,
                    # Path has been authenticated: tail == inbound peer.
                    "path": ["a"],
                },
            }
            with caplog.at_level(logging.DEBUG, logger="salt.topology.router"):
                links, local_match = r.forward_publish(load, a_link)

            # Transit flood: forwarded to every non-inbound peer.
            # ``a`` is excluded (inbound); ``c`` is included.
            assert links == [c_link]
            assert local_match is False
            # forward_publish logs at DEBUG (docs call this out), not
            # WARNING.
            fwd_msgs = [
                rec
                for rec in caplog.records
                if "forward_publish flooding" in rec.getMessage()
            ]
            assert fwd_msgs, "expected forward_publish flood debug line"
            assert fwd_msgs[0].levelno == logging.DEBUG
        finally:
            br.close()
            reg.close()

    def test_transit_hop_uses_learned_route_when_available(self, tmp_path):
        """
        Same chain as above, but ``b`` has learned ``far`` reachable
        via ``c``.  forward_publish should return only the transit hop,
        not a flood.
        """
        r, _opts, reg, br = _make_router(tmp_path, "b")
        try:
            a_link = _Link("a")
            c_link = _Link("c")
            d_link = _Link("d")
            r._links = {"a": a_link, "c": c_link, "d": d_link}
            r._routes = {"far": ("c", 2)}

            load = {
                "tgt": "C@far",
                "jid": "j-fwd-resolved",
                "topology": {
                    "origin": "a",
                    "destinations": ["far"],
                    "transit_match": False,
                    "path": ["a"],
                },
            }
            links, _ = r.forward_publish(load, a_link)
            # Only the resolved next-hop link.
            assert links == [c_link]
        finally:
            br.close()
            reg.close()
