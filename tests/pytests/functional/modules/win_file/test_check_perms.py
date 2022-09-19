"""
Tests for win_file execution module
"""
import pytest

import salt.modules.win_file as win_file
import salt.utils.win_dacl as win_dacl
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {
        win_file: {
            "__utils__": {
                "dacl.check_perms": win_dacl.check_perms,
                "dacl.set_perms": win_dacl.set_perms,
            }
        },
        win_dacl: {"__opts__": {"test": False}},
    }


@pytest.fixture(scope="function")
def test_file():
    with pytest.helpers.temp_file("win_file_test.file") as test_file:
        yield test_file


def test_check_perms_set_owner_test_true(test_file):
    """
    Test setting the owner of a file with test=True
    """
    expected = {
        "comment": "",
        "changes": {"owner": "Backup Operators"},
        "name": str(test_file),
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_file.check_perms(
            path=str(test_file), owner="Backup Operators", inheritance=None
        )
        assert result == expected


def test_check_perms_set_owner(test_file):
    """
    Test setting the owner of a file
    """
    expected = {
        "comment": "",
        "changes": {"owner": "Backup Operators"},
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(
        path=str(test_file), owner="Backup Operators", inheritance=None
    )
    assert result == expected


def test_check_perms_deny_test_true(test_file):
    """
    Test setting deny perms on a file with test=True
    """
    expected = {
        "comment": "",
        "changes": {"deny_perms": {"Users": {"permissions": "read_execute"}}},
        "name": str(test_file),
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_file.check_perms(
            path=str(test_file),
            deny_perms={"Users": {"perms": "read_execute"}},
            inheritance=None,
        )
    assert result == expected


def test_check_perms_deny(test_file):
    """
    Test setting deny perms on a file
    """
    expected = {
        "comment": "",
        "changes": {"deny_perms": {"Users": {"permissions": "read_execute"}}},
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(
        path=str(test_file),
        deny_perms={"Users": {"perms": "read_execute"}},
        inheritance=None,
    )
    assert result == expected


def test_check_perms_grant_test_true(test_file):
    """
    Test setting grant perms on a file with test=True
    """
    expected = {
        "comment": "",
        "changes": {"grant_perms": {"Users": {"permissions": "read_execute"}}},
        "name": str(test_file),
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_file.check_perms(
            path=str(test_file),
            grant_perms={"Users": {"perms": "read_execute"}},
            inheritance=None,
        )
        assert result == expected


def test_check_perms_grant(test_file):
    """
    Test setting grant perms on a file
    """
    expected = {
        "comment": "",
        "changes": {"grant_perms": {"Users": {"permissions": "read_execute"}}},
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(
        path=str(test_file),
        grant_perms={"Users": {"perms": "read_execute"}},
        inheritance=None,
    )
    assert result == expected


def test_check_perms_inheritance_false_test_true(test_file):
    """
    Test setting inheritance to False with test=True
    """
    expected = {
        "comment": "",
        "changes": {"inheritance": False},
        "name": str(test_file),
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_file.check_perms(path=str(test_file), inheritance=False)
    assert result == expected


def test_check_perms_inheritance_false(test_file):
    """
    Test setting inheritance to False
    """
    expected = {
        "comment": "",
        "changes": {"inheritance": False},
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(path=str(test_file), inheritance=False)
    assert result == expected


def test_check_perms_inheritance_true(test_file):
    """
    Test setting inheritance to true when it's already true (default)
    """
    expected = {
        "comment": "",
        "changes": {},
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(path=str(test_file), inheritance=True)
    assert result == expected


def test_check_perms_reset_test_true(test_file):
    """
    Test resetting perms with test=True. This shows minimal changes
    """
    # Turn off inheritance
    win_dacl.set_inheritance(obj_name=str(test_file), enabled=False, clear=True)
    # Set some permissions
    win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Administrator",
        permissions="full_control",
    )
    expected = {
        "comment": "",
        "changes": {
            "grant_perms": {
                "Administrators": {"permissions": "full_control"},
                "Users": {"permissions": "read_execute"},
            },
            "remove_perms": {
                "Administrator": {
                    "grant": {
                        "applies to": "This folder only",
                        "permissions": "Full control",
                    }
                }
            },
        },
        "name": str(test_file),
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        result = win_file.check_perms(
            path=str(test_file),
            grant_perms={
                "Users": {"perms": "read_execute"},
                "Administrators": {"perms": "full_control"},
            },
            inheritance=False,
            reset=True,
        )
        assert result == expected


def test_check_perms_reset(test_file):
    """
    Test resetting perms on a File
    """
    # Turn off inheritance
    win_dacl.set_inheritance(obj_name=str(test_file), enabled=False, clear=True)
    # Set some permissions
    win_dacl.set_permissions(
        obj_name=str(test_file),
        principal="Administrator",
        permissions="full_control",
    )
    expected = {
        "comment": "",
        "changes": {
            "grant_perms": {
                "Administrators": {"permissions": "full_control"},
                "Users": {"permissions": "read_execute"},
            },
            "remove_perms": {
                "Administrator": {
                    "grant": {
                        "applies to": "This folder only",
                        "permissions": "Full control",
                    }
                }
            },
        },
        "name": str(test_file),
        "result": True,
    }
    result = win_file.check_perms(
        path=str(test_file),
        grant_perms={
            "Users": {"perms": "read_execute"},
            "Administrators": {"perms": "full_control"},
        },
        inheritance=False,
        reset=True,
    )
    assert result == expected


def test_check_perms_issue_43328(test_file):
    """
    Make sure that a CommandExecutionError is raised if the file does NOT
    exist
    """
    fake_file = test_file.parent / "fake.file"
    with pytest.raises(CommandExecutionError):
        win_file.check_perms(str(fake_file))
