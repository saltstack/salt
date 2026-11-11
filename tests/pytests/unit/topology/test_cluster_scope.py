"""
Unit tests for :func:`salt.topology.router.extract_cluster_scope`.

These pin the documented behaviour of the ``C@<cluster_id>`` compound
scope token described in ``doc/topics/master-topology/index.md`` under
"Targeting across clusters".  Pure-function tests --- no master spin-up
and no loader involvement.

Each test mirrors a concrete example (or edge case) listed in the
docs so a docs/implementation drift surfaces here first.
"""

import salt.topology.router as router

# ---------------------------------------------------------------------------
# Section: ``C@<cluster_id>`` --- direct cluster scope
# ---------------------------------------------------------------------------


class TestDocumentedExamples:
    """Pin the three worked examples from the ``C@`` docs section."""

    def test_single_cluster(self):
        # Docs: ``salt -C 'C@west' test.ping`` -> single cluster
        assert router.extract_cluster_scope("C@west") == {"west"}

    def test_comma_separated_list(self):
        # Docs: ``salt -C 'C@west,east-sub' test.ping``
        assert router.extract_cluster_scope("C@west,east-sub") == {
            "west",
            "east-sub",
        }

    def test_combined_with_other_matchers(self):
        # Docs: ``salt -C 'C@west and G@os:ubuntu' test.ping``
        assert router.extract_cluster_scope("C@west and G@os:ubuntu") == {"west"}


class TestDocumentedEdgeCases:
    """Pin the three edge cases called out in the docs."""

    def test_c_at_adjacent_to_or_floods(self):
        # Docs: ``C@east or web-*`` -> flood (returns None)
        assert router.extract_cluster_scope("C@east or web-*") is None

    def test_or_inside_parens_does_not_flood(self):
        # Docs mention this sibling case in the router docstring:
        # ``C@east and (web-* or db-*)`` keeps scope = {east} because
        # the ``or`` is at a deeper paren depth than the C@ token.
        got = router.extract_cluster_scope("C@east and (web-* or db-*)")
        assert got == {"east"}

    def test_not_c_is_not_stripped_and_floods(self):
        # Docs: ``not C@east and web-*`` is NOT stripped; router must
        # fall through to flood so each cluster evaluates locally.
        assert router.extract_cluster_scope("not C@east and web-*") is None

    def test_absence_of_c_floods(self):
        # Docs: "Absence of any C@ token means 'flood per policy.'"
        assert router.extract_cluster_scope("web-*") is None
        assert router.extract_cluster_scope("*") is None
        assert router.extract_cluster_scope("G@os:ubuntu and web-*") is None


# ---------------------------------------------------------------------------
# Section: ``N@<nodegroup>`` with embedded ``C@``
# ---------------------------------------------------------------------------


class TestNodegroupEmbeddedCAt:
    """
    Docs claim nodegroups whose definition contains ``C@`` are expanded
    *before* scope extraction.  Pin the expansion order so a regression
    in :func:`_expand_nodegroup_tokens` surfaces here.
    """

    def test_nodegroup_with_embedded_c_at(self):
        # Docs: nodegroup defined as ``C@west and web-*`` scopes to west.
        ng = {"production": "C@west and web-*"}
        assert router.extract_cluster_scope("N@production", nodegroups=ng) == {"west"}

    def test_nodegroup_without_c_at_floods(self):
        # Plain nodegroup (no C@) -> flood, consistent with bare glob.
        ng = {"webs": "web-*"}
        assert router.extract_cluster_scope("N@webs", nodegroups=ng) is None

    def test_unknown_nodegroup_floods(self):
        # Unresolvable N@ must not crash and must fall through to flood.
        assert router.extract_cluster_scope("N@missing", nodegroups={}) is None

    def test_no_nodegroups_arg_leaves_n_at_opaque(self):
        # Without nodegroups mapping, N@ stays opaque -> no C@ seen ->
        # flood.  Protects against the bug where router.master.py calls
        # extract_cluster_scope() *without* ``nodegroups=`` and silently
        # misroutes a nodegroup-scoped publish.
        assert router.extract_cluster_scope("N@production") is None


# ---------------------------------------------------------------------------
# Section: pre-tokenised input (compound-matcher shape)
# ---------------------------------------------------------------------------


class TestTokenisedInput:
    """The router must accept both str and list-of-tokens form."""

    def test_list_input(self):
        tokens = ["C@east,west", "and", "web-*"]
        assert router.extract_cluster_scope(tokens) == {"east", "west"}

    def test_empty_string(self):
        assert router.extract_cluster_scope("") is None

    def test_none_input(self):
        assert router.extract_cluster_scope(None) is None
