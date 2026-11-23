"""
Tests for salt.utils.resources.

Covers:
- enabled_resource_types(opts): opt-driven list of resource types the minion runs
- bare_resource_ids_from_decl(): flatten per-type id maps
- bare_resource_id_in_minion_data_cache(): master-side grains-cache lookup
"""

import logging

import salt.utils.resources
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# enabled_resource_types()
# ---------------------------------------------------------------------------


def test_enabled_resource_types_empty_opts_returns_empty_list():
    """No ``resource_types`` configured -> no types enabled."""
    assert salt.utils.resources.enabled_resource_types({}) == []


def test_enabled_resource_types_none_returns_empty_list():
    """Explicit ``resource_types: None`` is treated like absent."""
    assert salt.utils.resources.enabled_resource_types({"resource_types": None}) == []


def test_enabled_resource_types_empty_list_returns_empty_list():
    assert salt.utils.resources.enabled_resource_types({"resource_types": []}) == []


def test_enabled_resource_types_simple_list_passthrough():
    opts = {"resource_types": ["dummy", "ssh"]}
    assert salt.utils.resources.enabled_resource_types(opts) == ["dummy", "ssh"]


def test_enabled_resource_types_filters_non_string_entries():
    """Non-string entries (None, int, dict) are filtered out, not raised."""
    opts = {"resource_types": ["dummy", None, 42, {}, "ssh", ""]}
    assert salt.utils.resources.enabled_resource_types(opts) == ["dummy", "ssh"]


def test_enabled_resource_types_non_list_warns_and_defaults(caplog):
    """A scalar/dict ``resource_types`` is rejected with a warning."""
    caplog.set_level(logging.WARNING)
    assert (
        salt.utils.resources.enabled_resource_types({"resource_types": "dummy"}) == []
    )
    assert "resource_types" in caplog.text


def test_enabled_resource_types_dict_warns_and_defaults(caplog):
    caplog.set_level(logging.WARNING)
    assert (
        salt.utils.resources.enabled_resource_types({"resource_types": {"dummy": {}}})
        == []
    )
    assert "resource_types" in caplog.text


# ---------------------------------------------------------------------------
# bare_resource_ids_from_decl() -- shared by master-side cache lookup
# ---------------------------------------------------------------------------


def test_bare_resource_ids_from_decl_list_shape():
    """Post-discovery shape: ``{rtype: [id, ...]}``."""
    decl = {"dummy": ["d1", "d2"], "ssh": ["h1"]}
    assert sorted(salt.utils.resources.bare_resource_ids_from_decl(decl)) == [
        "d1",
        "d2",
        "h1",
    ]


def test_bare_resource_ids_from_decl_handles_non_dict():
    assert salt.utils.resources.bare_resource_ids_from_decl(None) == []
    assert salt.utils.resources.bare_resource_ids_from_decl("nope") == []


# ---------------------------------------------------------------------------
# bare_resource_id_in_minion_data_cache() -- grains-only path (post-pillar-removal)
# ---------------------------------------------------------------------------


def test_bare_resource_id_in_cache_grains_hit():
    """With pillar gone, grains is the only cache-side fallback source."""
    grains_cache = MagicMock()
    grains_cache.list.return_value = ["minion-2"]
    grains_cache.fetch.return_value = {"salt_resources": {"dummy": ["m2-dummy2"]}}

    opts = {"minion_data_cache": True}
    with patch("salt.cache.factory", return_value=grains_cache):
        assert salt.utils.resources.bare_resource_id_in_minion_data_cache(
            opts, "m2-dummy2"
        )


def test_bare_resource_id_in_cache_grains_miss():
    grains_cache = MagicMock()
    grains_cache.list.return_value = ["minion-2"]
    grains_cache.fetch.return_value = {"salt_resources": {"dummy": ["m2-dummy2"]}}

    opts = {"minion_data_cache": True}
    with patch("salt.cache.factory", return_value=grains_cache):
        assert not salt.utils.resources.bare_resource_id_in_minion_data_cache(
            opts, "not-a-resource"
        )


def test_bare_resource_id_in_cache_disabled_returns_false():
    opts = {"minion_data_cache": False}
    assert not salt.utils.resources.bare_resource_id_in_minion_data_cache(
        opts, "m2-dummy2"
    )


def test_bare_resource_id_in_cache_reuses_passed_cache_for_grains():
    shared = MagicMock()

    def list_side_effect(bank):
        if bank == "grains":
            return ["minion-2"]
        return []

    def fetch_side_effect(bank, mid):
        if bank == "grains" and mid == "minion-2":
            return {"salt_resources": {"dummy": ["m2-dummy2"]}}
        return {}

    shared.list.side_effect = list_side_effect
    shared.fetch.side_effect = fetch_side_effect

    opts = {"minion_data_cache": True}
    assert salt.utils.resources.bare_resource_id_in_minion_data_cache(
        opts, "m2-dummy2", cache=shared
    )


# ---------------------------------------------------------------------------
# No-pillar invariant: the opts["pillar"] subtree must NEVER be read by the
# resource utils that remain. Guards against regression that re-introduces
# removed pillar helpers by any other name.
# ---------------------------------------------------------------------------


def test_enabled_resource_types_does_not_read_pillar():
    """A trap pillar subtree must not influence enabled_resource_types."""
    opts = {
        "pillar": {"resources": {"dummy": {"resource_ids": ["poison"]}}},
    }
    # Pillar's "resources" key must NOT be interpreted as enabling the dummy type.
    assert salt.utils.resources.enabled_resource_types(opts) == []


def test_module_has_no_pillar_helpers():
    """Guard the removed pillar-reader helpers. If anyone re-adds either, fail."""
    removed = ("pillar" + "_resources_tree", "resource" + "_pillar_key")
    for name in removed:
        assert not hasattr(salt.utils.resources, name), (
            f"salt.utils.resources.{name} is re-added; pillar-as-source "
            "is deprecated -- use enabled_resource_types(opts) and per-module "
            "opts keys instead."
        )
