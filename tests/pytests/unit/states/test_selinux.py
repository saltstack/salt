"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.selinux as selinux
from tests.support.mock import MagicMock, patch

pytestmark = [pytest.mark.skip_unless_on_linux]


@pytest.fixture
def configure_loader_modules():
    return {selinux: {}}


def test_mode():
    """
    Test to verifies the mode SELinux is running in,
    can be set to enforcing or permissive.
    """
    ret = {
        "name": "unknown",
        "changes": {},
        "result": False,
        "comment": "unknown is not an accepted mode",
    }
    assert selinux.mode("unknown") == ret

    mock_en = MagicMock(return_value="Enforcing")
    mock_pr = MagicMock(side_effect=["Permissive", "Enforcing"])
    with patch.dict(
        selinux.__salt__,
        {
            "selinux.getenforce": mock_en,
            "selinux.getconfig": mock_en,
            "selinux.setenforce": mock_pr,
        },
    ):
        comt = "SELinux is already in Enforcing mode"
        ret = {"name": "Enforcing", "comment": comt, "result": True, "changes": {}}
        assert selinux.mode("Enforcing") == ret

        with patch.dict(selinux.__opts__, {"test": True}):
            comt = "SELinux mode is set to be changed to Permissive"
            ret = {
                "name": "Permissive",
                "comment": comt,
                "result": None,
                "changes": {"new": "Permissive", "old": "Enforcing"},
            }
            assert selinux.mode("Permissive") == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "SELinux has been set to Permissive mode"
            ret = {
                "name": "Permissive",
                "comment": comt,
                "result": True,
                "changes": {"new": "Permissive", "old": "Enforcing"},
            }
            assert selinux.mode("Permissive") == ret

            comt = "Failed to set SELinux to Permissive mode"
            ret.update(
                {"name": "Permissive", "comment": comt, "result": False, "changes": {}}
            )
            assert selinux.mode("Permissive") == ret


def test_boolean():
    """
    Test to set up an SELinux boolean.
    """
    name = "samba_create_home_dirs"
    value = True
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_en = MagicMock(return_value=[])
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_en}):
        comt = f"Boolean {name} is not available"
        ret.update({"comment": comt})
        assert selinux.boolean(name, value) == ret

    mock_bools = MagicMock(return_value={name: {"State": "on", "Default": "on"}})
    with patch.dict(selinux.__salt__, {"selinux.list_sebool": mock_bools}):
        comt = "None is not a valid value for the boolean"
        ret.update({"comment": comt})
        assert selinux.boolean(name, None) == ret

        comt = "Boolean is in the correct state"
        ret.update({"comment": comt, "result": True})
        assert selinux.boolean(name, value, True) == ret

        comt = "Boolean is in the correct state"
        ret.update({"comment": comt, "result": True})
        assert selinux.boolean(name, value) == ret

    mock_bools = MagicMock(return_value={name: {"State": "off", "Default": "on"}})
    mock = MagicMock(side_effect=[True, False])
    with patch.dict(
        selinux.__salt__,
        {"selinux.list_sebool": mock_bools, "selinux.setsebool": mock},
    ):
        with patch.dict(selinux.__opts__, {"test": True}):
            comt = "Boolean samba_create_home_dirs is set to be changed to on"
            ret.update({"comment": comt, "result": None})
            assert selinux.boolean(name, value) == ret

        with patch.dict(selinux.__opts__, {"test": False}):
            comt = "Boolean samba_create_home_dirs has been set to on"
            ret.update({"comment": comt, "result": True})
            ret.update({"changes": {"State": {"old": "off", "new": "on"}}})
            assert selinux.boolean(name, value) == ret

            comt = "Failed to set the boolean samba_create_home_dirs to on"
            ret.update({"comment": comt, "result": False})
            ret.update({"changes": {}})
            assert selinux.boolean(name, value) == ret
