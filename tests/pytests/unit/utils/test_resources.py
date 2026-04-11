"""
Tests for salt.utils.resources (configurable resource pillar key).
"""

import salt.utils.resources


def test_resource_pillar_key_default():
    assert salt.utils.resources.resource_pillar_key({}) == "resources"
    assert salt.utils.resources.resource_pillar_key({"resource_pillar_key": "x"}) == "x"


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
