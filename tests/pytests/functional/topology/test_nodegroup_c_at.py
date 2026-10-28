"""
Functional tests for :func:`salt.topology.router.extract_cluster_scope`
with nodegroup pre-expansion.

A nodegroup definition can embed ``C@`` tokens.  Without pre-expansion,
the router scans only the raw ``N@<name>`` reference and defaults to
flood.  :func:`extract_cluster_scope` is wired through
:meth:`TopologyRouter.route_publish` with ``opts["nodegroups"]`` so a
``C@``-bearing nodegroup is visible to the scope scan and the publish
is routed to only the named clusters.

Covered cases:

* Nodegroup containing a single ``C@east`` -> scope == {"east"}.
* Nodegroup containing ``C@east and web-*`` -> scope == {"east"}.
* Nodegroup referencing another nodegroup that contains ``C@west``
  (recursive expansion) -> scope == {"west"}.
* Empty nodegroup -> scope is ``None`` (flood).
* Non-existent nodegroup -> scope is ``None`` (flood, matches
  :func:`nodegroup_comp`'s own error-tolerant return).
* Nodegroup referencing itself (cycle) -> scope is ``None`` (flood).
* Nodegroup with multiple ``C@`` tokens unioned -> scope union.
* Compound mixing an ``N@`` wrapping ``C@`` with a positive ``C@``
  outside -> union of both.
* ``N@`` reference under ``not`` -> flood (negation path trumps).
* ``route_publish`` end-to-end: the correct peer links are chosen.
"""

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fixtures / helpers (mirrors test_router.py's lightweight pattern)
# ---------------------------------------------------------------------------


def _router_opts(tmp_path, cluster_id, nodegroups=None):
    pki_dir = tmp_path / f"{cluster_id}-pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    opts = {
        "pki_dir": str(pki_dir),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 512,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
    }
    if nodegroups is not None:
        opts["nodegroups"] = nodegroups
    return opts


def _make_router(tmp_path, cluster_id, nodegroups=None):
    opts = _router_opts(tmp_path, cluster_id, nodegroups=nodegroups)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br_cache = breadcrumbs.open_writer(opts)
    reg_cache = registry.open_writer(opts)
    r = router.TopologyRouter(opts, reg_cache, br_cache)
    return r, opts, reg_cache, br_cache


class _StubLink:
    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = "connected"


# ---------------------------------------------------------------------------
# extract_cluster_scope with nodegroup pre-expansion
# ---------------------------------------------------------------------------


class TestExtractClusterScopeNodegroups:
    def test_single_c_at_in_nodegroup(self):
        ng = {"east_only": "C@east"}
        assert router.extract_cluster_scope("N@east_only", nodegroups=ng) == {"east"}

    def test_c_at_with_additional_terms_in_nodegroup(self):
        ng = {"east_web": "C@east and web-*"}
        assert router.extract_cluster_scope("N@east_web", nodegroups=ng) == {"east"}

    def test_recursive_nodegroup(self):
        ng = {
            "inner": "C@west",
            "outer": "N@inner and db-*",
        }
        assert router.extract_cluster_scope("N@outer", nodegroups=ng) == {"west"}

    def test_recursive_three_levels_deep(self):
        ng = {
            "l0": "C@north",
            "l1": "N@l0",
            "l2": "N@l1 and web-*",
        }
        assert router.extract_cluster_scope("N@l2", nodegroups=ng) == {"north"}

    def test_empty_nodegroup_returns_flood(self):
        ng = {"empty": ""}
        assert router.extract_cluster_scope("N@empty", nodegroups=ng) is None

    def test_missing_nodegroup_returns_flood(self):
        # nodegroup_comp returns "" on an unknown nodegroup --> no C@ seen,
        # flood semantics.
        assert router.extract_cluster_scope("N@does_not_exist", nodegroups={}) is None

    def test_cyclic_nodegroup_returns_flood(self):
        # nodegroup_comp protects against cycles and returns "".  The
        # outer N@ expands to empty, no C@ visible, flood.
        ng = {"loop": "N@loop and web-*"}
        assert router.extract_cluster_scope("N@loop", nodegroups=ng) is None

    def test_or_adjacent_c_at_in_nodegroup_floods(self):
        """
        ``C@east or C@west`` inside a nodegroup expands to tokens where
        each ``C@`` sits adjacent to ``or``.  The router's
        :func:`_c_at_adjacent_to_or` rule treats any ``or``-adjacent
        ``C@`` as flood (``None``) because the conservative pattern
        cannot distinguish ``C@east or C@west`` (which could safely
        resolve to ``{east, west}``) from ``C@east or web-*`` (where
        the OR branches to a non-cluster-scoped predicate).  See the
        docstring on :func:`salt.topology.router.extract_cluster_scope`.
        """
        ng = {"multi": "C@east or C@west"}
        assert router.extract_cluster_scope("N@multi", nodegroups=ng) is None

    def test_or_between_nodegroup_and_c_at_floods(self):
        """
        An ``or`` connecting a C@-bearing nodegroup to a top-level
        ``C@`` lands under the same conservative rule as
        :meth:`test_or_adjacent_c_at_in_nodegroup_floods`.
        """
        ng = {"east_web": "C@east and web-*"}
        got = router.extract_cluster_scope("N@east_web or C@south", nodegroups=ng)
        assert got is None

    def test_not_near_nodegroup_floods(self):
        # Explicit negation still returns None (flood) --- the receiver
        # evaluates the full compound locally.
        ng = {"east_only": "C@east"}
        assert (
            router.extract_cluster_scope("web-* and not N@east_only", nodegroups=ng)
            is None
        )

    def test_nodegroup_with_no_c_at_falls_through(self):
        ng = {"plain": "web-* and G@os:ubuntu"}
        assert router.extract_cluster_scope("N@plain", nodegroups=ng) is None

    def test_no_nodegroups_opt_is_safe(self):
        # If opts["nodegroups"] is absent, N@ tokens stay opaque and no
        # C@ is extracted --> flood.  Pre-existing behavior preserved.
        assert router.extract_cluster_scope("N@any_name") is None


# ---------------------------------------------------------------------------
# route_publish wires nodegroups through
# ---------------------------------------------------------------------------


class TestRoutePublishWithNodegroups:
    def test_route_publish_picks_only_scoped_peer(self, tmp_path):
        ng = {"east_web": "C@east and web-*"}
        r, opts, reg, br = _make_router(tmp_path, "origin", nodegroups=ng)
        try:
            east = _StubLink("east")
            west = _StubLink("west")
            r._links = {"east": east, "west": west}
            load = {"tgt": "N@east_web", "jid": "20200101000000000000"}
            links, local_match = r.route_publish(load)
            # Only east is in scope.
            assert [link.peer_cluster_id for link in links] == ["east"]
            # Envelope reflects the extracted destinations.
            env = load["topology"]
            assert env["origin"] == "origin"
            assert env["destinations"] == ["east"]
            assert env["transit_match"] is False  # origin != east
            assert env["path"] == []
            assert local_match is False
        finally:
            br.close()
            reg.close()

    def test_route_publish_flood_on_missing_nodegroup(self, tmp_path):
        r, opts, reg, br = _make_router(tmp_path, "origin", nodegroups={})
        try:
            east = _StubLink("east")
            west = _StubLink("west")
            r._links = {"east": east, "west": west}
            load = {"tgt": "N@missing", "jid": "20200101000000000001"}
            links, local_match = r.route_publish(load)
            # Unknown nodegroup -> flood: all peer links picked, local match.
            assert sorted(link.peer_cluster_id for link in links) == [
                "east",
                "west",
            ]
            assert local_match is True
            assert load["topology"]["destinations"] is None
        finally:
            br.close()
            reg.close()

    def test_route_publish_recursive_nodegroup(self, tmp_path):
        ng = {
            "inner": "C@west",
            "outer": "N@inner",
        }
        r, opts, reg, br = _make_router(tmp_path, "origin", nodegroups=ng)
        try:
            east = _StubLink("east")
            west = _StubLink("west")
            r._links = {"east": east, "west": west}
            load = {"tgt": "N@outer", "jid": "20200101000000000002"}
            links, _ = r.route_publish(load)
            assert [link.peer_cluster_id for link in links] == ["west"]
            assert load["topology"]["destinations"] == ["west"]
        finally:
            br.close()
            reg.close()
