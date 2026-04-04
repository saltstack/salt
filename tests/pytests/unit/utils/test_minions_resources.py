"""
Tests for resource-aware targeting in salt.utils.minions.

Covers:
- _build_resource_index(): constructs the flat three-way index
- _get_resource_index(): in-process caching with TTL
- _update_resource_index(): atomic update of index + cache
- CkMinions._augment_with_resources(): adds resource IDs to wildcard results
- CkMinions._check_resource_minions(): resolves T@ expressions
- check_minions() wildcard-augmentation conditional logic
"""

import pytest

import salt.utils.minions
from salt.utils.minions import (
    _MERGE_RESOURCE_FUNS,
    _RESOURCE_INDEX_BANK,
    _RESOURCE_INDEX_KEY,
    _build_resource_index,
    _get_resource_index,
    _update_resource_index,
)
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

FLAT_INDEX = _build_resource_index(MINION_RESOURCES)


@pytest.fixture(autouse=True)
def reset_resource_index():
    """Reset the module-level index before each test."""
    salt.utils.minions._resource_index = {"by_id": {}, "by_type": {}, "by_minion": {}}
    salt.utils.minions._resource_index_ts = 0.0
    yield
    salt.utils.minions._resource_index = {"by_id": {}, "by_type": {}, "by_minion": {}}
    salt.utils.minions._resource_index_ts = 0.0


@pytest.fixture
def mock_cache():
    """A cache mock that returns the flat index."""
    cache = MagicMock()
    cache.fetch.return_value = FLAT_INDEX
    cache.store.return_value = None
    return cache


@pytest.fixture
def empty_cache():
    """A cache mock that returns nothing."""
    cache = MagicMock()
    cache.fetch.return_value = {}
    cache.store.return_value = None
    return cache


@pytest.fixture
def ck(master_opts):
    """CkMinions instance with a mocked cache (empty index)."""
    instance = salt.utils.minions.CkMinions(master_opts)
    instance.cache = MagicMock()
    instance.cache.fetch.return_value = {}
    instance.cache.store.return_value = None
    return instance


@pytest.fixture
def ck_with_resources(master_opts):
    """CkMinions with the flat resource index populated."""
    instance = salt.utils.minions.CkMinions(master_opts)
    instance.cache = MagicMock()
    instance.cache.fetch.return_value = FLAT_INDEX
    instance.cache.store.return_value = None
    return instance


# ---------------------------------------------------------------------------
# _build_resource_index tests
# ---------------------------------------------------------------------------


def test_build_resource_index_by_id():
    index = _build_resource_index(MINION_RESOURCES)
    assert index["by_id"]["dummy-01"] == {"minion": "minion", "type": "dummy"}
    assert index["by_id"]["node1"] == {"minion": "minion", "type": "ssh"}


def test_build_resource_index_by_type():
    index = _build_resource_index(MINION_RESOURCES)
    assert set(index["by_type"]["dummy"]) == {"dummy-01", "dummy-02", "dummy-03"}
    assert set(index["by_type"]["ssh"]) == {"node1", "localhost"}


def test_build_resource_index_by_minion():
    index = _build_resource_index(MINION_RESOURCES)
    assert index["by_minion"]["minion"]["dummy"] == ["dummy-01", "dummy-02", "dummy-03"]


def test_build_resource_index_empty():
    index = _build_resource_index({})
    assert index == {"by_id": {}, "by_type": {}, "by_minion": {}}


# ---------------------------------------------------------------------------
# _get_resource_index tests
# ---------------------------------------------------------------------------


def test_get_resource_index_loads_from_cache(mock_cache):
    index = _get_resource_index(mock_cache)
    mock_cache.fetch.assert_called_once_with(_RESOURCE_INDEX_BANK, _RESOURCE_INDEX_KEY)
    assert index["by_id"]["dummy-01"]["type"] == "dummy"


def test_get_resource_index_caches_in_process(mock_cache):
    _get_resource_index(mock_cache)
    _get_resource_index(mock_cache)
    assert (
        mock_cache.fetch.call_count == 1
    ), "cache.fetch should only be called once within TTL"


def test_get_resource_index_refreshes_after_ttl(mock_cache):
    _get_resource_index(mock_cache)
    salt.utils.minions._resource_index_ts = 0.0  # force TTL expiry
    _get_resource_index(mock_cache)
    assert mock_cache.fetch.call_count == 2


def test_get_resource_index_cache_error_returns_empty():
    bad_cache = MagicMock()
    bad_cache.fetch.side_effect = Exception("cache unavailable")
    index = _get_resource_index(bad_cache)
    assert index == {"by_id": {}, "by_type": {}, "by_minion": {}}


# ---------------------------------------------------------------------------
# _update_resource_index tests
# ---------------------------------------------------------------------------


def test_update_resource_index_adds_minion(mock_cache):
    new_resources = {"dummy": ["dummy-99"]}
    _update_resource_index(mock_cache, "minion-b", new_resources)
    assert "dummy-99" in salt.utils.minions._resource_index["by_id"]
    assert "minion-b" in salt.utils.minions._resource_index["by_minion"]


def test_update_resource_index_removes_minion(mock_cache):
    salt.utils.minions._resource_index = _build_resource_index(MINION_RESOURCES)
    _update_resource_index(mock_cache, "minion", {})
    assert "minion" not in salt.utils.minions._resource_index["by_minion"]
    assert "dummy-01" not in salt.utils.minions._resource_index["by_id"]
    assert "dummy" not in salt.utils.minions._resource_index["by_type"]


def test_update_resource_index_persists_to_cache(mock_cache):
    _update_resource_index(mock_cache, "minion", {"dummy": ["dummy-01"]})
    mock_cache.store.assert_called_once_with(
        _RESOURCE_INDEX_BANK, _RESOURCE_INDEX_KEY, salt.utils.minions._resource_index
    )


def test_update_resource_index_surgical_preserves_other_minions(mock_cache):
    """
    Updating one minion must not disturb other minions' entries — this verifies
    the surgical O(r) update does not rebuild from scratch.
    """
    two_minions = {
        "minion-a": {"dummy": ["dummy-01", "dummy-02"]},
        "minion-b": {"ssh": ["node1"]},
    }
    salt.utils.minions._resource_index = _build_resource_index(two_minions)
    # Update only minion-a, removing dummy-01
    _update_resource_index(mock_cache, "minion-a", {"dummy": ["dummy-02"]})
    index = salt.utils.minions._resource_index
    assert "dummy-01" not in index["by_id"]
    assert "dummy-02" in index["by_id"]
    # minion-b must be untouched
    assert "node1" in index["by_id"]
    assert index["by_id"]["node1"]["minion"] == "minion-b"
    assert "minion-b" in index["by_minion"]


def test_update_resource_index_removes_empty_type(mock_cache):
    """
    When the last resource of a type is removed the by_type entry must be
    deleted entirely, not left as an empty list.
    """
    salt.utils.minions._resource_index = _build_resource_index(
        {"minion": {"ssh": ["node1"]}}
    )
    _update_resource_index(mock_cache, "minion", {})
    assert "ssh" not in salt.utils.minions._resource_index["by_type"]


def test_update_resource_index_partial_type_removal(mock_cache):
    """
    Removing one resource of a type must leave the remaining resources of that
    type intact in by_type.
    """
    salt.utils.minions._resource_index = _build_resource_index(
        {"minion": {"dummy": ["dummy-01", "dummy-02"]}}
    )
    _update_resource_index(mock_cache, "minion", {"dummy": ["dummy-02"]})
    index = salt.utils.minions._resource_index
    assert "dummy-01" not in index["by_type"]["dummy"]
    assert "dummy-02" in index["by_type"]["dummy"]


def test_update_resource_index_no_duplicate_by_type(mock_cache):
    """
    Re-registering the same resources must not produce duplicates in by_type.
    """
    salt.utils.minions._resource_index = _build_resource_index(
        {"minion": {"dummy": ["dummy-01"]}}
    )
    _update_resource_index(mock_cache, "minion", {"dummy": ["dummy-01"]})
    assert salt.utils.minions._resource_index["by_type"]["dummy"].count("dummy-01") == 1


# ---------------------------------------------------------------------------
# _augment_with_resources tests
# ---------------------------------------------------------------------------


def test_augment_with_resources_adds_resource_ids(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["minion"])
    assert "dummy-01" in result
    assert "node1" in result
    assert "minion" in result


def test_augment_with_resources_no_duplication(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["minion"])
    assert result.count("minion") == 1


def test_augment_with_resources_empty_index(ck):
    result = ck._augment_with_resources(["minion"])
    assert result == ["minion"]


def test_augment_with_resources_unmatched_minion(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["other-minion"])
    assert result == ["other-minion"]


def test_augment_with_resources_index_error_returns_minion_ids(ck):
    ck.cache.fetch.side_effect = Exception("cache unavailable")
    result = ck._augment_with_resources(["minion"])
    assert result == ["minion"]


# ---------------------------------------------------------------------------
# _check_resource_minions tests
# ---------------------------------------------------------------------------


def test_check_resource_minions_full_srn(ck_with_resources):
    result = ck_with_resources._check_resource_minions("dummy:dummy-01", greedy=True)
    assert result == {"minions": ["dummy-01"], "missing": []}


def test_check_resource_minions_all_of_type(ck_with_resources):
    result = ck_with_resources._check_resource_minions("dummy", greedy=True)
    assert set(result["minions"]) == {"dummy-01", "dummy-02", "dummy-03"}


def test_check_resource_minions_fallback_no_cache(ck):
    result = ck._check_resource_minions("dummy:dummy-01", greedy=True)
    assert result == {"minions": ["dummy-01"], "missing": []}


def test_check_resource_minions_empty_cache_bare_type(ck):
    result = ck._check_resource_minions("dummy", greedy=True)
    assert result == {"minions": [], "missing": []}


def test_check_resource_minions_trailing_colon(ck_with_resources):
    result = ck_with_resources._check_resource_minions("dummy:", greedy=True)
    assert set(result["minions"]) == {"dummy-01", "dummy-02", "dummy-03"}


# ---------------------------------------------------------------------------
# check_minions integration tests
# ---------------------------------------------------------------------------


def test_check_minions_glob_wildcard_augmented(ck_with_resources):
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob")
    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_glob_specific_not_augmented(ck_with_resources):
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("minion", tgt_type="glob")
    assert "dummy-01" not in result["minions"]


def test_check_minions_compound_not_augmented(ck_with_resources):
    with patch.object(
        ck_with_resources,
        "_check_compound_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "minion and G@os:Debian", tgt_type="compound"
        )
    assert "dummy-01" not in result["minions"]


def test_augment_cache_error_does_not_break_check_minions(ck):
    ck.cache.fetch.side_effect = Exception("cache driver failure")
    with patch.object(
        ck,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck.check_minions("*", tgt_type="glob")
    assert "minion" in result["minions"]


# ---------------------------------------------------------------------------
# check_minions merge-mode conditional tests
# ---------------------------------------------------------------------------


def test_check_minions_merge_fun_skips_augmentation(ck_with_resources):
    """
    When fun is a merge-mode function (e.g. state.apply) a wildcard glob must
    NOT augment the minion list with resource IDs.  Resources are executed
    inline by the managing minion and must not appear as separate job targets.
    """
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "*", tgt_type="glob", fun="state.apply"
        )
    assert "dummy-01" not in result["minions"]
    assert "node1" not in result["minions"]
    assert "minion" in result["minions"]


def test_check_minions_merge_fun_all_merge_funs_skip(ck_with_resources):
    """All functions in _MERGE_RESOURCE_FUNS must skip resource augmentation."""
    for fun in _MERGE_RESOURCE_FUNS:
        with patch.object(
            ck_with_resources,
            "_check_glob_minions",
            return_value={"minions": ["minion"], "missing": []},
        ):
            result = ck_with_resources.check_minions("*", tgt_type="glob", fun=fun)
        assert "dummy-01" not in result["minions"], f"augmented for {fun}"


def test_check_minions_non_merge_fun_still_augments(ck_with_resources):
    """
    A non-merge function such as test.ping with a wildcard glob must still
    receive the full augmented list including resource IDs.
    """
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob", fun="test.ping")
    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_no_fun_still_augments(ck_with_resources):
    """
    Calling check_minions without fun (backward-compatible default None)
    must still augment a wildcard glob — behaviour must be unchanged for
    all existing call sites that do not pass fun.
    """
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob")
    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_merge_fun_compound_not_affected(ck_with_resources):
    """
    The merge-mode skip only applies to wildcard globs.  A compound
    expression is never augmented regardless of fun.
    """
    with patch.object(
        ck_with_resources,
        "_check_compound_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "G@os:Debian", tgt_type="compound", fun="test.ping"
        )
    assert "dummy-01" not in result["minions"]
