"""
Tests for resource-aware targeting in :mod:`salt.utils.minions`.

Covers:

* :func:`salt.utils.minions.resource_index_srn_key` — canonical SRN keys.
* :func:`salt.utils.minions._build_resource_index` /
  :func:`salt.utils.minions._coerce_resource_index_schema` — pure utilities
  used by migration scripts and test fixtures.
* :func:`salt.utils.minions.update_resource_index` — the master-side
  register-a-minion shim over
  :class:`salt.utils.resource_registry.ResourceRegistry`.
* :meth:`CkMinions._check_resource_minions` — T@ expression resolution.
* :meth:`CkMinions._augment_with_resources` — wildcard glob augmentation.
* :meth:`CkMinions.check_minions` merge-mode conditional logic.

The registry is an mmap-backed singleton shared per-process. Tests use
:func:`salt.utils.resource_registry.reset_registry` to get a fresh
per-``cachedir`` instance.
"""

import pytest

import salt.utils.minions
import salt.utils.resource_registry
from salt.utils.minions import (
    _MERGE_RESOURCE_FUNS,
    RESOURCE_INDEX_SCHEMA_VERSION,
    _build_resource_index,
    _coerce_resource_index_schema,
    resource_index_srn_key,
    update_resource_index,
)
from tests.support.mock import patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


MINION_RESOURCES = {
    "minion": {
        "dummy": ["dummy-01", "dummy-02", "dummy-03"],
        "ssh": ["node1", "localhost"],
    }
}


@pytest.fixture(autouse=True)
def reset_registry_singleton():
    """Drop the process-wide registry before and after each test."""
    salt.utils.resource_registry.reset_registry()
    yield
    salt.utils.resource_registry.reset_registry()


@pytest.fixture
def opts(master_opts, tmp_path):
    """Master opts pointing at a per-test tmp cachedir."""
    master_opts["cachedir"] = str(tmp_path)
    return master_opts


@pytest.fixture
def registry(opts):
    """A fresh ResourceRegistry anchored on ``opts['cachedir']``."""
    return salt.utils.resource_registry.get_registry(opts)


@pytest.fixture
def populated_registry(opts):
    """Registry pre-populated with :data:`MINION_RESOURCES`."""
    reg = salt.utils.resource_registry.get_registry(opts)
    for minion_id, resources in MINION_RESOURCES.items():
        reg.register_minion(minion_id, resources)
    return reg


@pytest.fixture
def ck(opts):
    """CkMinions bound to the empty per-test registry."""
    return salt.utils.minions.CkMinions(opts)


@pytest.fixture
def ck_with_resources(opts, populated_registry):
    """CkMinions with :data:`MINION_RESOURCES` pre-registered."""
    return salt.utils.minions.CkMinions(opts)


# ---------------------------------------------------------------------------
# Pure utility helpers
# ---------------------------------------------------------------------------


def test_resource_index_srn_key():
    assert resource_index_srn_key("dummy", "x") == "dummy:x"


def test_build_resource_index_by_id():
    index = _build_resource_index(MINION_RESOURCES)
    assert index["by_id"]["dummy:dummy-01"] == {"minion": "minion", "type": "dummy"}
    assert index["by_id"]["ssh:node1"] == {"minion": "minion", "type": "ssh"}


def test_build_resource_index_by_type():
    index = _build_resource_index(MINION_RESOURCES)
    assert set(index["by_type"]["dummy"]) == {"dummy-01", "dummy-02", "dummy-03"}
    assert set(index["by_type"]["ssh"]) == {"node1", "localhost"}


def test_build_resource_index_by_minion():
    index = _build_resource_index(MINION_RESOURCES)
    assert index["by_minion"]["minion"]["dummy"] == [
        "dummy-01",
        "dummy-02",
        "dummy-03",
    ]


def test_build_resource_index_empty():
    index = _build_resource_index({})
    assert index["schema_version"] == RESOURCE_INDEX_SCHEMA_VERSION
    assert index["by_id"] == {}
    assert index["by_type"] == {}
    assert index["by_minion"] == {}


def test_coerce_resource_index_schema_legacy_rebuilds_by_id():
    legacy = {
        "by_minion": {
            "m1": {"ssh": ["n1"], "dummy": ["n1"]},
        },
        "by_type": {"ssh": ["n1"], "dummy": ["n1"]},
        "by_id": {"n1": {"minion": "m1", "type": "ssh"}},
    }
    coerced = _coerce_resource_index_schema(legacy)
    assert coerced["schema_version"] == 2
    assert coerced["by_id"]["ssh:n1"]["type"] == "ssh"
    assert coerced["by_id"]["dummy:n1"]["type"] == "dummy"


# ---------------------------------------------------------------------------
# update_resource_index — the master-side register-a-minion shim
# ---------------------------------------------------------------------------


def test_update_resource_index_adds_minion(opts):
    update_resource_index(opts, "minion-b", {"dummy": ["dummy-99"]})
    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.has_resource("minion-b", "dummy", "dummy-99")
    assert reg.get_resources_for_minion("minion-b") == {"dummy": ["dummy-99"]}


def test_update_resource_index_removes_minion(opts):
    update_resource_index(opts, "minion", MINION_RESOURCES["minion"])
    update_resource_index(opts, "minion", {})
    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.get_resources_for_minion("minion") == {}
    assert reg.get_resource_ids_by_type("dummy") == []


def test_update_resource_index_surgical_preserves_other_minions(opts):
    update_resource_index(opts, "minion-a", {"dummy": ["dummy-01", "dummy-02"]})
    update_resource_index(opts, "minion-b", {"ssh": ["node1"]})
    update_resource_index(opts, "minion-a", {"dummy": ["dummy-02"]})

    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.has_resource("minion-b", "ssh", "node1")
    assert reg.has_resource("minion-a", "dummy", "dummy-02")
    assert not reg.has_srn("dummy", "dummy-01")


def test_update_resource_index_removes_empty_type(opts):
    update_resource_index(opts, "minion", {"ssh": ["node1"]})
    update_resource_index(opts, "minion", {})
    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.get_resource_ids_by_type("ssh") == []


def test_update_resource_index_partial_type_removal(opts):
    update_resource_index(opts, "minion", {"dummy": ["dummy-01", "dummy-02"]})
    update_resource_index(opts, "minion", {"dummy": ["dummy-02"]})
    reg = salt.utils.resource_registry.get_registry(opts)
    rids = reg.get_resource_ids_by_type("dummy")
    assert set(rids) == {"dummy-02"}


def test_update_resource_index_no_duplicate_by_type(opts):
    update_resource_index(opts, "minion", {"dummy": ["dummy-01"]})
    update_resource_index(opts, "minion", {"dummy": ["dummy-01"]})
    reg = salt.utils.resource_registry.get_registry(opts)
    rids = reg.get_resource_ids_by_type("dummy")
    assert rids.count("dummy-01") == 1


def test_update_resource_index_handles_none_resources(opts):
    """A minion reporting ``resources: None`` must not crash — treat as empty."""
    update_resource_index(opts, "minion", {"dummy": ["dummy-01"]})
    update_resource_index(opts, "minion", None)
    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.get_resources_for_minion("minion") == {}


def test_update_resource_index_registry_error_is_swallowed(opts):
    """A registry write failure must not blow up the master's handler."""
    with patch.object(
        salt.utils.resource_registry.ResourceRegistry,
        "register_minion",
        side_effect=RuntimeError("registry down"),
    ):
        # Returns (0, 0) rather than raising.
        result = update_resource_index(opts, "m", {"dummy": ["d"]})
    assert result == (0, 0)


# ---------------------------------------------------------------------------
# Composite (type, id) — same bare id under multiple resource types
# ---------------------------------------------------------------------------


SHARED_ID = "shared-01"
DUPLICATE_BARE_ID_RESOURCES = {
    "minion-a": {
        "dummy": [SHARED_ID],
        "ssh": [SHARED_ID],
    },
}


def test_build_resource_index_duplicate_bare_id_two_types():
    """by_id must keep one entry per (type, id), not collapse on bare id."""
    index = _build_resource_index(DUPLICATE_BARE_ID_RESOURCES)
    assert index["by_id"][resource_index_srn_key("dummy", SHARED_ID)] == {
        "minion": "minion-a",
        "type": "dummy",
    }
    assert index["by_id"][resource_index_srn_key("ssh", SHARED_ID)] == {
        "minion": "minion-a",
        "type": "ssh",
    }
    assert set(index["by_type"]["dummy"]) == {SHARED_ID}
    assert set(index["by_type"]["ssh"]) == {SHARED_ID}


def test_update_resource_index_shared_bare_id_two_types(opts):
    update_resource_index(opts, "minion-a", DUPLICATE_BARE_ID_RESOURCES["minion-a"])
    reg = salt.utils.resource_registry.get_registry(opts)
    assert reg.has_resource("minion-a", "dummy", SHARED_ID)
    assert reg.has_resource("minion-a", "ssh", SHARED_ID)

    # Drop only the ssh entry — dummy must be untouched.
    update_resource_index(opts, "minion-a", {"dummy": [SHARED_ID]})
    assert reg.has_resource("minion-a", "dummy", SHARED_ID)
    assert not reg.has_srn("ssh", SHARED_ID)


# ---------------------------------------------------------------------------
# CkMinions._check_resource_minions — T@ resolution
# ---------------------------------------------------------------------------


def test_check_resource_minions_full_srn(ck_with_resources):
    result = ck_with_resources._check_resource_minions("dummy:dummy-01", greedy=True)
    assert result == {"minions": ["dummy-01"], "missing": []}


def test_check_resource_minions_all_of_type(ck_with_resources):
    result = ck_with_resources._check_resource_minions("dummy", greedy=True)
    assert set(result["minions"]) == {"dummy-01", "dummy-02", "dummy-03"}


def test_check_resource_minions_fallback_unknown_srn(ck):
    """Unregistered SRNs echo back the resource ID (managing minion filters locally)."""
    result = ck._check_resource_minions("dummy:dummy-01", greedy=True)
    assert result == {"minions": ["dummy-01"], "missing": []}


def test_check_resource_minions_empty_registry_bare_type(ck):
    result = ck._check_resource_minions("dummy", greedy=True)
    assert result == {"minions": [], "missing": []}


def test_check_resource_minions_trailing_colon(ck_with_resources):
    """A trailing colon (``dummy:``) must be treated as a bare-type expression."""
    result = ck_with_resources._check_resource_minions("dummy:", greedy=True)
    assert set(result["minions"]) == {"dummy-01", "dummy-02", "dummy-03"}


def test_check_resource_minions_full_srn_per_type_with_duplicate_bare_id(opts):
    update_resource_index(opts, "minion-a", DUPLICATE_BARE_ID_RESOURCES["minion-a"])
    ck = salt.utils.minions.CkMinions(opts)

    assert ck._check_resource_minions(f"dummy:{SHARED_ID}", greedy=True) == {
        "minions": [SHARED_ID],
        "missing": [],
    }
    assert ck._check_resource_minions(f"ssh:{SHARED_ID}", greedy=True) == {
        "minions": [SHARED_ID],
        "missing": [],
    }


def test_check_resource_minions_registry_error_returns_empty(ck):
    with patch.object(ck.registry, "has_srn", side_effect=RuntimeError("boom")):
        result = ck._check_resource_minions("dummy:dummy-01", greedy=True)
    # SRN path echoes back the id even when the lookup fails.
    assert result == {"minions": ["dummy-01"], "missing": []}


# ---------------------------------------------------------------------------
# CkMinions._augment_with_resources — wildcard glob augmentation
# ---------------------------------------------------------------------------


def test_augment_with_resources_adds_resource_ids(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["minion"])
    assert "dummy-01" in result
    assert "node1" in result
    assert "minion" in result


def test_augment_with_resources_no_duplication(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["minion"])
    assert result.count("minion") == 1


def test_augment_with_resources_empty_registry(ck):
    result = ck._augment_with_resources(["minion"])
    assert result == ["minion"]


def test_augment_with_resources_unmatched_minion(ck_with_resources):
    result = ck_with_resources._augment_with_resources(["other-minion"])
    assert result == ["other-minion"]


def test_augment_with_resources_registry_error_returns_minion_ids(ck):
    with patch.object(
        ck.registry,
        "get_resources_for_minion",
        side_effect=RuntimeError("registry unavailable"),
    ):
        result = ck._augment_with_resources(["minion"])
    assert result == ["minion"]


# ---------------------------------------------------------------------------
# check_minions — integration with augmentation + merge-mode conditional
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


def test_augment_registry_error_does_not_break_check_minions(ck):
    with patch.object(
        ck.registry,
        "get_resources_for_minion",
        side_effect=RuntimeError("registry failure"),
    ), patch.object(
        ck,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck.check_minions("*", tgt_type="glob")
    assert "minion" in result["minions"]


def test_check_minions_merge_fun_skips_augmentation(ck_with_resources):
    """Merge-mode wildcard globs (e.g. state.apply) must NOT augment with rids."""
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
    for fun in _MERGE_RESOURCE_FUNS:
        with patch.object(
            ck_with_resources,
            "_check_glob_minions",
            return_value={"minions": ["minion"], "missing": []},
        ):
            result = ck_with_resources.check_minions("*", tgt_type="glob", fun=fun)
        assert "dummy-01" not in result["minions"], f"augmented for {fun}"


def test_check_minions_list_fun_still_augments(ck_with_resources):
    """Multifunction jobs pass ``fun`` as a list: must not TypeError."""
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "*", tgt_type="glob", fun=["test.arg", "test.arg"]
        )
    assert "dummy-01" in result["minions"]
    assert "minion" in result["minions"]


def test_check_minions_non_merge_fun_still_augments(ck_with_resources):
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob", fun="test.ping")
    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_no_fun_still_augments(ck_with_resources):
    with patch.object(
        ck_with_resources,
        "_check_glob_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions("*", tgt_type="glob")
    assert "dummy-01" in result["minions"]
    assert "node1" in result["minions"]


def test_check_minions_merge_fun_compound_not_affected(ck_with_resources):
    """The merge-mode skip only applies to wildcard globs, not compound targets."""
    with patch.object(
        ck_with_resources,
        "_check_compound_minions",
        return_value={"minions": ["minion"], "missing": []},
    ):
        result = ck_with_resources.check_minions(
            "G@os:Debian", tgt_type="compound", fun="test.ping"
        )
    assert "dummy-01" not in result["minions"]
