"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.powerpath as powerpath
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {powerpath: {}}


def test_license_present():
    """
    Test to ensures that the specified PowerPath license key is present
    on the host.
    """
    name = "mylic"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_t = MagicMock(
        side_effect=[
            {"result": True, "output": name},
            {"result": False, "output": name},
        ]
    )
    mock = MagicMock(side_effect=[False, True, True, True, True])
    mock_l = MagicMock(return_value=[{"key": name}])
    with patch.dict(
        powerpath.__salt__,
        {
            "powerpath.has_powerpath": mock,
            "powerpath.list_licenses": mock_l,
            "powerpath.add_license": mock_t,
        },
    ):
        comt = "PowerPath is not installed."
        ret.update({"comment": comt, "result": False})
        assert powerpath.license_present(name) == ret

        comt = "License key {} already present".format(name)
        ret.update({"comment": comt, "result": True})
        assert powerpath.license_present(name) == ret

        with patch.dict(powerpath.__opts__, {"test": True}):
            comt = "License key Mylic is set to be added"
            ret.update({"comment": comt, "result": None, "name": "Mylic"})
            assert powerpath.license_present("Mylic") == ret

        with patch.dict(powerpath.__opts__, {"test": False}):
            ret.update({"comment": name, "result": True, "changes": {"Mylic": "added"}})
            assert powerpath.license_present("Mylic") == ret

            ret.update({"result": False, "changes": {}})
            assert powerpath.license_present("Mylic") == ret


def test_license_absent():
    """
    Test to ensures that the specified PowerPath license key is absent
    on the host.
    """
    name = "mylic"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    mock_t = MagicMock(
        side_effect=[
            {"result": True, "output": name},
            {"result": False, "output": name},
        ]
    )
    mock = MagicMock(side_effect=[False, True, True, True, True])
    mock_l = MagicMock(return_value=[{"key": "salt"}])
    with patch.dict(
        powerpath.__salt__,
        {
            "powerpath.has_powerpath": mock,
            "powerpath.list_licenses": mock_l,
            "powerpath.remove_license": mock_t,
        },
    ):
        comt = "PowerPath is not installed."
        ret.update({"comment": comt, "result": False})
        assert powerpath.license_absent(name) == ret

        comt = "License key {} not present".format(name)
        ret.update({"comment": comt, "result": True})
        assert powerpath.license_absent(name) == ret

        with patch.dict(powerpath.__opts__, {"test": True}):
            comt = "License key salt is set to be removed"
            ret.update({"comment": comt, "result": None, "name": "salt"})
            assert powerpath.license_absent("salt") == ret

        with patch.dict(powerpath.__opts__, {"test": False}):
            ret.update(
                {"comment": name, "result": True, "changes": {"salt": "removed"}}
            )
            assert powerpath.license_absent("salt") == ret

            ret.update({"result": False, "changes": {}})
            assert powerpath.license_absent("salt") == ret
