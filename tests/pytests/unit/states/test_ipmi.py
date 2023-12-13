"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.states.ipmi
"""

import pytest

import salt.states.ipmi as ipmi
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {ipmi: {}}


def test_boot_device():
    """
    Test to request power state change.
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value=name)
    with patch.dict(
        ipmi.__salt__, {"ipmi.get_bootdev": mock, "ipmi.set_bootdev": mock}
    ):
        comt = "system already in this state"
        ret.update({"comment": comt})
        assert ipmi.boot_device(name) == ret

        with patch.dict(ipmi.__opts__, {"test": False}):
            comt = "changed boot device"
            ret.update(
                {
                    "name": "default",
                    "comment": comt,
                    "result": True,
                    "changes": {"new": "default", "old": "salt"},
                }
            )
            assert ipmi.boot_device() == ret

        with patch.dict(ipmi.__opts__, {"test": True}):
            comt = "would change boot device"
            ret.update({"comment": comt, "result": None})
            assert ipmi.boot_device() == ret


def test_power():
    """
    Test to request power state change
    """
    ret = {"name": "power_on", "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value="on")
    with patch.dict(ipmi.__salt__, {"ipmi.get_power": mock, "ipmi.set_power": mock}):
        comt = "system already in this state"
        ret.update({"comment": comt})
        assert ipmi.power() == ret

        with patch.dict(ipmi.__opts__, {"test": False}):
            comt = "changed system power"
            ret.update(
                {
                    "name": "off",
                    "comment": comt,
                    "result": True,
                    "changes": {"new": "off", "old": "on"},
                }
            )
            assert ipmi.power("off") == ret

        with patch.dict(ipmi.__opts__, {"test": True}):
            comt = "would power: off system"
            ret.update({"comment": comt, "result": None})
            assert ipmi.power("off") == ret


def test_user_present():
    """
    Test to ensure IPMI user and user privileges.
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock_ret = {
        "access": {
            "callback": False,
            "link_auth": True,
            "ipmi_msg": True,
            "privilege_level": "administrator",
        }
    }
    mock = MagicMock(return_value=mock_ret)
    mock_bool = MagicMock(side_effect=[True, False, False, False])
    with patch.dict(
        ipmi.__salt__,
        {
            "ipmi.get_user": mock,
            "ipmi.set_user_password": mock_bool,
            "ipmi.ensure_user": mock_bool,
        },
    ):
        comt = "user already present"
        ret.update({"comment": comt})
        assert ipmi.user_present(name, 5, "salt@123") == ret

        with patch.dict(ipmi.__opts__, {"test": True}):
            comt = "would (re)create user"
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"new": "salt", "old": mock_ret},
                }
            )
            assert ipmi.user_present(name, 5, "pw@123") == ret

        with patch.dict(ipmi.__opts__, {"test": False}):
            comt = "(re)created user"
            ret.update(
                {
                    "comment": comt,
                    "result": True,
                    "changes": {"new": mock_ret, "old": mock_ret},
                }
            )
            assert ipmi.user_present(name, 5, "pw@123") == ret


def test_user_absent():
    """
    Test to delete all user (uid) records having the matching name.
    """
    name = "salt"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[[], [5], [5]])
    mock_bool = MagicMock(return_value=True)
    with patch.dict(
        ipmi.__salt__, {"ipmi.get_name_uids": mock, "ipmi.delete_user": mock_bool}
    ):
        comt = "user already absent"
        ret.update({"comment": comt})
        assert ipmi.user_absent(name) == ret

        with patch.dict(ipmi.__opts__, {"test": True}):
            comt = "would delete user(s)"
            ret.update({"comment": comt, "result": None, "changes": {"delete": [5]}})
            assert ipmi.user_absent(name) == ret

        with patch.dict(ipmi.__opts__, {"test": False}):
            comt = "user(s) removed"
            ret.update(
                {
                    "comment": comt,
                    "result": False,
                    "changes": {"new": "None", "old": [5]},
                }
            )
            assert ipmi.user_absent(name) == ret
