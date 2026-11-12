"""
Functional tests for :mod:`salt.matchers.cluster_match`.

These tests boot a real master via the topology harness, load the
matcher plugin through the real :func:`salt.loader.matchers`
loader, and call ``cluster_match.match`` directly.  Compound-
matcher integration (the ``C@`` sigil) is landed by other Phase 5
teams and is intentionally *not* exercised here.
"""

import pytest

import salt.loader

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def _cluster_match(opts):
    """Load the matcher LazyLoader off a real master's opts dict."""
    return salt.loader.matchers(opts)["cluster_match.match"]


def test_single_cluster_id_matches_on_master(single_master):
    """``opts['cluster_id'] == 'east'`` matched against ``'east'`` is True."""
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "east"
    assert _cluster_match(opts)("east", opts=opts) is True


def test_comma_separated_union_matches_east(single_master):
    """A master in ``east`` matches the union target ``east,west``."""
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "east"
    assert _cluster_match(opts)("east,west", opts=opts) is True


def test_comma_separated_union_matches_west(single_master):
    """A master in ``west`` matches the union target ``east,west``."""
    cluster = single_master(cluster_id="west")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "west"
    assert _cluster_match(opts)("east,west", opts=opts) is True


def test_non_matching_cluster_id_returns_false(single_master):
    """A master in ``west`` does not match target ``east``."""
    cluster = single_master(cluster_id="west")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "west"
    assert _cluster_match(opts)("east", opts=opts) is False


def test_minion_side_master_cluster_id_fallback(single_master):
    """
    When ``opts`` has no ``cluster_id`` (minion process) the matcher
    consults ``opts['master_cluster_id']`` instead.
    """
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts.pop("cluster_id", None)
    opts["master_cluster_id"] = "east"
    match = _cluster_match(opts)
    assert match("east", opts=opts) is True
    assert match("west", opts=opts) is False
    assert match("east,west", opts=opts) is True


def test_both_identifiers_missing_returns_false(single_master):
    """
    No ``cluster_id`` and no ``master_cluster_id`` -> safe non-match,
    regardless of the target.  Covers pre-handshake minions and
    non-topology masters.
    """
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts.pop("cluster_id", None)
    opts.pop("master_cluster_id", None)
    match = _cluster_match(opts)
    assert match("east", opts=opts) is False
    assert match("east,west", opts=opts) is False
    assert match("", opts=opts) is False


def test_whitespace_tolerant_target(single_master):
    """Whitespace around comma-separated names is ignored."""
    cluster = single_master(cluster_id="west")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "west"
    match = _cluster_match(opts)
    assert match("east, west", opts=opts) is True
    assert match(" east , west ", opts=opts) is True
    assert match("\teast,\twest\n", opts=opts) is True


def test_empty_target_string_returns_false(single_master):
    """An empty or whitespace-only target cannot match anything."""
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "east"
    match = _cluster_match(opts)
    assert match("", opts=opts) is False
    assert match("   ", opts=opts) is False
    assert match(",", opts=opts) is False


def test_case_sensitive_cluster_ids(single_master):
    """
    ``cluster_id`` values are lowercase per CLUSTER_ID_RE; the matcher
    does not case-fold the target.  ``EAST`` is not ``east``.
    """
    cluster = single_master(cluster_id="east")
    opts = cluster.masters[0].config.copy()
    opts["cluster_id"] = "east"
    match = _cluster_match(opts)
    assert match("east", opts=opts) is True
    assert match("EAST", opts=opts) is False
    assert match("East", opts=opts) is False
