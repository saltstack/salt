"""
Unit tests for :mod:`salt.matchers.cluster_match`.

These are pure-function tests: no master is spun up and no loader
is involved.  They exercise target-string parsing edge cases and
the opts-fallback matrix.
"""

import pytest

import salt.matchers.cluster_match as cluster_match


@pytest.mark.parametrize(
    "target,cluster_id,expected",
    [
        ("east", "east", True),
        ("east", "west", False),
        ("east,west", "east", True),
        ("east,west", "west", True),
        ("east,west", "north", False),
    ],
)
def test_basic_membership(target, cluster_id, expected):
    opts = {"cluster_id": cluster_id}
    assert cluster_match.match(target, opts=opts) is expected


def test_master_cluster_id_fallback_when_cluster_id_absent():
    opts = {"master_cluster_id": "east"}
    assert cluster_match.match("east", opts=opts) is True
    assert cluster_match.match("west", opts=opts) is False


def test_cluster_id_wins_over_master_cluster_id():
    """
    When both are present (unusual, but possible on a hybrid role),
    the master-side identifier takes precedence.
    """
    opts = {"cluster_id": "east", "master_cluster_id": "west"}
    assert cluster_match.match("east", opts=opts) is True
    assert cluster_match.match("west", opts=opts) is False


def test_empty_cluster_id_falls_back_to_master_cluster_id():
    """An empty string is treated as absent for both fields."""
    opts = {"cluster_id": "", "master_cluster_id": "east"}
    assert cluster_match.match("east", opts=opts) is True


def test_none_cluster_id_falls_back_to_master_cluster_id():
    opts = {"cluster_id": None, "master_cluster_id": "east"}
    assert cluster_match.match("east", opts=opts) is True


def test_both_identifiers_missing_returns_false():
    assert cluster_match.match("east", opts={}) is False
    assert cluster_match.match("east,west", opts={}) is False


def test_both_identifiers_none_returns_false():
    opts = {"cluster_id": None, "master_cluster_id": None}
    assert cluster_match.match("east", opts=opts) is False


def test_empty_target_returns_false():
    opts = {"cluster_id": "east"}
    assert cluster_match.match("", opts=opts) is False


def test_whitespace_only_target_returns_false():
    opts = {"cluster_id": "east"}
    assert cluster_match.match("   ", opts=opts) is False
    assert cluster_match.match("\t\n", opts=opts) is False


def test_only_commas_target_returns_false():
    opts = {"cluster_id": "east"}
    assert cluster_match.match(",", opts=opts) is False
    assert cluster_match.match(",,,", opts=opts) is False
    assert cluster_match.match(" , , ", opts=opts) is False


def test_consecutive_commas_tolerated():
    """Empty tokens between commas are discarded, not matched."""
    opts = {"cluster_id": "east"}
    assert cluster_match.match("east,,west", opts=opts) is True
    assert cluster_match.match("east,,,west", opts=opts) is True
    opts = {"cluster_id": "west"}
    assert cluster_match.match("east,,west", opts=opts) is True


def test_leading_and_trailing_commas_tolerated():
    opts = {"cluster_id": "east"}
    assert cluster_match.match(",east", opts=opts) is True
    assert cluster_match.match("east,", opts=opts) is True
    assert cluster_match.match(",east,", opts=opts) is True
    assert cluster_match.match(",,east,,", opts=opts) is True


def test_whitespace_around_tokens_stripped():
    opts = {"cluster_id": "east"}
    assert cluster_match.match(" east ", opts=opts) is True
    assert cluster_match.match("east, west", opts=opts) is True
    assert cluster_match.match(" east , west ", opts=opts) is True
    assert cluster_match.match("\teast\t,\twest\t", opts=opts) is True


def test_internal_whitespace_in_token_not_stripped():
    """
    Only leading/trailing whitespace per-token is stripped. An
    identifier with embedded whitespace is never a valid cluster_id
    (CLUSTER_ID_RE forbids it) so it must not match.
    """
    opts = {"cluster_id": "east"}
    assert cluster_match.match("ea st", opts=opts) is False
    assert cluster_match.match("east west", opts=opts) is False


def test_deduplicated_targets_still_match():
    """Repeating a target name is a no-op."""
    opts = {"cluster_id": "east"}
    assert cluster_match.match("east,east,east", opts=opts) is True
    assert cluster_match.match("east, east , east", opts=opts) is True


def test_case_sensitive_match():
    opts = {"cluster_id": "east"}
    assert cluster_match.match("east", opts=opts) is True
    assert cluster_match.match("EAST", opts=opts) is False
    assert cluster_match.match("East", opts=opts) is False
    assert cluster_match.match("eAsT", opts=opts) is False


def test_unicode_target_tokens_do_not_crash():
    """Non-ASCII target tokens are tolerated and simply never match."""
    opts = {"cluster_id": "east"}
    assert cluster_match.match("éast", opts=opts) is False
    assert cluster_match.match("east,テスト", opts=opts) is True


def test_unicode_cluster_id_compares_by_equality():
    """
    CLUSTER_ID_RE forbids non-ASCII in practice, but the matcher
    does not re-validate: if a non-ASCII id ends up in opts, exact
    equality still works.
    """
    opts = {"cluster_id": "テスト"}
    assert cluster_match.match("テスト", opts=opts) is True
    assert cluster_match.match("east", opts=opts) is False


@pytest.mark.parametrize("tgt", [None, 0, 1, True, False, 1.5, [], ["east"], ("east",)])
def test_non_string_target_returns_false(tgt):
    """A non-string target is a programmer error, not a match."""
    opts = {"cluster_id": "east"}
    assert cluster_match.match(tgt, opts=opts) is False


def test_opts_none_defaults_to_empty():
    """
    Called with ``opts=None`` outside of a loader context, the
    matcher must not raise and must return False (no identifier
    available).
    """
    assert cluster_match.match("east") is False


def test_minion_id_argument_is_ignored():
    """The minion_id kwarg is accepted for signature parity only."""
    opts = {"cluster_id": "east"}
    assert cluster_match.match("east", opts=opts, minion_id="anything") is True
    assert cluster_match.match("west", opts=opts, minion_id="anything") is False


def test_long_target_list():
    """A long union with many members is handled."""
    opts = {"cluster_id": "cluster42"}
    tgt = ",".join(f"cluster{i}" for i in range(100))
    assert cluster_match.match(tgt, opts=opts) is True
    opts = {"cluster_id": "notthere"}
    assert cluster_match.match(tgt, opts=opts) is False
