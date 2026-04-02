"""
Tests for resource-aware targeting in salt.utils.minions.

Covers:
- CkMinions._augment_with_resources(): adds resource IDs to wildcard results
- CkMinions._check_resource_minions(): resolves T@ expressions
- check_minions() wildcard-augmentation conditional logic
"""

import pytest

import salt.utils.minions
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINION_RESOURCES = {
    "minion": {
        "dummy": ["dummy-01", "dummy-02", "dummy-03"],
        "ssh": ["node1", "localhost"],
    }
}


@pytest.fixture
def ck(master_opts):
    """CkMinions instance with a mocked cache."""
    ck = salt.utils.minions.CkMinions(master_opts)
    cache = MagicMock()
    cache.list.return_value = []
    cache.fetch.return_value = {}
    ck.cache = cache
    return ck


@pytest.fixture
def ck_with_resources(ck):
    """CkMinions with minion_resources cache populated."""

    def _list(bank):
        if bank == "minion_resources":
            return list(MINION_RESOURCES.keys())
        return []

    def _fetch(bank, key):
        if bank == "minion_resources":
            return MINION_RESOURCES.get(key, {})
        return {}

    ck.cache.list.side_effect = _list
    ck.cache.fetch.side_effect = _fetch
    return ck


# ---------------------------------------------------------------------------
# _augment_with_resources tests
# ---------------------------------------------------------------------------


def test_augment_with_resources_adds_resource_ids(ck_with_resources):
    """
    When the cache contains resource registrations, augmenting a minion list
    appends every resource ID managed by those minions.
    """
    result = ck_with_resources._augment_with_resources(["minion"])
    assert "minion" in result
    assert "dummy-01" in result
    assert "dummy-02" in result
    assert "dummy-03" in result
    assert "node1" in result
    assert "localhost" in result


def test_augment_with_resources_no_duplication(ck_with_resources):
    """Resource IDs already in the minion list are not added twice."""
    # Pre-populate list with one resource ID that would otherwise be added.
    result = ck_with_resources._augment_with_resources(["minion", "dummy-01"])
    assert result.count("dummy-01") == 1


def test_augment_with_resources_empty_cache(ck):
    """When the cache is empty, the original minion list is returned unchanged."""
    result = ck._augment_with_resources(["minion", "dummy-01"])
    assert result == ["minion", "dummy-01"]


def test_augment_with_resources_unmatched_minion(ck_with_resources):
    """Minions not in the resource cache do not cause errors; others are still augmented."""
    result = ck_with_resources._augment_with_resources(["minion", "unknown-minion"])
    assert "dummy-01" in result
    assert "unknown-minion" in result


# ---------------------------------------------------------------------------
# _check_resource_minions tests
# ---------------------------------------------------------------------------


def test_check_resource_minions_full_srn(ck_with_resources):
    """
    T@dummy:dummy-01 with a populated cache returns the specific resource ID.
    """
    result = ck_with_resources._check_resource_minions("dummy:dummy-01", greedy=True)
    assert "dummy-01" in result["minions"]


def test_check_resource_minions_all_of_type(ck_with_resources):
    """T@dummy (bare type) returns all dummy resource IDs from the cache."""
    result = ck_with_resources._check_resource_minions("dummy", greedy=True)
    ids = set(result["minions"])
    assert {"dummy-01", "dummy-02", "dummy-03"}.issubset(ids)


def test_check_resource_minions_fallback_no_cache(ck):
    """
    When the cache is empty but the expression contains a specific ID, the ID
    is returned directly so targeting still works without cache registration.
    """
    result = ck._check_resource_minions("dummy:dummy-01", greedy=True)
    assert "dummy-01" in result["minions"]


def test_check_resource_minions_empty_cache_bare_type(ck):
    """
    When the cache is empty and the expression is a bare type, an empty
    minions list is returned — there is no ID to derive from the expression.
    """
    result = ck._check_resource_minions("dummy", greedy=True)
    assert result["minions"] == []


# ---------------------------------------------------------------------------
# check_minions wildcard augmentation logic
# ---------------------------------------------------------------------------


def test_check_minions_glob_wildcard_augmented(ck_with_resources):
    """
    check_minions('*', 'glob') must augment the result with resource IDs so
    the master keeps its response window open for resource returns.
    """
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob")

    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_glob_specific_not_augmented(ck_with_resources):
    """
    check_minions('minion', 'glob') must NOT augment with resource IDs.
    Targeting a specific minion by name must not implicitly include its
    resources — the operator asked for the minion, not its resources.
    """
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("minion", tgt_type="glob")

    assert "dummy-01" not in result["minions"]
    assert result["minions"] == ["minion"]


def test_check_minions_compound_not_augmented(ck_with_resources):
    """
    Compound targets are never augmented — T@/M@ handle resource selection
    explicitly within the compound expression.
    """
    with patch.object(
        ck_with_resources,
        "_check_compound_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "minion and G@os:Debian", tgt_type="compound"
        )

    assert "dummy-01" not in result["minions"]
