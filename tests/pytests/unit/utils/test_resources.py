"""
Tests for salt.utils.resources (configurable resource pillar key).
"""

import logging

import pytest

import salt.utils.resources
from tests.support.mock import MagicMock, patch


def test_resource_pillar_key_default():
    assert salt.utils.resources.resource_pillar_key({}) == "resources"
    assert salt.utils.resources.resource_pillar_key({"resource_pillar_key": "x"}) == "x"


@pytest.mark.parametrize("bad", ("", None))
def test_resource_pillar_key_empty_warns_and_defaults(bad, caplog):
    caplog.set_level(logging.WARNING)
    assert (
        salt.utils.resources.resource_pillar_key({"resource_pillar_key": bad})
        == "resources"
    )
    assert "resource_pillar_key is empty" in caplog.text


def test_pillar_resources_tree_default_key():
    opts = {"pillar": {"resources": {"ssh": {}}}}
    assert salt.utils.resources.pillar_resources_tree(opts) == {"ssh": {}}


def test_pillar_resources_tree_custom_key():
    opts = {"resource_pillar_key": "my_res", "pillar": {"my_res": {"a": 1}}}
    assert salt.utils.resources.pillar_resources_tree(opts) == {"a": 1}


def test_pillar_resources_tree_missing_key_same_as_empty():
    opts = {"pillar": {}}
    assert salt.utils.resources.pillar_resources_tree(opts) == {}


def test_pillar_resources_tree_wrong_type():
    opts = {"pillar": {"resources": "bad"}}
    assert salt.utils.resources.pillar_resources_tree(opts) == {}


def test_bare_resource_id_in_cache_pillar_separate_cache_driver():
    """Pillar bank follows ``pillar.cache_driver``, not only the default cache."""
    pillar_cache = MagicMock()
    pillar_cache.list.return_value = ["minion-2"]
    pillar_cache.fetch.return_value = {
        "resources": {"dummy": {"resource_ids": ["m2-dummy2"]}}
    }

    grains_cache = MagicMock()
    grains_cache.list.return_value = []

    def fake_factory(opts, **kwargs):
        if kwargs.get("driver") == "pillar_redis":
            return pillar_cache
        return grains_cache

    opts = {"minion_data_cache": True, "pillar.cache_driver": "pillar_redis"}
    with patch("salt.cache.factory", side_effect=fake_factory):
        assert salt.utils.resources.bare_resource_id_in_minion_data_cache(
            opts, "m2-dummy2"
        )
    pillar_cache.list.assert_called_once_with("pillar")
    # Short-circuit once pillar matches; grains are not scanned.
    grains_cache.list.assert_not_called()


def test_bare_resource_id_in_cache_reuses_passed_cache_for_grains():
    shared = MagicMock()

    def list_side_effect(bank):
        if bank == "pillar":
            return []
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
