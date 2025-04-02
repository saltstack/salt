"""
    Test cases for salt.states.ini_manage
"""

import copy
import os

import pytest

import salt.modules.ini_manage as mod_ini_manage
import salt.states.ini_manage as ini_manage
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        ini_manage: {
            "__salt__": {
                "ini.get_ini": mod_ini_manage.get_ini,
                "ini.set_option": mod_ini_manage.set_option,
            },
            "__opts__": {"test": False},
        },
        mod_ini_manage: {"__opts__": {"test": False}},
    }


@pytest.fixture
def sections():
    sections = OrderedDict()
    sections["general"] = OrderedDict()
    sections["general"]["hostname"] = "myserver.com"
    sections["general"]["port"] = "1234"
    return sections


def test_options_present(tmp_path, sections):
    """
    Test to verify options present when
    file does not initially exist
    """
    name = str(tmp_path / "test.ini")

    exp_ret = {
        "name": name,
        "changes": {"general": {"before": None, "after": sections["general"]}},
        "result": True,
        "comment": "Changes take effect",
    }
    assert ini_manage.options_present(name, sections) == exp_ret
    assert os.path.exists(name)
    assert mod_ini_manage.get_ini(name) == sections


def test_options_present_true_no_file(tmp_path, sections):
    """
    Test to verify options present when
    file does not initially exist and test=True
    """
    name = str(tmp_path / "test_true_no_file.ini")

    exp_ret = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": (
            "Changed key hostname in section general.\n"
            "Changed key port in section general.\n"
        ),
    }
    with patch.dict(ini_manage.__opts__, {"test": True}), patch.dict(
        mod_ini_manage.__opts__, {"test": True}
    ):
        assert ini_manage.options_present(name, sections) == exp_ret

    assert not os.path.exists(name)


def test_options_present_true_file(tmp_path, sections):
    """
    Test to verify options present when
    file does exist and test=True
    """
    name = str(tmp_path / "test_true_file.ini")

    exp_ret = {
        "name": name,
        "changes": {},
        "result": None,
        "comment": (
            "Unchanged key hostname in section general.\n"
            "Unchanged key port in section general.\n"
            "Changed key user in section general.\n"
        ),
    }

    ini_manage.options_present(name, sections)

    new_section = copy.deepcopy(sections)
    new_section["general"]["user"] = "saltuser"

    with patch.dict(ini_manage.__opts__, {"test": True}), patch.dict(
        mod_ini_manage.__opts__, {"test": True}
    ):
        assert ini_manage.options_present(name, new_section) == exp_ret

    assert os.path.exists(name)
    assert mod_ini_manage.get_ini(name) == sections


def test_options_absent():
    """
    Test to verify options absent in file.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(ini_manage.__opts__, {"test": True}):
        comt = "No changes detected."
        ret.update({"comment": comt, "result": True})
        assert ini_manage.options_absent(name) == ret

    with patch.dict(ini_manage.__opts__, {"test": False}):
        comt = "No anomaly detected"
        ret.update({"comment": comt, "result": True})
        assert ini_manage.options_absent(name) == ret
    sections = {"Tables": ["key2", "key3"]}
    changes = {"Tables": {"key2": "2", "key3": "3"}}
    with patch.dict(
        ini_manage.__salt__,
        {"ini.remove_option": MagicMock(side_effect=["2", "3"])},
    ):
        with patch.dict(ini_manage.__opts__, {"test": False}):
            comt = "Changes take effect"
            ret.update({"comment": comt, "result": True, "changes": changes})
            assert ini_manage.options_absent(name, sections) == ret


def test_sections_present():
    """
    Test to verify sections present in file.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(ini_manage.__opts__, {"test": True}):
        with patch.dict(
            ini_manage.__salt__, {"ini.get_ini": MagicMock(return_value=None)}
        ):
            comt = "No changes detected."
            ret.update({"comment": comt, "result": True})
            assert ini_manage.sections_present(name) == ret

    changes = {
        "first": "who is on",
        "second": "what is on",
        "third": "I don't know",
    }
    with patch.dict(
        ini_manage.__salt__, {"ini.set_option": MagicMock(return_value=changes)}
    ):
        with patch.dict(ini_manage.__opts__, {"test": False}):
            comt = "Changes take effect"
            ret.update({"comment": comt, "result": True, "changes": changes})
            assert ini_manage.sections_present(name) == ret


def test_sections_absent():
    """
    Test to verify sections absent in file.
    """
    name = "salt"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(ini_manage.__opts__, {"test": True}):
        with patch.dict(
            ini_manage.__salt__, {"ini.get_ini": MagicMock(return_value=None)}
        ):
            comt = "No changes detected."
            ret.update({"comment": comt, "result": True})
            assert ini_manage.sections_absent(name) == ret

    with patch.dict(ini_manage.__opts__, {"test": False}):
        comt = "No anomaly detected"
        ret.update({"comment": comt, "result": True})
        assert ini_manage.sections_absent(name) == ret
