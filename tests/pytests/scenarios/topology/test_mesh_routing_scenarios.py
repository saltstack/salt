"""
Scenario tests for master-topology router BUGs #2b and #13g.

Both bugs live in :mod:`salt.topology.router` and are addressed
without any public-API change:

* **BUG #2b** --- Scoped ``C@`` routing to a non-adjacent cluster
  (chain ``A ↔ B ↔ C``, ``salt -C 'C@c and web-*'`` from A) silently
  dropped at the origin because ``route_publish`` picked outbound
  links only from direct peers.  The fix learns a next-hop route from
  the ``path`` field on each accepted summary and consults the
  routing table at route time; unresolved destinations fall through
  to flood with a WARNING log (parity with the syndic "if you don't
  know where it is, broadcast" behavior).

* **BUG #13g** --- ``C@east or web-*`` collapsed to ``destinations=
  {east}`` and dropped ``web-*`` minions on OTHER clusters.  The fix
  recognises an ``or`` operator sitting at the same paren depth as
  a ``C@`` token and returns ``None`` (flood) from
  ``extract_cluster_scope`` --- let every cluster's local matcher
  evaluate the full compound.  ``C@east and (web-* or db-*)`` is NOT
  affected: the inner ``or`` is at a different depth than the
  top-level ``C@``, so destinations stay ``{east}``.

Each test asserts the exact difference between pre-fix and post-fix
behavior and would have failed before the fix.  Style matches
``test_mesh_dedup_scenarios.py`` --- stub inbound links on a real
router with real breadcrumb / registry MmapCaches.
"""

import asyncio
import logging

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router_mod
from salt.topology.link import LinkHealth
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _StubInboundLink:
    """
    Minimal :class:`PeerMasterLink` stand-in that records sends.

    Mirrors the pattern used by ``test_mesh_dedup_scenarios.py``.
    """

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = LinkHealth.CONNECTED
        self.publishes = []
        self.summaries = []

    async def send_publish(self, load, path):
        self.publishes.append({"load": load, "path": list(path)})

    async def send_summary(self, summary):
        self.summaries.append(summary)


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
        "topology_link_port": 44507,
    }


def _make_router(tmp_path, cluster_id):
    """Build a real :class:`TopologyRouter` on fresh MmapCaches."""
    opts = _router_opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br_cache = breadcrumbs.open_writer(opts)
    reg_cache = registry.open_writer(opts)
    r = router_mod.TopologyRouter(opts, reg_cache, br_cache)
    return r, opts, reg_cache, br_cache


def _summary(cluster_id, path, origin_seq=1):
    """Build a :class:`ClusterSummary` with the given path."""
    return ClusterSummary(
        cluster_id=cluster_id,
        path=tuple(path),
        minion_count=1,
        up_count=1,
        grain_histograms={},
        origin_seq=origin_seq,
        origin_at=1_700_000_000.0,
    )


def _ingest(router, summary, link):
    """Run :meth:`ingest_summary` on a one-shot event loop."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(router.ingest_summary(summary, link))
    finally:
        loop.close()


# ===========================================================================
# BUG #2b --- non-adjacent scoped routing (chain A↔B↔C)
# ===========================================================================


def test_chain_scoped_C_at_non_adjacent_cluster_routes_via_transit_hop(tmp_path):
    """
    Chain ``A ↔ B ↔ C``, operator on A runs
    ``salt -C 'C@c and web-*' test.ping``.  A knows only B as a direct
    peer; the routing table learned from C's summary (traversed path
    ``[c, b]``) tells A that C is reachable via B.  Expected:
    ``route_publish`` returns ``[b_link]`` and ``local_match=False``.

    Pre-fix: ``_links`` filter picks no link because C isn't a direct
    peer -> empty list, silent drop.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        b_link = _StubInboundLink("b")
        r._links = {"b": b_link}  # pylint: disable=protected-access

        # Simulate the summary flow: C -> B -> A, so A ingests a
        # summary from origin ``c`` with ``path=[c, b]`` on the ``b``
        # link.  This is the only mechanism that populates the
        # routing table in the live system.
        _ingest(r, _summary("c", ["c", "b"]), b_link)

        load = {"tgt": "C@c and web-*", "jid": "jid-chain-1"}
        links, local = r.route_publish(load)

        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "b"
        }, f"route_publish must send to B (next hop toward C); got {onward}"
        assert local is False
        # Envelope carries C as the destination so B's forward_publish
        # knows which peer to transit to.
        assert load["topology"]["destinations"] == ["c"]
    finally:
        br.close()
        reg.close()


def test_chain_scoped_unknown_cluster_floods_with_warning(tmp_path, caplog):
    """
    Chain ``A ↔ B ↔ C``, operator on A runs
    ``salt -C 'C@nonexistent and web-*' test.ping`` for a cluster that
    is not in any summary A has seen.  Expected: FLOOD fallback with
    a WARNING log naming the unresolved destination.

    Pre-fix: silent drop (empty link list, no log above DEBUG).
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        b_link = _StubInboundLink("b")
        r._links = {"b": b_link}  # pylint: disable=protected-access

        load = {"tgt": "C@nonexistent and web-*", "jid": "jid-chain-2"}
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
            links, local = r.route_publish(load)

        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "b"
        }, f"unresolved destination must fall through to flood; got {onward}"
        assert local is False
        warnings = [
            rec.getMessage() for rec in caplog.records if rec.levelno >= logging.WARNING
        ]
        assert any(
            "no known route" in msg and "nonexistent" in msg for msg in warnings
        ), f"expected a WARNING naming the unresolved destination; got {warnings}"
    finally:
        br.close()
        reg.close()


def test_chain_scoped_mixed_destinations_route_via_single_hop(tmp_path):
    """
    Chain ``A ↔ B ↔ C``, operator on A runs
    ``salt -C 'C@b,c and web-*' test.ping``.  B is direct; C routes
    via B.  Expected: ``route_publish`` emits ONE link (B) because
    both destinations collapse to the same next hop.  B's own
    ``forward_publish`` is responsible for the second-hop transit to
    C --- that lives in the mesh-dedup scenarios.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        b_link = _StubInboundLink("b")
        r._links = {"b": b_link}  # pylint: disable=protected-access
        _ingest(r, _summary("c", ["c", "b"]), b_link)

        load = {"tgt": "C@b,c and web-*", "jid": "jid-chain-3"}
        links, local = r.route_publish(load)

        onward = [lnk.peer_cluster_id for lnk in links]
        assert onward == [
            "b"
        ], f"mixed destinations must dedupe to the single next hop; got {onward}"
        assert local is False
        # Envelope keeps both destinations so B's forward_publish can
        # fan out appropriately on the next hop.
        assert set(load["topology"]["destinations"]) == {"b", "c"}
    finally:
        br.close()
        reg.close()


def test_chain_scoped_route_prefers_shortest_path_after_fresher_summary(tmp_path):
    """
    Freshness invariant: a strictly-newer summary with a shorter path
    overrides a previously-learned longer route.  This matches the
    ``origin_seq`` dedup policy --- newer gossip overwrites stale
    topology info.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        b_link = _StubInboundLink("b")
        d_link = _StubInboundLink("d")
        r._links = {  # pylint: disable=protected-access
            "b": b_link,
            "d": d_link,
        }

        # First: learn C via B at distance 3 (path [c, x, b]).
        _ingest(r, _summary("c", ["c", "x", "b"], origin_seq=1), b_link)
        assert r._routes["c"] == ("b", 3)  # pylint: disable=protected-access

        # Then: a newer summary (seq=2) arrives via D at distance 2.
        _ingest(r, _summary("c", ["c", "d"], origin_seq=2), d_link)
        assert r._routes["c"] == ("d", 2)  # pylint: disable=protected-access

        load = {"tgt": "C@c", "jid": "jid-chain-4"}
        links, _local = r.route_publish(load)
        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "d"
        }, f"route must prefer D (shortest fresh path); got {onward}"
    finally:
        br.close()
        reg.close()


# ===========================================================================
# BUG #13g --- `C@east or web-*` collapses to east-only
# ===========================================================================


def test_or_adjacent_to_C_at_floods_destinations(tmp_path):
    """
    ``C@east or web-*`` on A↔B↔C should flood: ``web-*`` minions on
    other clusters must receive the publish.  Expected: ``route_publish``
    returns every peer link (flood) and ``destinations=None`` on the
    envelope so transit hops also flood.

    Pre-fix: destinations collapsed to ``{east}``; A sends only to
    east and ``web-*`` minions on other clusters miss the publish.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        b_link = _StubInboundLink("b")
        c_link = _StubInboundLink("c")
        east_link = _StubInboundLink("east")
        r._links = {  # pylint: disable=protected-access
            "b": b_link,
            "c": c_link,
            "east": east_link,
        }

        load = {"tgt": "C@east or web-*", "jid": "jid-or-1"}
        links, local = r.route_publish(load)

        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "b",
            "c",
            "east",
        }, f"OR-adjacent C@ must flood to every direct peer; got {onward}"
        assert local is True, "flood envelope implies local match=True"
        assert (
            load["topology"]["destinations"] is None
        ), "OR-adjacent C@ must set destinations=None (flood)"
    finally:
        br.close()
        reg.close()


def test_parens_isolate_or_from_C_at_keeps_scoped(tmp_path):
    """
    ``C@east and (web-* or db-*)`` keeps destinations=``{east}``
    because the ``or`` sits inside a parenthesised sub-expression at
    a deeper paren-depth than the top-level ``C@``.  The receiver's
    local matcher still evaluates ``(web-* or db-*)`` --- only the
    cluster scope is pinned.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        east_link = _StubInboundLink("east")
        b_link = _StubInboundLink("b")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "b": b_link,
        }

        load = {"tgt": "C@east and (web-* or db-*)", "jid": "jid-or-2"}
        links, local = r.route_publish(load)

        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "east"
        }, f"parens must isolate the OR; destinations stay east-only, got {onward}"
        assert local is False
        assert load["topology"]["destinations"] == [
            "east"
        ], f"destinations must still be east; got {load['topology']['destinations']}"
    finally:
        br.close()
        reg.close()


def test_top_level_or_crosses_C_at_scopes_floods(tmp_path):
    """
    ``C@east and web-* or C@west and db-*`` --- the top-level ``or``
    joins two cluster-scoped sub-expressions.  The router cannot
    honour a mixed scoping (east AND web-*) OR (west AND db-*) via
    its destination set --- it must flood and let each cluster's
    local matcher evaluate the full compound.
    """
    r, _opts, reg, br = _make_router(tmp_path, "a")
    try:
        east_link = _StubInboundLink("east")
        west_link = _StubInboundLink("west")
        b_link = _StubInboundLink("b")
        r._links = {  # pylint: disable=protected-access
            "east": east_link,
            "west": west_link,
            "b": b_link,
        }

        load = {
            "tgt": "C@east and web-* or C@west and db-*",
            "jid": "jid-or-3",
        }
        links, local = r.route_publish(load)

        onward = {lnk.peer_cluster_id for lnk in links}
        assert onward == {
            "east",
            "west",
            "b",
        }, f"top-level OR across C@ scopes must flood; got {onward}"
        assert local is True
        assert load["topology"]["destinations"] is None
    finally:
        br.close()
        reg.close()
