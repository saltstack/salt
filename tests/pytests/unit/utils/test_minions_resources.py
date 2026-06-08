"""
Tests for resource-aware targeting in :mod:`salt.utils.minions`.

Covers:

* End-to-end bare-ID targeting — :func:`update_resource_index` then
  :meth:`CkMinions.check_minions` (mirrors master ``_register_resources`` +
  ``salt <resource-id>`` glob/list).
* Concurrent registration vs targeting checks (multi-worker regression guard).

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

import threading

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

# Avoid production-sized primary mmap (~256 MiB) for every test; see
# ``test_resource_registry._TEST_PRIMARY_*``.
_TEST_PRIMARY_CAPACITY = 4096
_TEST_PRIMARY_SLOT_SIZE = 128


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
    master_opts.setdefault("resource_index_primary_capacity", _TEST_PRIMARY_CAPACITY)
    master_opts.setdefault("resource_index_primary_slot_size", _TEST_PRIMARY_SLOT_SIZE)
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


def test_registry_resolve_bare_resource_id(populated_registry):
    assert populated_registry.resolve_bare_resource_id("dummy-02") == [
        ("dummy", "dummy-02")
    ]
    assert populated_registry.resolve_bare_resource_id("nosuch") == []


def test_check_minions_list_includes_bare_registered_resource_id(ck_with_resources):
    """``salt -L <resource-id>`` must resolve via the resource registry."""
    result = ck_with_resources.check_minions("dummy-02", tgt_type="list")
    assert result["minions"] == ["dummy-02"]
    assert result["missing"] == []


def test_check_minions_glob_exact_bare_registered_resource_id(ck_with_resources):
    result = ck_with_resources.check_minions("dummy-02", tgt_type="glob")
    assert "dummy-02" in result["minions"]


def test_check_glob_minions_bare_resource_from_pillar_cache_empty_registry(opts):
    """Bare glob matches cached pillar ``resources`` when mmap registry is cold."""
    opts["minion_data_cache"] = True
    fake_cache = MagicMock()

    def fetch_side_effect(bank, mid):
        if bank == "pillar" and mid == "m2":
            return {"resources": {"dummy": {"resource_ids": ["m2-dummy2"]}}}
        return {}

    fake_cache.list.side_effect = lambda bank: ["m2"]
    fake_cache.fetch.side_effect = fetch_side_effect

    with patch("salt.cache.factory", return_value=fake_cache):
        ck = salt.utils.minions.CkMinions(opts)
        result = ck._check_glob_minions("m2-dummy2", greedy=True)
    assert "m2-dummy2" in result["minions"]


def test_check_glob_minions_bare_resource_from_grains_cache_empty_registry(opts):
    opts["minion_data_cache"] = True
    fake_cache = MagicMock()

    def fetch_side_effect(bank, mid):
        if bank == "grains" and mid == "m2":
            return {"salt_resources": {"dummy": ["m2-dummy2"]}}
        return {}

    fake_cache.list.side_effect = lambda bank: ["m2"]
    fake_cache.fetch.side_effect = fetch_side_effect

    with patch("salt.cache.factory", return_value=fake_cache):
        ck = salt.utils.minions.CkMinions(opts)
        result = ck._check_glob_minions("m2-dummy2", greedy=True)
    assert "m2-dummy2" in result["minions"]


def test_check_list_minions_bare_resource_from_cache_empty_registry(opts):
    opts["minion_data_cache"] = True
    fake_cache = MagicMock()
    fake_cache.list.side_effect = lambda bank: ["m2"]

    def fetch_side_effect(bank, mid):
        if bank == "pillar" and mid == "m2":
            return {"resources": {"dummy": {"resource_ids": ["m2-dummy2"]}}}
        return {}

    fake_cache.fetch.side_effect = fetch_side_effect

    with patch("salt.cache.factory", return_value=fake_cache):
        ck = salt.utils.minions.CkMinions(opts)
        result = ck._check_list_minions("m2-dummy2", greedy=True)
    assert result["minions"] == ["m2-dummy2"]
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# Bare resource ID targeting — master path + concurrency
# ---------------------------------------------------------------------------


def test_update_resource_index_then_check_minions_glob_bare_id(opts):
    """
    Full stack path used by the master after ``_register_resources``: registry
    mmap populated via :func:`update_resource_index`, then glob targeting must
    include the bare resource token (e.g. ``salt m2-dummy2 test.ping``).
    """
    update_resource_index(opts, "minion-2", {"dummy": ["m2-dummy2", "m2-dummy1"]})
    ck = salt.utils.minions.CkMinions(opts)
    got = ck.check_minions("m2-dummy2", tgt_type="glob", fun="test.ping")
    assert "m2-dummy2" in got["minions"]


def test_update_resource_index_then_check_minions_list_bare_id(opts):
    """``salt -L m2-dummy2`` resolves when the id is registered."""
    update_resource_index(opts, "minion-2", {"dummy": ["m2-dummy2"]})
    ck = salt.utils.minions.CkMinions(opts)
    got = ck.check_minions("m2-dummy2", tgt_type="list")
    assert got["minions"] == ["m2-dummy2"]
    assert got["missing"] == []


def test_concurrent_update_resource_index_and_check_minions_glob(opts):
    """
    Several threads alternating writes (as master workers do) with readers that
    evaluate bare-ID glob targets must not raise (mmap ``ACCESS_READ`` vs
    ``ACCESS_WRITE`` races previously blew up here).
    """
    errs = []
    lock = threading.Lock()

    def worker(tag):
        try:
            for i in range(40):
                mid = f"minion-{tag}-{i % 4}"
                rid = f"res-{tag}-{i}"
                update_resource_index(opts, mid, {"dummy": [rid]})
                ck = salt.utils.minions.CkMinions(opts)
                ck.check_minions(rid, tgt_type="glob", fun="test.ping")
                ck.check_minions(rid, tgt_type="list")
        except Exception as exc:  # pylint: disable=broad-except
            with lock:
                errs.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errs, errs


# ---------------------------------------------------------------------------
# _augment_grain_match_with_resource_grains
# ---------------------------------------------------------------------------


def _build_ck_with_resource_grain_cache(opts, entries):
    """
    Build a ``CkMinions`` whose ``self.cache`` returns ``entries`` for the
    ``resource_grains`` bank. Other banks return empty so the standard
    minion-grain match never matches.
    """
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    fake.list = MagicMock(
        side_effect=lambda bank: (
            list(entries.keys()) if bank == "resource_grains" else []
        )
    )
    fake.fetch = MagicMock(
        side_effect=lambda bank, key: (
            entries.get(key) if bank == "resource_grains" else None
        )
    )
    ck.cache = fake
    return ck


def test_augment_grain_match_adds_matched_resource_id(opts):
    """
    A grain expression ``key:value`` that matches a per-resource grain dict
    appends the bare resource id to ``result["minions"]``.
    """
    opts["minion_data_cache"] = True
    entries = {
        "dummy:dummy-01": {"dummy_grain_1": "one", "resource_id": "dummy-01"},
        "dummy:dummy-02": {"dummy_grain_1": "one", "resource_id": "dummy-02"},
        "dummy:other": {"dummy_grain_1": "two", "resource_id": "other"},
    }
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "dummy_grain_1:one", ":", regex_match=False
    )
    assert sorted(result["minions"]) == ["dummy-01", "dummy-02"]


def test_augment_grain_match_dedups_against_existing_minions(opts):
    """An id already in ``result["minions"]`` must not be duplicated."""
    opts["minion_data_cache"] = True
    entries = {"dummy:dummy-01": {"dummy_grain_1": "one"}}
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": ["dummy-01"], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "dummy_grain_1:one", ":", regex_match=False
    )
    assert result["minions"] == ["dummy-01"]


def test_augment_grain_match_skips_when_minion_data_cache_disabled(opts):
    """Disabled :conf_master:`minion_data_cache` short-circuits the augment."""
    opts["minion_data_cache"] = False
    entries = {"dummy:dummy-01": {"dummy_grain_1": "one"}}
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "dummy_grain_1:one", ":", regex_match=False
    )
    assert result["minions"] == []


def test_augment_grain_match_handles_missing_bank(opts):
    """
    When the ``resource_grains`` bank doesn't exist (no minion has registered
    yet), the helper must not raise.
    """
    opts["minion_data_cache"] = True
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    fake.list = MagicMock(side_effect=Exception("bank not found"))
    ck.cache = fake
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "any:thing", ":", regex_match=False
    )
    assert result["minions"] == []


def test_augment_grain_match_pcre_regex_match(opts):
    """Regex form (``salt -P``) must apply ``regex_match=True`` to subdict_match."""
    opts["minion_data_cache"] = True
    entries = {
        "dummy:dummy-01": {"environment": "production-east"},
        "dummy:dummy-02": {"environment": "production-west"},
        "dummy:dummy-03": {"environment": "staging-east"},
    }
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "environment:^production-.*", ":", regex_match=True
    )
    assert sorted(result["minions"]) == ["dummy-01", "dummy-02"]


def test_augment_grain_match_skips_non_dict_entries(opts):
    """A corrupted cache entry that isn't a dict must not crash the helper."""
    opts["minion_data_cache"] = True
    entries = {
        "dummy:dummy-01": "not-a-dict",
        "dummy:dummy-02": {"k": "v"},
    }
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(result, "k:v", ":", regex_match=False)
    assert result["minions"] == ["dummy-02"]


def test_augment_grain_match_invalid_srn_skipped(opts):
    """SRN keys without a ``:`` separator (corrupt or malformed) are skipped."""
    opts["minion_data_cache"] = True
    entries = {
        "no-colon-here": {"k": "v"},
        "dummy:valid": {"k": "v"},
    }
    ck = _build_ck_with_resource_grain_cache(opts, entries)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(result, "k:v", ":", regex_match=False)
    # The "no-colon-here" entry has rid="" after partition → skipped.
    # Wait — partition(":") on "no-colon-here" returns ("no-colon-here", "", "")
    # so rid is empty and the entry is skipped.
    assert result["minions"] == ["valid"]


# ---------------------------------------------------------------------------
# Nodegroup expansion with G@ for resources
# ---------------------------------------------------------------------------


def test_nodegroup_with_grain_term_matches_resources(opts):
    """
    A nodegroup whose definition includes a ``G@`` term must match
    resources via the same augment path. ``_check_compound_minions``
    expands ``N@<group>`` → the underlying compound expression, then
    each ``G@`` term flows through ``_check_grain_minions`` →
    ``_augment_grain_match_with_resource_grains``.

    We verify the wire-up by stuffing a nodegroup definition into opts
    and confirming the resource id reaches the ``minions`` set in the
    result.
    """
    opts["minion_data_cache"] = True
    opts["nodegroups"] = {"prod_nodes": "G@env:prod"}

    update_resource_index(opts, "minion-1", {"dummy": ["dummy-01", "dummy-02"]})

    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    fake.list = MagicMock(
        side_effect=lambda bank: (
            ["dummy:dummy-01", "dummy:dummy-02"] if bank == "resource_grains" else []
        )
    )
    fake.fetch = MagicMock(
        side_effect=lambda bank, key: (
            {
                "dummy:dummy-01": {"env": "prod"},
                "dummy:dummy-02": {"env": "staging"},
            }.get(key)
            if bank == "resource_grains"
            else None
        )
    )
    ck.cache = fake

    got = ck.check_minions("N@prod_nodes", tgt_type="compound", fun="test.ping")
    assert (
        "dummy-01" in got["minions"]
    ), f"Nodegroup compound expansion lost the resource id: {got!r}"
    assert (
        "dummy-02" not in got["minions"]
    ), "Resource not matching the grain expression must not appear"


# ---------------------------------------------------------------------------
# Modest-scale perf: augment over many resources
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
def test_augment_grain_match_handles_thousand_resources_in_under_a_second(opts):
    """
    Sanity-check the ``-G`` augment path under a realistic resource count.
    1000 resource_grains entries × one grain key must scan and match in
    well under a second on commodity hardware. This isn't a strict perf
    contract — it's a regression guard that catches accidental O(N²) or
    per-fetch-per-key blow-ups in the hot read path.
    """
    import time

    opts["minion_data_cache"] = True

    n = 1000
    entries = {
        f"dummy:r{i:04d}": {"env": "prod" if i % 2 else "staging"} for i in range(n)
    }
    # Match half the entries (env:prod for odd indices).
    expected_match_count = n // 2

    fake = MagicMock()
    fake.list = MagicMock(
        side_effect=lambda bank: (
            list(entries.keys()) if bank == "resource_grains" else []
        )
    )
    fake.fetch = MagicMock(
        side_effect=lambda bank, key: (
            entries.get(key) if bank == "resource_grains" else None
        )
    )
    ck = salt.utils.minions.CkMinions(opts)
    ck.cache = fake

    result = {"minions": [], "missing": []}
    start = time.perf_counter()
    ck._augment_grain_match_with_resource_grains(
        result, "env:prod", ":", regex_match=False
    )
    elapsed = time.perf_counter() - start

    assert (
        len(result["minions"]) == expected_match_count
    ), f"Expected {expected_match_count} matches, got {len(result['minions'])}"
    # Generous budget — a 5× overshoot still indicates accidental
    # quadratic scanning. Local dev runs comfortably finish in < 50 ms.
    assert elapsed < 1.0, (
        f"_augment_grain_match_with_resource_grains over {n} entries "
        f"took {elapsed:.3f}s — likely a perf regression"
    )


def _run_check_minions_grain_perf(opts, minion_count, resources_per_minion, budget):
    """
    Drive :meth:`CkMinions.check_minions` against a synthetic fleet of
    ``minion_count`` minions × ``resources_per_minion`` resources and return
    the elapsed wall-clock seconds. Half of each population is tagged
    ``env=prod`` so a ``-G env:prod`` query matches exactly half of both.
    """
    import time

    opts["minion_data_cache"] = True

    minion_ids = [f"minion-{i:06d}" for i in range(minion_count)]
    minion_grains = {
        mid: {"env": "prod" if idx % 2 == 0 else "staging", "os": "Linux"}
        for idx, mid in enumerate(minion_ids)
    }
    resource_grains = {}
    for m_idx, mid in enumerate(minion_ids):
        for r_idx in range(resources_per_minion):
            srn = f"dummy:r-{m_idx:06d}-{r_idx:04d}"
            resource_grains[srn] = {
                "env": "prod" if r_idx % 2 == 0 else "staging",
                "managed_by": mid,
            }

    expected_minions = sum(1 for g in minion_grains.values() if g["env"] == "prod")
    expected_resources = sum(1 for g in resource_grains.values() if g["env"] == "prod")

    fake = MagicMock()

    def _list(bank):
        if bank == "grains":
            return list(minion_grains)
        if bank == "resource_grains":
            return list(resource_grains)
        return []

    def _fetch(bank, key):
        if bank == "grains":
            return minion_grains.get(key)
        if bank == "resource_grains":
            return resource_grains.get(key)
        return None

    fake.list = MagicMock(side_effect=_list)
    fake.fetch = MagicMock(side_effect=_fetch)

    ck = salt.utils.minions.CkMinions(opts)
    ck.cache = fake
    # Bypass PKI listing — we are exercising cache-driven grain matching only.
    with patch.object(ck, "_pki_minions", return_value=set(minion_ids)):
        start = time.perf_counter()
        result = ck.check_minions("env:prod", tgt_type="grain")
        elapsed = time.perf_counter() - start

    matched = result["minions"]
    matched_minions = [m for m in matched if m in minion_grains]
    matched_resources = [m for m in matched if m not in minion_grains]

    msg = (
        f"\n[perf] check_minions(-G env:prod) over "
        f"{minion_count} minions × {resources_per_minion} resources "
        f"({len(resource_grains)} resource_grains entries): "
        f"{elapsed * 1000:.1f} ms — matched "
        f"{len(matched_minions)} minions + {len(matched_resources)} resources"
    )
    # Always surface the timing on stdout so ``pytest -s`` shows it; the
    # assertion failure path also embeds it for ``-v`` inspection.
    print(msg)

    assert len(matched_minions) == expected_minions, (
        f"expected {expected_minions} minions matched, got "
        f"{len(matched_minions)}: {sorted(matched_minions)[:5]}…"
    )
    assert len(matched_resources) == expected_resources, (
        f"expected {expected_resources} resources matched, got "
        f"{len(matched_resources)}"
    )
    assert elapsed < budget, msg
    return elapsed


@pytest.mark.slow_test
def test_check_minions_grain_target_100_minions_100_resources_each(opts):
    """
    End-to-end :meth:`CkMinions.check_minions` timing for grain targeting:
    100 minions × 100 resources (10,000 entries) — small fleet baseline.
    A ``-G env:prod`` query matches 50 minions + 5,000 resource IDs.
    """
    # Local dev finishes in ~75 ms; CI ARM/FIPS ~3-5x slower; 5 s leaves
    # headroom while still catching an accidental O(N²) regression.
    _run_check_minions_grain_perf(opts, 100, 100, budget=5.0)


@pytest.mark.slow_test
def test_check_minions_grain_target_1000_minions_100_resources_each(opts):
    """
    End-to-end :meth:`CkMinions.check_minions` timing for grain targeting:
    1,000 minions × 100 resources (100,000 entries) — large-fleet stress.
    A ``-G env:prod`` query matches 500 minions + 50,000 resource IDs.
    """
    _run_check_minions_grain_perf(opts, 1000, 100, budget=30.0)


@pytest.mark.slow_test
@pytest.mark.timeout(240, func_only=True)
def test_check_minions_grain_target_10000_minions_100_resources_each(opts):
    """
    End-to-end :meth:`CkMinions.check_minions` timing for grain targeting:
    10,000 minions × 100 resources (1,000,000 entries) — million-resource
    stress test for the in-process scan path.
    A ``-G env:prod`` query matches 5,000 minions + 500,000 resource IDs.

    Carries an explicit ``@pytest.mark.timeout(240)`` override.  The
    global default applied by ``tests/conftest.py`` is 90 s, but the
    in-test ``budget=180.0`` allows the call itself to run that long
    under coverage tracing on a loaded GHA runner.  Without this
    override the global 90 s wall-clock fires before the test's own
    budget assertion has a chance to evaluate, masking real
    slowdowns as "timeout" failures.
    """
    _run_check_minions_grain_perf(opts, 10000, 100, budget=180.0)
