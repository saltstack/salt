"""
:codeauthor: Shane Lee <leesh@vmware.com>

    Test cases for salt.modules.win_file

"""
import os

from mock import MagicMock
import pytest
import salt.modules.win_file as win_file
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.win_dacl as win_dacl
import salt.utils.win_functions
import salt.modules.temp as temp
from salt.exceptions import CommandExecutionError
from tests.support.mock import patch


pytest.importorskip("win32api", reason="System is not Windows.")


class DummyStat:
    st_mode = 33188
    st_ino = 115331251
    st_dev = 44
    st_nlink = 1
    st_uid = 99200001
    st_gid = 99200001
    st_size = 41743
    st_atime = 1552661253
    st_mtime = 1552661253
    st_ctime = 1552661253


@pytest.fixture
def fake_path():
    if salt.utils.platform.is_windows():
        FAKE_PATH = os.sep.join(["C:", "path", "does", "not", "exist"])
    else:
        FAKE_PATH = os.sep.join(["path", "does", "not", "exist"])
    yield FAKE_PATH


@pytest.fixture
def fake_ret():
    yield {"fake": "ret data"}


@pytest.fixture
def curr_user():
    yield salt.utils.win_functions.get_current_user(False)


@pytest.fixture(scope="function")
def setup_teardown_vars(tmp_path, curr_user):
    temp_file = temp.file(parent=tmp_path)
    win_dacl.set_owner(obj_name=temp_file, principal=curr_user)
    win_dacl.set_inheritance(obj_name=temp_file, enabled=True)
    assert win_dacl.get_owner(obj_name=temp_file) == curr_user
    try:
        yield temp_file
    finally:
        os.remove(temp_file)


@pytest.fixture
def configure_loader_modules():
    return {
        win_file: {
            "__utils__": {
                "dacl.check_perms": win_dacl.check_perms,
                "dacl.set_perms": win_dacl.set_perms,
                "files.normalize_mode": salt.utils.files.normalize_mode,
                "path.islink": salt.utils.path.islink,
                "dacl.get_name": win_dacl.get_name,
            }
        },
        win_dacl: {"__opts__": {"test": False}},
    }


def test_issue_43328_stats(fake_path):
    """
    Make sure that a CommandExecutionError is raised if the file does NOT
    exist
    """
    with patch("os.path.exists", return_value=False):
        pytest.raises(CommandExecutionError, win_file.stats, fake_path)


def test_issue_43328_check_perms_no_ret(fake_path):
    """
    Make sure that a CommandExecutionError is raised if the file does NOT
    exist
    """
    with patch("os.path.exists", return_value=False):
        pytest.raises(
            CommandExecutionError, win_file.check_perms, fake_path
        )


def test_issue_52002_check_file_remove_symlink(tmp_path):
    """
    Make sure that directories including symlinks or symlinks can be removed
    """
    base = str(tmp_path / "base-")
    target = os.path.join(base, "child 1", "target\\")
    symlink = os.path.join(base, "child 2", "link")
    try:
        # Create environment
        assert win_file.directory_exists(target) is False
        assert win_file.directory_exists(symlink) is False
        assert win_file.makedirs_(target) is True
        assert win_file.makedirs_(symlink) is True
        assert win_file.symlink(target, symlink) is True
        assert win_file.directory_exists(symlink) is True
        assert win_file.is_link(symlink) is True
        # Test removal of directory containing symlink
        assert win_file.remove(base) is True
        assert win_file.directory_exists(base) is False
    finally:
        if os.path.exists(base):
            win_file.remove(base)


def test_check_perms_set_owner_test_true(setup_teardown_vars):
    """
    Test setting the owner of a file with test=True
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"owner": "Administrators"},
        "name": temp_file,
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        ret = win_file.check_perms(path=temp_file, owner="Administrators", inheritance=None)
        assert ret == expected


def test_check_perms_set_owner(setup_teardown_vars):
    """
    Test setting the owner of a file
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"owner": "Administrators"},
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(
        path=temp_file, owner="Administrators", inheritance=None
    )
    assert ret == expected


def test_check_perms_deny_test_true(setup_teardown_vars):
    """
    Test setting deny perms on a file with test=True
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"deny_perms": {"Users": {"permissions": "read_execute"}}},
        "name": temp_file,
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        ret = win_file.check_perms(
            path=temp_file,
            deny_perms={"Users": {"perms": "read_execute"}},
            inheritance=None,
        )
        assert ret == expected


def test_check_perms_deny(setup_teardown_vars):
    """
    Test setting deny perms on a file
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"deny_perms": {"Users": {"permissions": "read_execute"}}},
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(
        path=temp_file,
        deny_perms={"Users": {"perms": "read_execute"}},
        inheritance=None,
    )
    assert ret == expected


def test_check_perms_grant_test_true(setup_teardown_vars):
    """
    Test setting grant perms on a file with test=True
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"grant_perms": {"Users": {"permissions": "read_execute"}}},
        "name": temp_file,
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        ret = win_file.check_perms(
            path=temp_file,
            grant_perms={"Users": {"perms": "read_execute"}},
            inheritance=None,
        )
        assert ret == expected


def test_check_perms_grant(setup_teardown_vars):
    """
    Test setting grant perms on a file
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"grant_perms": {"Users": {"permissions": "read_execute"}}},
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(
        path=temp_file,
        grant_perms={"Users": {"perms": "read_execute"}},
        inheritance=None,
    )
    assert ret == expected


def test_check_perms_validate():
    """
    Test validate helper function
    """
    grant_perms = {
        "user_does_not_exist": {
            "perms": {
                "read_attributes",
                "create_folders"
            }
        }
    }
    ret = win_file._validate_users(grant_perms)
    assert ret is False


def test_check_perms_validate_true():
    """
    Test validate helper function when user does exist
    """
    grant_perms = {
        "Administrator": {
            "perms": {
                "read_attributes",
                "create_folders"
            }
        }
    }
    ret = win_file._validate_users(grant_perms)
    assert ret is True


def test_check_perms_inheritance_false_test_true(setup_teardown_vars):
    """
    Test setting inheritance to False with test=True
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"inheritance": False},
        "name": temp_file,
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        ret = win_file.check_perms(path=temp_file, inheritance=False)
        assert ret == expected


def test_check_perms_inheritance_false(setup_teardown_vars):
    """
    Test setting inheritance to False
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {"inheritance": False},
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(path=temp_file, inheritance=False)
    assert ret == expected


def test_check_perms_inheritance_true(setup_teardown_vars):
    """
    Test setting inheritance to true when it's already true (default)
    """
    temp_file = setup_teardown_vars
    expected = {
        "comment": "",
        "changes": {},
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(path=temp_file, inheritance=True)
    assert ret == expected


def test_check_perms_reset_test_true(setup_teardown_vars):
    """
    Test resetting perms with test=True. This shows minimal changes
    """
    temp_file = setup_teardown_vars
    # Turn off inheritance
    win_dacl.set_inheritance(obj_name=temp_file, enabled=False, clear=True)
    # Set some permissions
    win_dacl.set_permissions(
        obj_name=temp_file,
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
                        "applies to": "Not Inherited (file)",
                        "permissions": "Full control",
                    }
                }
            },
        },
        "name": temp_file,
        "result": None,
    }
    with patch.dict(win_dacl.__opts__, {"test": True}):
        ret = win_file.check_perms(
            path=temp_file,
            grant_perms={
                "Users": {"perms": "read_execute"},
                "Administrators": {"perms": "full_control"},
            },
            inheritance=False,
            reset=True,
        )
        assert ret == expected


def test_check_perms_reset(setup_teardown_vars):
    """
    Test resetting perms on a File
    """
    temp_file = setup_teardown_vars
    # Turn off inheritance
    win_dacl.set_inheritance(obj_name=temp_file, enabled=False, clear=True)
    # Set some permissions
    win_dacl.set_permissions(
        obj_name=temp_file,
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
                        "applies to": "Not Inherited (file)",
                        "permissions": "Full control",
                    }
                }
            },
        },
        "name": temp_file,
        "result": True,
    }
    ret = win_file.check_perms(
        path=temp_file,
        grant_perms={
            "Users": {"perms": "read_execute"},
            "Administrators": {"perms": "full_control"},
        },
        inheritance=False,
        reset=True,
    )
    assert ret == expected


def test_stat():
    with patch("os.path.exists", MagicMock(return_value=True)), patch(
        "salt.modules.win_file._resolve_symlink",
        MagicMock(side_effect=lambda path: path),
    ), patch("salt.modules.win_file.get_uid", MagicMock(return_value=1)), patch(
        "salt.modules.win_file.uid_to_user", MagicMock(return_value="dummy")
    ), patch(
        "salt.modules.win_file.get_pgid", MagicMock(return_value=1)
    ), patch(
        "salt.modules.win_file.gid_to_group", MagicMock(return_value="dummy")
    ), patch(
        "os.stat", MagicMock(return_value=DummyStat())
    ):
        ret = win_file.stats("dummy", None, True)
        assert ret["mode"] == "0644"
        assert ret["type"] == "file"
