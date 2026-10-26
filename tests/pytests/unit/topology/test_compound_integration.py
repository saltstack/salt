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
