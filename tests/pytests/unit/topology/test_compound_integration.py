"""
Unit tests for the ``C@`` cluster matcher's integration with Salt's
compound-target machinery.

These are pure-structure tests: no master is spun up, no loader is
touched.  They assert the three wiring edits land in the shape the
RFC specifies so a refactor accidentally dropping one of them is
caught immediately.
"""

import inspect

import salt.matchers.compound_match as compound_match
import salt.utils.minions as minions

# ---------------------------------------------------------------------
# TARGET_REX
# ---------------------------------------------------------------------


def test_target_rex_matches_cluster_engine():
    """``C@east`` must match with ``engine='C'``, ``pattern='east'``."""
    m = minions.TARGET_REX.match("C@east")
    assert m is not None
    assert m.group("engine") == "C"
    assert m.group("pattern") == "east"


def test_target_rex_matches_cluster_union():
    """``C@east,west`` must match with ``pattern='east,west'``."""
    m = minions.TARGET_REX.match("C@east,west")
    assert m is not None
    assert m.group("engine") == "C"
    assert m.group("pattern") == "east,west"


def test_target_rex_cluster_delimiter_is_none():
    """
    ``C`` is not in the delimiter-eligible class (``G|P|I|J``), so a
    character after ``C`` must be treated as part of the pattern,
    not a delimiter.
    """
    m = minions.TARGET_REX.match("C@east")
    assert m is not None
    assert m.group("delimiter") is None


def test_parse_target_cluster_shape():
    """``parse_target("C@east")`` must return a usable dict."""
    parsed = minions.parse_target("C@east")
    assert parsed == {
        "engine": "C",
        "delimiter": None,
        "pattern": "east",
    }


def test_parse_target_cluster_union_shape():
    """``parse_target("C@east,west")`` must preserve the union pattern."""
    parsed = minions.parse_target("C@east,west")
    assert parsed["engine"] == "C"
    assert parsed["pattern"] == "east,west"
    assert parsed["delimiter"] is None


# ---------------------------------------------------------------------
# ``_check_compound_minions`` ref dict wiring
# ---------------------------------------------------------------------


def test_check_compound_minions_ref_has_cluster_entry():
    """
    ``CkMinions._check_compound_minions`` builds its dispatch
    table conditionally on ``minion_data_cache``.  Inspect the
    source to confirm ``"C"`` appears as a key — this is cheaper
    than instantiating a full ``CkMinions`` just to exercise the
    code path.
    """
    src = inspect.getsource(minions.CkMinions._check_compound_minions)
    assert '"C":' in src or "'C':" in src, (
        "_check_compound_minions must include a 'C' entry in its "
        "ref dict so C@ clauses dispatch to the cluster handler."
    )


# ---------------------------------------------------------------------
# ``compound_match.ref`` wiring
# ---------------------------------------------------------------------


def _make_ckminions(opts):
    """
    Build a bare :class:`CkMinions` for pure-logic tests.

    ``CkMinions.__init__`` wires up a cache driver, key store, and
    transport probe; none of that is needed for exercising the
    pure ``_local_cluster_id`` / ``_check_cluster_minions``
    branches.  Bypass ``__init__`` so the opts dict can stay
    minimal.
    """
    ck = minions.CkMinions.__new__(minions.CkMinions)
    ck.opts = opts
    ck.acc = "minions"
    return ck


def test_compound_match_source_dispatches_c_to_cluster():
    """
    ``salt.matchers.compound_match.match`` builds its ref dict
    locally.  Inspect the function source to confirm ``"C"`` maps
    to ``"cluster"`` so per-minion compound evaluation hits the
    cluster matcher plugin.
    """
    src = inspect.getsource(compound_match.match)
    assert (
        '"C": "cluster"' in src or "'C': 'cluster'" in src
    ), "compound_match.match's ref dict must map 'C' to 'cluster'."


# ---------------------------------------------------------------------
# ``_local_cluster_id`` --- topology-config fallback for C@ matching
# ---------------------------------------------------------------------


def test_local_cluster_id_prefers_opts_cluster_id():
    """``opts["cluster_id"]`` wins over everything else when present."""
    ck = _make_ckminions(
        {
            "cluster_id": "east",
            "master_cluster_id": "ignored",
            "topology_enabled": True,
        }
    )
    assert ck._local_cluster_id() == "east"


def test_local_cluster_id_falls_back_to_master_cluster_id():
    """
    ``opts["master_cluster_id"]`` is the second-tier source when the
    3008.x master-cluster primitive is not set.
    """
    ck = _make_ckminions({"master_cluster_id": "east"})
    assert ck._local_cluster_id() == "east"


def test_local_cluster_id_reads_topology_conf(tmp_path):
    """
    On a topology-enabled solo master, ``opts["cluster_id"]`` is
    FORBIDDEN by the pre-flight check (3008.x ``_pre_flight``
    requires ``cluster_peers`` whenever ``cluster_id`` is truthy).
    The topology identity must come from ``topology.conf`` via
    :func:`salt.config.topology.load_topology_config`.  This test
    pins that fallback: without ``opts["cluster_id"]``, the
    ``C@east`` match on a topology-enabled master still resolves
    to ``east``.
    """
    topo_conf = tmp_path / "topology.conf"
    topo_conf.write_text("cluster_id: east\npeers: []\n")
    ck = _make_ckminions(
        {
            "topology_enabled": True,
            "topology_config_file": str(topo_conf),
        }
    )
    assert ck._local_cluster_id() == "east"


def test_local_cluster_id_cached_per_opts(tmp_path):
    """
    The topology-config read is cached in
    ``opts["_topology_cluster_id_cache"]`` so the per-publish C@
    compound match does not re-parse ``topology.conf`` on every
    call.
    """
    topo_conf = tmp_path / "topology.conf"
    topo_conf.write_text("cluster_id: east\npeers: []\n")
    opts = {
        "topology_enabled": True,
        "topology_config_file": str(topo_conf),
    }
    ck = _make_ckminions(opts)
    first = ck._local_cluster_id()
    assert first == "east"
    assert opts["_topology_cluster_id_cache"] == "east"
    # Delete the config file to prove the second call uses the cache.
    topo_conf.unlink()
    assert ck._local_cluster_id() == "east"


def test_check_cluster_minions_dispatches_on_topology_cluster_id(tmp_path):
    """
    End-to-end: ``_check_compound_minions`` with target ``"C@east"``
    on a topology-only master (no ``opts["cluster_id"]``) must
    recognise east as the local cluster and return the all-minions
    set.  Pre-fix this returned empty because the C@ matcher only
    consulted ``opts["cluster_id"]``, which is unset on a
    topology-enabled solo master.
    """
    topo_conf = tmp_path / "topology.conf"
    topo_conf.write_text("cluster_id: east\npeers: []\n")
    ck = _make_ckminions(
        {
            "topology_enabled": True,
            "topology_config_file": str(topo_conf),
            "minion_data_cache": False,  # take the simple return path
        }
    )
    result = ck._check_cluster_minions("east", greedy=True, minions=["m1", "m2"])
    assert result["minions"] == ["m1", "m2"]


def test_check_cluster_minions_empty_when_not_in_scope(tmp_path):
    """
    ``_check_cluster_minions("west", ...)`` on an east master is
    empty.  The forward-only path is the router's responsibility;
    the local match contributes nothing.
    """
    topo_conf = tmp_path / "topology.conf"
    topo_conf.write_text("cluster_id: east\npeers: []\n")
    ck = _make_ckminions(
        {
            "topology_enabled": True,
            "topology_config_file": str(topo_conf),
        }
    )
    result = ck._check_cluster_minions("west", greedy=True, minions=["m1"])
    assert result["minions"] == []
