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
# _augment_grain_match_with_resource_grains — literal resource_id fast path
# (exact-key hash probe: ``self.cache.contains(bank, "<rtype>:<literal>")``)
# ---------------------------------------------------------------------------


def _build_ck_with_contains(opts, present_keys, list_result=None):
    """
    Build a ``CkMinions`` whose ``self.cache`` answers:

    * ``contains(bank, key)`` → ``key in present_keys`` for the
      ``resource_grains`` bank; ``False`` for everything else.
    * ``list(bank)`` → ``list_result`` (defaults to the keys in
      ``present_keys``) so the fallback slow path works if the
      literal fast path is NOT taken.

    Returns ``(ck, fake_cache)`` so tests can introspect call counts.
    """
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    keys = list(present_keys)

    def _contains(bank, key):
        if bank != "resource_grains":
            return False
        return key in present_keys

    def _list(bank):
        if bank != "resource_grains":
            return []
        return list(keys if list_result is None else list_result)

    def _fetch(bank, key):
        if bank != "resource_grains":
            return None
        gd = present_keys.get(key) if isinstance(present_keys, dict) else None
        return gd

    fake.contains = MagicMock(side_effect=_contains)
    fake.list = MagicMock(side_effect=_list)
    fake.fetch = MagicMock(side_effect=_fetch)
    ck.cache = fake
    return ck, fake


def test_augment_grain_literal_resource_id_hits_via_contains_probe(opts):
    """
    Literal ``resource_id:<id>`` with a single configured type must probe
    exactly ``cache.contains("resource_grains", "<rtype>:<literal>")`` and
    return the bare id. Crucially, ``cache.list`` must NOT be called -- the
    probe is authoritative and avoids the O(bank-size) scan.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {"dummy:dummy-01": {"resource_id": "dummy-01"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:dummy-01", ":", regex_match=False
    )

    assert result["minions"] == ["dummy-01"]
    # Exactly one probe (T == 1); no bank list / fetch on the fast path.
    assert fake.contains.call_count == 1
    fake.contains.assert_called_with("resource_grains", "dummy:dummy-01")
    assert fake.list.call_count == 0
    assert fake.fetch.call_count == 0


def test_augment_grain_literal_resource_id_miss_probes_every_type(opts):
    """
    Literal predicate against an id that is not registered under any
    configured type returns no match -- and we probe each configured type
    exactly once (``T`` probes total, no fall-through to the scan).
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy", "ssh", "aws"]
    ck, fake = _build_ck_with_contains(opts, present_keys={})

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:nosuch", ":", regex_match=False
    )

    assert result["minions"] == []
    assert fake.contains.call_count == 3
    probed = [c.args[1] for c in fake.contains.call_args_list]
    assert set(probed) == {"dummy:nosuch", "ssh:nosuch", "aws:nosuch"}
    # No fall-through to the scan: the probe is authoritative.
    assert fake.list.call_count == 0
    assert fake.fetch.call_count == 0


def test_augment_grain_literal_resource_id_matches_second_type(opts):
    """
    Multiple configured types; id is registered under exactly one. The
    probe short-circuits on the first hit -- we may make up to T probes
    in the worst case, and the matching id is appended once.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy", "ssh"]
    # Only registered under ssh, not dummy.
    present = {"ssh:node-42": {"resource_id": "node-42"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:node-42", ":", regex_match=False
    )

    assert result["minions"] == ["node-42"]
    # Probe order is enabled_resource_types order: dummy (miss) then ssh (hit).
    probed = [c.args[1] for c in fake.contains.call_args_list]
    assert probed == ["dummy:node-42", "ssh:node-42"]
    assert fake.list.call_count == 0


def test_augment_grain_glob_resource_id_falls_through_to_scan_fast_path(opts):
    """
    ``resource_id:a-dummy-*`` has a wildcard, so the literal fast path
    must fall through and the existing bank-scan fast path (via
    :func:`_resource_id_candidates`) handles it instead. No
    ``cache.contains`` calls expected.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {
        "dummy:a-dummy-01": {"resource_id": "a-dummy-01"},
        "dummy:a-dummy-02": {"resource_id": "a-dummy-02"},
        "dummy:other": {"resource_id": "other"},
    }
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-dummy-*", ":", regex_match=False
    )

    assert sorted(result["minions"]) == ["a-dummy-01", "a-dummy-02"]
    # Fast path for globs is bank-list-based, not contains-probe-based.
    assert fake.contains.call_count == 0
    assert fake.list.call_count >= 1


def test_augment_grain_nested_resource_id_predicate_falls_through(opts):
    """
    ``resource_id:a:b`` is a nested predicate -- the fast path must NOT
    swallow it. Falls through to the slow path (which rejects it via
    :func:`_resource_id_candidates` as well, then does the full scan).
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {"dummy:a": {"resource_id": "a"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a:b", ":", regex_match=False
    )

    # Nested predicates never hit the hash-probe fast path.
    assert fake.contains.call_count == 0
    # No match either way: "resource_id" value in the grain dict is "a",
    # which does not nest-match "resource_id:a:b".
    assert result["minions"] == []


def test_augment_grain_non_resource_id_predicate_falls_through(opts):
    """
    A grain target with a different key (e.g. ``role:web``) must not
    trigger the literal-probe fast path. It falls through to the
    existing slow path (bank list + per-key fetch + subdict_match).
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {
        "dummy:d-1": {"role": "web", "resource_id": "d-1"},
        "dummy:d-2": {"role": "db", "resource_id": "d-2"},
    }
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "role:web", ":", regex_match=False
    )

    assert result["minions"] == ["d-1"]
    assert fake.contains.call_count == 0
    # Slow path: list + fetch per key.
    assert fake.list.call_count >= 1
    assert fake.fetch.call_count >= 1


def test_augment_grain_empty_resource_id_predicate_falls_through(opts):
    """
    ``resource_id:`` with an empty pattern must not take the fast path
    (empty literal would probe ``<rtype>:`` which is never a valid
    bank key). Falls through to the existing behaviour.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {"dummy:x": {"resource_id": "x"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:", ":", regex_match=False
    )

    assert fake.contains.call_count == 0
    # No bare match for the empty pattern.
    assert result["minions"] == []


def test_augment_grain_literal_regex_predicate_does_not_take_fast_path(opts):
    """
    PCRE form (``salt -P resource_id:^d``) must bypass the literal-exact
    probe -- regex match semantics are not identity-equal to the literal
    bank-key test. Falls through to the existing regex-aware scan.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {
        "dummy:d-1": {"resource_id": "d-1"},
        "dummy:x-1": {"resource_id": "x-1"},
    }
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    # "d-1" is a valid regex (treated as literal by re.search anyway) but
    # the fast path MUST NOT trigger when ``regex_match=True``.
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:d-1", ":", regex_match=True
    )

    assert fake.contains.call_count == 0
    assert result["minions"] == ["d-1"]


def test_augment_grain_literal_no_configured_types_returns_empty(opts):
    """
    Edge case: ``opts["resource_types"]`` missing / empty → the fast path
    makes zero probes and returns no match. No fall-through to the scan.
    """
    opts["minion_data_cache"] = True
    opts.pop("resource_types", None)
    present = {"dummy:dummy-01": {"resource_id": "dummy-01"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:dummy-01", ":", regex_match=False
    )

    assert result["minions"] == []
    assert fake.contains.call_count == 0
    # Probe path is authoritative -- the scan must NOT run as a backstop.
    assert fake.list.call_count == 0


def test_augment_grain_literal_contains_raises_is_swallowed(opts):
    """
    If the cache driver raises on ``contains`` for one type, we continue
    to the next type rather than crashing the resolver. A subsequent hit
    still returns the id.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy", "ssh"]
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()

    def _contains(bank, key):
        if key == "dummy:x":
            raise RuntimeError("driver glitch")
        return key == "ssh:x"

    fake.contains = MagicMock(side_effect=_contains)
    fake.list = MagicMock(return_value=[])
    fake.fetch = MagicMock(return_value=None)
    ck.cache = fake

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:x", ":", regex_match=False
    )

    assert result["minions"] == ["x"]
    assert fake.contains.call_count == 2


def test_augment_grain_literal_enabled_types_raises_is_swallowed(opts):
    """
    A failure in ``enabled_resource_types`` must not propagate -- the
    fast path treats it as "zero configured types" and returns empty.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {"dummy:dummy-01": {"resource_id": "dummy-01"}}
    ck, fake = _build_ck_with_contains(opts, present)

    result = {"minions": [], "missing": []}
    with patch(
        "salt.utils.resources.enabled_resource_types",
        side_effect=RuntimeError("opts corrupt"),
    ):
        ck._augment_grain_match_with_resource_grains(
            result, "resource_id:dummy-01", ":", regex_match=False
        )

    assert result["minions"] == []
    assert fake.contains.call_count == 0


def test_is_literal_glob_helper_shapes():
    """Sanity check for the exported shape helpers."""
    from salt.utils.minions import _is_literal_glob, _is_resource_id_literal_predicate

    assert _is_literal_glob("abc") is True
    assert _is_literal_glob("a-dummy-0000100") is True
    assert _is_literal_glob("a*") is False
    assert _is_literal_glob("a?") is False
    assert _is_literal_glob("a[0-9]") is False
    assert _is_literal_glob("") is False
    assert _is_literal_glob(None) is False

    assert _is_resource_id_literal_predicate("resource_id:dummy-01", ":") is True
    assert _is_resource_id_literal_predicate("resource_id:a-*", ":") is False
    assert _is_resource_id_literal_predicate("resource_id:a:b", ":") is False
    assert _is_resource_id_literal_predicate("resource_id:", ":") is False
    assert _is_resource_id_literal_predicate("role:web", ":") is False
    assert _is_resource_id_literal_predicate("", ":") is False
    assert _is_resource_id_literal_predicate(None, ":") is False


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


# ---------------------------------------------------------------------------
# Mission 2: sorted-key cache for ``resource_id:<glob>`` with a fixed prefix
#
# The query planner must route ``resource_id:<prefix>*`` style predicates
# through a sorted-key cache that bounds the scan via binary search on the
# fixed prefix. Behavioural contract tests -- no reliance on the internal
# planner entry point beyond the ``_augment_grain_match_with_resource_grains``
# public surface.
# ---------------------------------------------------------------------------


_gtc = pytest.importorskip(
    "salt.utils.grain_target_cache",
    reason="Mission 2 sorted-key cache module not yet landed",
)


def _build_ck_with_keys(opts, keys):
    """
    Build a ``CkMinions`` whose ``self.cache`` returns ``keys`` from
    ``list("resource_grains")`` and nothing from other banks. Grain
    dicts for each key are synthesised on the fly so a slow-path
    fallback still produces correct matches (the ``resource_id`` grain
    is derived from the SRN).

    Returns ``(ck, fake_cache)`` so tests can inspect the mock.
    """
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    present = list(keys)

    def _list(bank):
        return list(present) if bank == "resource_grains" else []

    def _fetch(bank, key):
        if bank != "resource_grains":
            return None
        _rtype, _, rid = key.partition(":")
        if not rid:
            return None
        return {"resource_id": rid}

    def _contains(bank, key):
        if bank != "resource_grains":
            return False
        return key in present

    fake.list = MagicMock(side_effect=_list)
    fake.fetch = MagicMock(side_effect=_fetch)
    fake.contains = MagicMock(side_effect=_contains)
    ck.cache = fake
    return ck, fake


def _rids(result):
    return sorted(result["minions"])


def test_augment_grain_resource_id_fixed_prefix_matches_only_prefix_keys(opts):
    """
    ``resource_id:a-*`` against a bank with ``a-foo``, ``a-bar``,
    ``b-baz`` must return exactly ``a-foo`` and ``a-bar``. This is the
    behavioural contract regardless of whether the implementation used
    the sorted-key fast path or fell through to the existing scan.
    """
    opts["minion_data_cache"] = True
    ck, _fake = _build_ck_with_keys(opts, ["dummy:a-foo", "dummy:a-bar", "dummy:b-baz"])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-*", ":", regex_match=False
    )
    assert _rids(result) == ["a-bar", "a-foo"]


def test_augment_grain_resource_id_fixed_prefix_bounds_fnmatch_calls(opts, tmp_path):
    """
    With a sorted-key cache on a 10K-key bank, a ``resource_id:a-*``
    query must not run ``fnmatch`` against every key. We bound the
    call count to roughly (matches + a small number of binary-search
    probes). A linear scan would hit all 10,000 keys.
    """
    import fnmatch

    import salt.utils.grain_target_cache as _gtc_mod

    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    bank_dir = tmp_path / "resource_grains"
    bank_dir.mkdir()
    cachedir = str(tmp_path)

    # 10,000 keys; prefix ``a-`` matches 100 of them (indices 0..99).
    keys = [f"dummy:a-{i:03d}" for i in range(100)]
    keys += [f"dummy:b-{i:04d}" for i in range(9900)]
    ck, fake = _build_ck_with_keys(opts, keys)
    fake.cachedir = cachedir
    _gtc_mod.invalidate()

    real_fnmatchcase = fnmatch.fnmatchcase
    call_count = {"n": 0}

    def _count(name, pat):
        call_count["n"] += 1
        return real_fnmatchcase(name, pat)

    result = {"minions": [], "missing": []}
    with patch("fnmatch.fnmatchcase", side_effect=_count):
        ck._augment_grain_match_with_resource_grains(
            result, "resource_id:a-*", ":", regex_match=False
        )

    assert len(result["minions"]) == 100
    # Sorted-cache path should keep fnmatch calls bounded by
    # (matches + a few bsearch probes). Pin an upper bound well below
    # the full bank size. On a pure linear scan this would be 10000.
    bound = 100 * 2 + 64
    assert call_count["n"] <= bound, (
        f"fnmatchcase called {call_count['n']} times on a 10K bank with "
        f"100 matches -- expected <= {bound} with sorted-cache routing"
    )


def test_augment_grain_resource_id_no_fixed_prefix_matches_correctly(opts):
    """
    ``resource_id:*-foo`` has no fixed prefix. The sorted-cache path
    does not apply; we fall through to the existing linear scan but
    the match set must still be correct.
    """
    opts["minion_data_cache"] = True
    ck, _fake = _build_ck_with_keys(opts, ["dummy:a-foo", "dummy:b-foo", "dummy:a-bar"])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:*-foo", ":", regex_match=False
    )
    assert _rids(result) == ["a-foo", "b-foo"]


def test_augment_grain_resource_id_charclass_first_matches_correctly(opts):
    """
    ``resource_id:[ab]-*`` leads with a char class -- there is no
    fixed prefix. The implementation may fall through to a linear
    scan or expand the char class; either way the result set must
    match exactly the keys that fnmatch accepts.
    """
    opts["minion_data_cache"] = True
    ck, _fake = _build_ck_with_keys(opts, ["dummy:a-1", "dummy:b-1", "dummy:c-1"])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:[ab]-*", ":", regex_match=False
    )
    assert _rids(result) == ["a-1", "b-1"]


def test_augment_grain_resource_id_pure_literal_uses_mission1_hash_probe(opts):
    """
    A literal predicate (``resource_id:a-dummy-0000100``) is handled
    by Mission 1's ``cache.contains`` hash-probe fast path. The
    Mission 2 sorted-cache path MUST NOT be consulted.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present_keys = {"dummy:a-dummy-0000100": {"resource_id": "a-dummy-0000100"}}

    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    fake.contains = MagicMock(
        side_effect=lambda b, k: b == "resource_grains" and k in present_keys
    )
    fake.list = MagicMock(return_value=[])
    fake.fetch = MagicMock(return_value=None)
    ck.cache = fake

    gsk_candidates = ["get_sorted_keys", "sorted_keys", "sorted_keys_for_bank"]
    gsk_name = next(
        (n for n in gsk_candidates if hasattr(_gtc, n)),
        None,
    )
    if gsk_name is None:
        pytest.skip("grain_target_cache has no recognised sorted-keys entry point")

    with patch.object(_gtc, gsk_name) as sorted_cache_entry:
        result = {"minions": [], "missing": []}
        ck._augment_grain_match_with_resource_grains(
            result,
            "resource_id:a-dummy-0000100",
            ":",
            regex_match=False,
        )

    assert result["minions"] == ["a-dummy-0000100"]
    assert sorted_cache_entry.call_count == 0, (
        "literal resource_id predicate should be resolved by the "
        "Mission 1 hash-probe path, not the sorted-key cache"
    )


def test_augment_grain_non_resource_id_predicate_bypasses_sorted_cache(opts):
    """
    ``role:web`` is not a ``resource_id`` predicate -- the sorted-key
    cache must not be consulted. The slow pickle-fetch path runs and
    the match set is still correct.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    entries = {
        "dummy:d-1": {"role": "web", "resource_id": "d-1"},
        "dummy:d-2": {"role": "db", "resource_id": "d-2"},
    }
    fake.list = MagicMock(
        side_effect=lambda b: list(entries) if b == "resource_grains" else []
    )
    fake.fetch = MagicMock(
        side_effect=lambda b, k: entries.get(k) if b == "resource_grains" else None
    )
    fake.contains = MagicMock(return_value=False)
    ck.cache = fake

    gsk_candidates = ["get_sorted_keys", "sorted_keys", "sorted_keys_for_bank"]
    gsk_name = next((n for n in gsk_candidates if hasattr(_gtc, n)), None)
    if gsk_name is None:
        pytest.skip("grain_target_cache has no recognised sorted-keys entry point")

    with patch.object(_gtc, gsk_name) as sorted_cache_entry:
        result = {"minions": [], "missing": []}
        ck._augment_grain_match_with_resource_grains(
            result, "role:web", ":", regex_match=False
        )

    assert result["minions"] == ["d-1"]
    assert sorted_cache_entry.call_count == 0


def test_augment_grain_resource_id_empty_predicate_does_not_crash(opts):
    opts["minion_data_cache"] = True
    ck, _fake = _build_ck_with_keys(opts, ["dummy:x"])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:", ":", regex_match=False
    )
    assert result["minions"] == []


def test_augment_grain_resource_id_pcre_bypasses_sorted_cache(opts):
    """
    PCRE form bypasses the fixed-prefix sorted-cache path. The sorted
    cache sees nothing; the existing regex scan produces the match.
    """
    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    present = {
        "dummy:d-1": {"resource_id": "d-1"},
        "dummy:x-1": {"resource_id": "x-1"},
    }
    ck = salt.utils.minions.CkMinions(opts)
    fake = MagicMock()
    fake.list = MagicMock(
        side_effect=lambda b: list(present) if b == "resource_grains" else []
    )
    fake.fetch = MagicMock(
        side_effect=lambda b, k: present.get(k) if b == "resource_grains" else None
    )
    fake.contains = MagicMock(return_value=False)
    ck.cache = fake

    gsk_candidates = ["get_sorted_keys", "sorted_keys", "sorted_keys_for_bank"]
    gsk_name = next((n for n in gsk_candidates if hasattr(_gtc, n)), None)

    result = {"minions": [], "missing": []}
    if gsk_name is None:
        ck._augment_grain_match_with_resource_grains(
            result, "resource_id:^d-", ":", regex_match=True
        )
    else:
        with patch.object(_gtc, gsk_name) as sorted_cache_entry:
            ck._augment_grain_match_with_resource_grains(
                result, "resource_id:^d-", ":", regex_match=True
            )
            assert sorted_cache_entry.call_count == 0

    # The current PCRE path matches ``d-1`` through subdict_match.
    assert "d-1" in result["minions"]
    assert "x-1" not in result["minions"]


def test_augment_grain_resource_id_fixed_prefix_empty_bank_returns_empty(opts):
    opts["minion_data_cache"] = True
    ck, _fake = _build_ck_with_keys(opts, [])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-*", ":", regex_match=False
    )
    assert result["minions"] == []


def test_augment_grain_resource_id_fixed_prefix_cached_across_calls(opts, tmp_path):
    """
    Two identical ``resource_id:<prefix>*`` queries in a row: the
    second query must not re-sort the bank. We assert this by
    counting ``cache.list`` calls -- a correctly-caching planner hits
    ``list`` at most ~1 time per query (one to confirm the generation
    hasn't changed; the actual sort is cached).

    The sorted-key cache uses a cheap O(1) bank-generation signal
    (mmap occupied-count or bank-directory mtime) to decide whether
    to rebuild. We stage a real on-disk bank directory so the
    directory-mtime fallback engages.
    """
    import os

    import salt.utils.grain_target_cache as _gtc_mod

    opts["minion_data_cache"] = True
    opts["resource_types"] = ["dummy"]
    bank_dir = tmp_path / "resource_grains"
    bank_dir.mkdir()
    cachedir = str(tmp_path)

    ck, fake = _build_ck_with_keys(opts, ["dummy:a-1", "dummy:a-2", "dummy:b-1"])
    fake.cachedir = cachedir
    # Force a clean cache slate so prior tests sharing the singleton
    # don't pollute this assertion.
    _gtc_mod.invalidate()

    result1 = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result1, "resource_id:a-*", ":", regex_match=False
    )
    first_list_calls = fake.list.call_count

    # Pin the bank-dir mtime so the generation signal does not advance
    # between the two queries (otherwise filesystem jitter would force
    # a rebuild and this test would be a flake rather than a cache
    # invariant check).
    st = os.stat(bank_dir)
    os.utime(bank_dir, ns=(st.st_atime_ns, st.st_mtime_ns))

    result2 = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result2, "resource_id:a-*", ":", regex_match=False
    )
    second_list_calls = fake.list.call_count

    assert _rids(result1) == _rids(result2) == ["a-1", "a-2"]
    # The second query should not materially increase the number of
    # list calls -- the sorted view is cached.
    assert second_list_calls - first_list_calls <= 1, (
        f"sorted-cache did not short-circuit the second identical query: "
        f"list() went from {first_list_calls} to {second_list_calls}"
    )


def test_augment_grain_resource_id_dedup_across_calls(opts):
    """
    A predicate matching 100 keys, called twice against the same
    ``result`` object, must contain each rid exactly once.
    """
    opts["minion_data_cache"] = True
    keys = [f"dummy:a-{i:03d}" for i in range(100)]
    keys += [f"dummy:b-{i:03d}" for i in range(50)]
    ck, _fake = _build_ck_with_keys(opts, keys)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-*", ":", regex_match=False
    )
    assert len(result["minions"]) == 100

    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-*", ":", regex_match=False
    )
    # No duplicates after the second identical query.
    assert len(result["minions"]) == len(set(result["minions"])) == 100


def test_augment_grain_resource_id_fixed_prefix_dedup_on_duplicate_keys(opts):
    """
    If the bank somehow returns a duplicate key for the sorted view,
    the resulting rid list must still contain each id exactly once.
    """
    opts["minion_data_cache"] = True
    # ``_build_ck_with_keys`` preserves duplicates as-is.
    ck, _fake = _build_ck_with_keys(opts, ["dummy:a-1", "dummy:a-1", "dummy:a-2"])
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:a-*", ":", regex_match=False
    )
    assert sorted(result["minions"]) == ["a-1", "a-2"]


@pytest.mark.parametrize(
    "pattern",
    [
        "a-*",
        "a-dummy-001*",
        "web-*",
        "ns-*",
        "foo?-*",
        "literal-key-123",
    ],
)
def test_augment_grain_resource_id_matches_linear_reference(opts, pattern):
    """
    Match-set equivalence: for any glob with a fixed prefix, the
    planner's output MUST equal the reference linear-scan match set
    over the bank's id portion. Covers a handful of representative
    shapes.
    """
    import fnmatch as _fnmatch
    import random as _random

    opts["minion_data_cache"] = True
    # Ensure Mission 1's literal hash-probe can resolve "<type>:<id>"
    # candidates; without this, a literal-only pattern returns empty
    # because the probe loop iterates zero configured types.
    opts["resource_types"] = ["dummy"]
    _random.seed(0xC0FFEE)
    keys = sorted(
        {
            f"dummy:{prefix}-{i:04d}"
            for prefix in ("a", "a-dummy-001", "a-dummy-002", "web", "ns", "foo1")
            for i in range(50)
        }
    )
    keys.append("dummy:literal-key-123")
    _random.shuffle(keys)

    ck, _fake = _build_ck_with_keys(opts, keys)

    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, f"resource_id:{pattern}", ":", regex_match=False
    )
    got = sorted(result["minions"])

    expected = sorted(
        {
            key.partition(":")[2]
            for key in keys
            if _fnmatch.fnmatchcase(key.partition(":")[2], pattern)
        }
    )
    assert got == expected, (
        f"pattern={pattern!r} planner returned {got!r} but linear "
        f"reference expects {expected!r}"
    )


def test_augment_grain_resource_id_prefix_with_colon_treats_id_only(opts):
    """
    Resource IDs are allowed to contain colons; the sorted keys are
    stored as ``<type>:<id>`` so a ``resource_id:ns:res-*`` query
    carries the first colon INSIDE the id portion. The current
    planner already treats a nested predicate specially (via
    ``_resource_id_candidates``, which returns ``None`` and falls
    back). The Mission 2 sorted-cache path is NOT expected to handle
    nested patterns either -- but it must still produce the correct
    result, even if that means the slow-path fallback runs.
    """
    opts["minion_data_cache"] = True
    # One matching key where the id literally contains a colon.
    keys = ["dummy:ns:res-1", "dummy:ns:res-2", "dummy:other"]
    ck, _fake = _build_ck_with_keys(opts, keys)
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, "resource_id:ns:res-*", ":", regex_match=False
    )
    # The nested-predicate rule short-circuits to the slow path.
    # subdict_match on {"resource_id": "ns:res-1"} with
    # ``resource_id:ns:res-*`` traverses one level and then runs an
    # fnmatch-style check on the remainder -- documented as a
    # fall-through here, not a strict shape test. Confirm no crash
    # and the result is a subset of the matching keys.
    for rid in result["minions"]:
        assert rid.startswith("ns:res-"), rid


def test_augment_grain_resource_id_backslash_in_pattern(opts):
    """
    ``resource_id:a\\*-foo`` -- backslash is NOT a glob escape in
    :mod:`fnmatch`; the pattern matches a literal ``a\\`` followed by
    any chars ending in ``-foo``. The sorted-cache planner must not
    misparse the backslash as an escape and silently drop the match.
    """
    import fnmatch as _fnmatch

    opts["minion_data_cache"] = True
    keys = [r"dummy:a\x-foo", r"dummy:a\y-foo", "dummy:aZ-foo"]
    ck, _fake = _build_ck_with_keys(opts, keys)

    pattern = r"a\*-foo"
    result = {"minions": [], "missing": []}
    ck._augment_grain_match_with_resource_grains(
        result, f"resource_id:{pattern}", ":", regex_match=False
    )
    expected = sorted(
        {
            key.partition(":")[2]
            for key in keys
            if _fnmatch.fnmatchcase(key.partition(":")[2], pattern)
        }
    )
    assert sorted(result["minions"]) == expected
