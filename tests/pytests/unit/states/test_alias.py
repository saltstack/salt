"""
unit tests for the alias state
"""

import pytest

import salt.states.alias as alias
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {alias: {}}


def test_present_has_target():
    """
    test alias.present has target already
    """
    name = "saltdude"
    target = "dude@saltstack.com"
    ret = {
        "comment": f"Alias {name} already present",
        "changes": {},
        "name": name,
        "result": True,
    }

    has_target = MagicMock(return_value=True)
    with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
        assert alias.present(name, target) == ret


def test_present_has_not_target_test():
    """
    test alias.present has not target yet test mode
    """
    name = "saltdude"
    target = "dude@saltstack.com"
    ret = {
        "comment": f"Alias {name} -> {target} is set to be added",
        "changes": {},
        "name": name,
        "result": None,
    }

    has_target = MagicMock(return_value=False)
    with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
        with patch.dict(alias.__opts__, {"test": True}):
            assert alias.present(name, target) == ret


def test_present_set_target():
    """
    test alias.present set target
    """
    name = "saltdude"
    target = "dude@saltstack.com"
    ret = {
        "comment": f"Set email alias {name} -> {target}",
        "changes": {"alias": name},
        "name": name,
        "result": True,
    }

    has_target = MagicMock(return_value=False)
    set_target = MagicMock(return_value=True)
    with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
        with patch.dict(alias.__opts__, {"test": False}):
            with patch.dict(alias.__salt__, {"aliases.set_target": set_target}):
                assert alias.present(name, target) == ret


def test_present_set_target_failed():
    """
    test alias.present set target failure
    """
    name = "saltdude"
    target = "dude@saltstack.com"
    ret = {
        "comment": f"Failed to set alias {name} -> {target}",
        "changes": {},
        "name": name,
        "result": False,
    }

    has_target = MagicMock(return_value=False)
    set_target = MagicMock(return_value=False)
    with patch.dict(alias.__salt__, {"aliases.has_target": has_target}):
        with patch.dict(alias.__opts__, {"test": False}):
            with patch.dict(alias.__salt__, {"aliases.set_target": set_target}):
                assert alias.present(name, target) == ret


def test_absent_already_gone():
    """
    test alias.absent already gone
    """
    name = "saltdude"
    ret = {
        "comment": f"Alias {name} already absent",
        "changes": {},
        "name": name,
        "result": True,
    }

    get_target = MagicMock(return_value=False)
    with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
        assert alias.absent(name) == ret


def test_absent_not_gone_test():
    """
    test alias.absent already gone test mode
    """
    name = "saltdude"
    ret = {
        "comment": f"Alias {name} is set to be removed",
        "changes": {},
        "name": name,
        "result": None,
    }

    get_target = MagicMock(return_value=True)
    with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
        with patch.dict(alias.__opts__, {"test": True}):
            assert alias.absent(name) == ret


def test_absent_rm_alias():
    """
    test alias.absent remove alias
    """
    name = "saltdude"
    ret = {
        "comment": f"Removed alias {name}",
        "changes": {"alias": name},
        "name": name,
        "result": True,
    }

    get_target = MagicMock(return_value=True)
    rm_alias = MagicMock(return_value=True)
    with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
        with patch.dict(alias.__opts__, {"test": False}):
            with patch.dict(alias.__salt__, {"aliases.rm_alias": rm_alias}):
                assert alias.absent(name) == ret


def test_absent_rm_alias_failed():
    """
    test alias.absent remove alias failure
    """
    name = "saltdude"
    ret = {
        "comment": f"Failed to remove alias {name}",
        "changes": {},
        "name": name,
        "result": False,
    }

    get_target = MagicMock(return_value=True)
    rm_alias = MagicMock(return_value=False)
    with patch.dict(alias.__salt__, {"aliases.get_target": get_target}):
        with patch.dict(alias.__opts__, {"test": False}):
            with patch.dict(alias.__salt__, {"aliases.rm_alias": rm_alias}):
                assert alias.absent(name) == ret
