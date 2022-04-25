import copy
import os

import pytest
import salt.modules.ini_manage as mod_ini_manage
import salt.states.ini_manage as ini_manage
from salt.utils.odict import OrderedDict
from tests.support.mock import patch


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


def test_options_present(tmpdir, sections):
    """
    Test to verify options present when
    file does not initially exist
    """
    name = tmpdir.join("test.ini").strpath

    exp_ret = {
        "name": name,
        "changes": {"general": {"before": None, "after": sections["general"]}},
        "result": True,
        "comment": "Changes take effect",
    }
    assert ini_manage.options_present(name, sections) == exp_ret
    assert os.path.exists(name)
    assert mod_ini_manage.get_ini(name) == sections


def test_options_present_true_no_file(tmpdir, sections):
    """
    Test to verify options present when
    file does not initially exist and test=True
    """
    name = tmpdir.join("test_true_no_file.ini").strpath

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


def test_options_present_true_file(tmpdir, sections):
    """
    Test to verify options present when
    file does exist and test=True
    """
    name = tmpdir.join("test_true_file.ini").strpath

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
