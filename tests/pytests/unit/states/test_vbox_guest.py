"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.vbox_guest as vbox_guest
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {vbox_guest: {}}


def test_additions_installed():
    """
    Test to ensure that the VirtualBox Guest Additions are installed
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[True, False, False, False])
    with patch.dict(
        vbox_guest.__salt__,
        {"vbox_guest.additions_version": mock, "vbox_guest.additions_install": mock},
    ):
        ret.update({"comment": "System already in the correct state"})
        assert vbox_guest.additions_installed("salt") == ret

        with patch.dict(vbox_guest.__opts__, {"test": True}):
            ret.update(
                {
                    "changes": {"new": True, "old": False},
                    "comment": (
                        "The state of VirtualBox Guest Additions will be changed."
                    ),
                    "result": None,
                }
            )
            assert vbox_guest.additions_installed("salt") == ret

        with patch.dict(vbox_guest.__opts__, {"test": False}):
            ret.update(
                {
                    "changes": {"new": False, "old": False},
                    "comment": "The state of VirtualBox Guest Additions was changed!",
                    "result": False,
                }
            )
            assert vbox_guest.additions_installed("salt") == ret


def test_additions_removed():
    """
    Test to ensure that the VirtualBox Guest Additions are removed.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[False, True, True, True])
    with patch.dict(
        vbox_guest.__salt__,
        {"vbox_guest.additions_version": mock, "vbox_guest.additions_remove": mock},
    ):
        ret.update({"comment": "System already in the correct state"})
        assert vbox_guest.additions_removed("salt") == ret

        with patch.dict(vbox_guest.__opts__, {"test": True}):
            ret.update(
                {
                    "changes": {"new": True, "old": True},
                    "comment": (
                        "The state of VirtualBox Guest Additions will be changed."
                    ),
                    "result": None,
                }
            )
            assert vbox_guest.additions_removed("salt") == ret

        with patch.dict(vbox_guest.__opts__, {"test": False}):
            ret.update(
                {
                    "comment": "The state of VirtualBox Guest Additions was changed!",
                    "result": True,
                }
            )
            assert vbox_guest.additions_removed("salt") == ret


def test_grantaccess_to_sharedfolders():
    """
    Test to grant access to auto-mounted shared folders to the users.
    """
    ret = {"name": "AB", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[["AB"], "salt", "salt", "salt"])
    with patch.dict(
        vbox_guest.__salt__,
        {
            "vbox_guest.list_shared_folders_users": mock,
            "vbox_guest.grant_access_to_shared_folders_to": mock,
        },
    ):
        ret.update({"comment": "System already in the correct state"})
        assert_method(ret)

        with patch.dict(vbox_guest.__opts__, {"test": True}):
            ret.update(
                {
                    "changes": {"new": ["AB"], "old": "salt"},
                    "comment": (
                        "List of users who have access to"
                        " auto-mounted shared folders will be changed"
                    ),
                    "result": None,
                }
            )
            assert_method(ret)

        with patch.dict(vbox_guest.__opts__, {"test": False}):
            ret.update(
                {
                    "changes": {"new": "salt", "old": "salt"},
                    "comment": (
                        "List of users who have access to"
                        " auto-mounted shared folders was changed"
                    ),
                    "result": True,
                }
            )
            assert_method(ret)


def assert_method(ret):
    """
    Method call for assert statements
    """
    assert vbox_guest.grant_access_to_shared_folders_to("AB") == ret
