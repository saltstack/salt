"""
Functional tests for the ``C@`` cluster matcher's integration with
Salt's compound-target machinery.

The matcher plugin :mod:`salt.matchers.cluster_match` is landed by
Phase 1; the wiring exercised here is Phase 5:

* :data:`salt.utils.minions.TARGET_REX` must recognise ``C`` as a
  compound engine so ``parse_target("C@east")`` yields a usable
  dict instead of dropping the token into the ``pattern`` bucket.
* :meth:`salt.utils.minions.CkMinions._check_compound_minions` must
  dispatch ``C@`` clauses to a cluster-aware handler at
  ``ClearFuncs.publish`` time.  Without that entry the origin
  master silently returns zero matched minions and never dispatches
  the publish.
* :data:`salt.matchers.compound_match.ref` must dispatch ``C`` to
  the ``cluster`` matcher plugin so per-minion compound evaluation
  honours the clause (relevant for mixed-engine expressions the
  router preserves across the wire).

Each test boots a real master via :mod:`tests.pytests.functional.topology`
fixtures and calls into ``CkMinions.check_minions`` so the end-to-
end master-side dispatch is exercised (not just the pure matcher
plugin, which is already covered by ``test_cluster_match.py``).
"""

import pytest

import salt.utils.minions

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def _ckminions(cluster, cluster_id):
    """
    Build a :class:`CkMinions` bound to *cluster*'s first master,
    with ``cluster_id`` set.  Returns the ck object so the caller
    can hit ``check_minions`` directly.

    Sets ``cluster_pki_dir`` to the master's live ``pki_dir`` so
    the key-cache (:mod:`salt.cache.localfs_key`) resolves accepted-
    minion lookups without crashing.  In production a topology master
    is also a 3008.x cluster peer, so this field is already set; the
    functional harness builds single-master clusters where only the
    topology identity is live, so we backfill the sibling here.
    """
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = cluster_id
    if not opts.get("cluster_pki_dir"):
        opts["cluster_pki_dir"] = opts.get("pki_dir")
    return salt.utils.minions.CkMinions(opts)


# ---------------------------------------------------------------------
# Target-expression parsing + ref-dict wiring
# ---------------------------------------------------------------------


def test_target_rex_accepts_cluster_engine(single_master):
    """
    ``parse_target("C@east")`` must identify ``C`` as the engine,
    ``east`` as the pattern, and leave the delimiter unset.
    """
    single_master(cluster_id="east")
    parsed = salt.utils.minions.parse_target("C@east")
    assert parsed["engine"] == "C"
    assert parsed["pattern"] == "east"
    assert parsed["delimiter"] is None


def test_target_rex_accepts_cluster_union(single_master):
    """``C@east,west`` must parse with the comma-separated set intact."""
    single_master(cluster_id="east")
    parsed = salt.utils.minions.parse_target("C@east,west")
    assert parsed["engine"] == "C"
    assert parsed["pattern"] == "east,west"


# ---------------------------------------------------------------------
# ``check_minions`` dispatch at publish time
# ---------------------------------------------------------------------


def test_c_at_local_cluster_matches_local_minion(single_master, attach_minion):
    """
    ``salt -C 'C@east'`` on an ``east`` master resolves to the
    local accepted minion.  This is the baseline origin-cluster
    check that the router relies on to decide "we have local
    minions to publish to."
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("C@east", tgt_type="compound")

    assert minion.id in result["minions"]


def test_c_at_local_cluster_and_glob_intersect(single_master, attach_minion):
    """
    ``salt -C 'C@east and <minion-id>'`` resolves to the glob-matching
    local minion when the cluster_id matches.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    expr = f"C@east and {minion.id}"
    result = ck.check_minions(expr, tgt_type="compound")

    assert minion.id in result["minions"]


def test_c_at_remote_cluster_resolves_to_empty_locally(single_master, attach_minion):
    """
    ``salt -C 'C@west'`` on an ``east`` master resolves to zero
    local matches.  Fan-out to the ``west`` peer is the router's
    job and happens elsewhere; what we assert here is that the
    origin-cluster check does *not* false-positive on an unrelated
    cluster target.
    """
    cluster = single_master(cluster_id="east")
    attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("C@west", tgt_type="compound")

    assert result["minions"] == []


def test_c_at_remote_cluster_and_glob_is_empty(single_master, attach_minion):
    """
    ``C@west and <local-minion-id>`` on an ``east`` master is empty
    locally — the ``and`` with a non-matching cluster clause must
    gate out the glob side.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    expr = f"C@west and {minion.id}"
    result = ck.check_minions(expr, tgt_type="compound")

    assert result["minions"] == []


def test_c_at_union_matches_when_local_is_in_set(single_master, attach_minion):
    """
    ``C@east,west`` on an ``east`` master resolves to local
    minions — east is in the union.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("C@east,west", tgt_type="compound")

    assert minion.id in result["minions"]


def test_c_at_union_matches_on_west_master(single_master, attach_minion):
    """
    Same union, but on a ``west`` master — still matches locally.
    Confirms the matcher is cluster-aware, not hard-coded to one
    side of the pair.
    """
    cluster = single_master(cluster_id="west")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "west")
    result = ck.check_minions("C@east,west", tgt_type="compound")

    assert minion.id in result["minions"]


def test_c_at_union_without_local_is_empty(single_master, attach_minion):
    """
    ``C@north,south`` on an ``east`` master — neither name is this
    cluster, so no local matches.
    """
    cluster = single_master(cluster_id="east")
    attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("C@north,south", tgt_type="compound")

    assert result["minions"] == []


# ---------------------------------------------------------------------
# Mixed-engine expressions
# ---------------------------------------------------------------------


def test_grain_and_cluster_combination_matches(single_master, attach_minion):
    """
    ``G@os:* and C@east`` on an ``east`` master matches a local minion
    with any OS grain.  Confirms the ``and``-combinator pairs the
    cluster clause with a traditional matcher correctly.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("G@os:* and C@east", tgt_type="compound")

    assert minion.id in result["minions"]


def test_grain_and_remote_cluster_is_empty(single_master, attach_minion):
    """
    ``G@os:* and C@west`` on an ``east`` master is empty — the
    cluster clause gates everything, even when the grain clause
    would otherwise match.
    """
    cluster = single_master(cluster_id="east")
    attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("G@os:* and C@west", tgt_type="compound")

    assert result["minions"] == []


# ---------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------


def test_glob_only_target_unchanged_without_c_at(single_master, attach_minion):
    """
    A plain compound target with no ``C@`` clause continues to
    resolve the way it did before the wiring landed.  Regression
    guard for the TARGET_REX change.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions(minion.id, tgt_type="compound")

    assert minion.id in result["minions"]


def test_grain_only_compound_unchanged(single_master, attach_minion):
    """
    ``G@os:*`` without any ``C@`` clause continues to resolve.
    Confirms the compound-match plugin's ref dict change didn't
    perturb the grain path.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions("G@os:*", tgt_type="compound")

    assert minion.id in result["minions"]


def test_list_target_unchanged(single_master, attach_minion):
    """
    ``L@a,b,c`` continues to resolve.  Compound-matcher regression
    guard outside the grain subsystem.
    """
    cluster = single_master(cluster_id="east")
    minion = attach_minion(cluster)

    ck = _ckminions(cluster, "east")
    result = ck.check_minions(f"L@{minion.id}", tgt_type="compound")

    assert minion.id in result["minions"]
