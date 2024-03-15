"""
:codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import os

import pytest

import salt.modules.win_path as win_path
import salt.utils.stringutils
import salt.utils.win_reg as reg_util
from tests.support.mock import MagicMock, patch

pytestmark = [pytest.mark.windows_whitelisted, pytest.mark.skip_unless_on_windows]

"""
Test cases for salt.modules.win_path.
"""


@pytest.fixture()
def pathsep():
    return ";"


@pytest.fixture
def configure_loader_modules():
    return {
        win_path: {
            "__opts__": {"test": False},
            "__salt__": {},
            "__utils__": {"reg.read_value": reg_util.read_value},
        },
    }


def test_get_path():
    """
    Test to return the system path
    """
    mock = MagicMock(return_value={"vdata": "C:\\Salt"})
    with patch.dict(win_path.__utils__, {"reg.read_value": mock}):
        assert win_path.get_path() == ["C:\\Salt"]


def test_exists():
    """
    Test to check if the directory is configured
    """
    mock = MagicMock(return_value=["C:\\Foo", "C:\\Bar"])
    with patch.object(win_path, "get_path", mock):
        # Ensure case insensitivity respected
        assert (win_path.exists("C:\\FOO")) is True
        assert (win_path.exists("c:\\foo")) is True
        assert (win_path.exists("c:\\mystuff")) is False


def test_util_reg():
    """
    Test to check if registry comes back clean when get_path is called
    """
    mock = MagicMock(return_value={"vdata": ""})
    with patch.dict(win_path.__utils__, {"reg.read_value": mock}):
        assert win_path.get_path() == []


def test_add(pathsep):
    """
    Test to add the directory to the SYSTEM path
    """
    orig_path = ("C:\\Foo", "C:\\Bar")

    # Helper function to make the env var easier to reuse
    def _env(path):
        return {"PATH": salt.utils.stringutils.to_str(pathsep.join(path))}

    # Helper function to make the run call easier to reuse
    def _run(name, index=None, retval=True, path=None):
        if path is None:
            path = orig_path
        env = _env(path)
        # Mock getters and setters
        mock_get = MagicMock(return_value=list(path))
        mock_set = MagicMock(return_value=retval)

        # Mock individual calls that would occur during normal usage
        patch_sep = patch.object(win_path, "PATHSEP", pathsep)
        patch_path = patch.object(win_path, "get_path", mock_get)
        patch_env = patch.object(os, "environ", env)
        patch_dict = patch.dict(win_path.__utils__, {"reg.set_value": mock_set})
        patch_rehash = patch.object(win_path, "rehash", MagicMock(return_value=True))

        with patch_sep, patch_path, patch_env, patch_dict, patch_rehash:
            return win_path.add(name, index), env, mock_set

    def _path_matches(path):
        return salt.utils.stringutils.to_str(pathsep.join(path))

    # Test an empty reg update
    ret, env, mock_set = _run("")
    assert ret is False

    # Test a successful reg update
    ret, env, mock_set = _run("c:\\salt", retval=True)
    new_path = ("C:\\Foo", "C:\\Bar", "c:\\salt")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test an unsuccessful reg update
    ret, env, mock_set = _run("c:\\salt", retval=False)
    new_path = ("C:\\Foo", "C:\\Bar", "c:\\salt")
    assert ret is False
    assert env["PATH"] == _path_matches(new_path)

    # Test adding with a custom index
    ret, env, mock_set = _run("c:\\salt", index=1, retval=True)
    new_path = ("C:\\Foo", "c:\\salt", "C:\\Bar")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test adding with a custom index of 0
    ret, env, mock_set = _run("c:\\salt", index=0, retval=True)
    new_path = ("c:\\salt", "C:\\Foo", "C:\\Bar")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test adding path with a case-insensitive match already present, and
    # no index provided. The path should remain unchanged and we should not
    # update the registry.
    ret, env, mock_set = _run("c:\\foo", retval=True)
    assert ret is True
    assert env["PATH"] == _path_matches(orig_path)

    # Test adding path with a case-insensitive match already present, and a
    # negative index provided which does not match the current index. The
    # match should be removed, and the path should be added to the end of
    # the list.
    ret, env, mock_set = _run("c:\\foo", index=-1, retval=True)
    new_path = ("C:\\Bar", "c:\\foo")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test adding path with a case-insensitive match already present, and a
    # negative index provided which matches the current index. No changes
    # should be made.
    ret, env, mock_set = _run("c:\\foo", index=-2, retval=True)
    assert ret is True
    assert env["PATH"] == _path_matches(orig_path)

    # Test adding path with a case-insensitive match already present, and a
    # negative index provided which is larger than the size of the list. No
    # changes should be made, since in these cases we assume an index of 0,
    # and the case-insensitive match is also at index 0.
    ret, env, mock_set = _run("c:\\foo", index=-5, retval=True)
    assert ret is True
    assert env["PATH"] == _path_matches(orig_path)

    # Test adding path with a case-insensitive match already present, and a
    # negative index provided which is larger than the size of the list.
    # The match should be removed from its current location and inserted at
    # the beginning, since when a negative index is larger than the list,
    # we put it at the beginning of the list.
    ret, env, mock_set = _run("c:\\bar", index=-5, retval=True)
    new_path = ("c:\\bar", "C:\\Foo")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test adding path with a case-insensitive match already present, and a
    # negative index provided which matches the current index. The path
    # should remain unchanged and we should not update the registry.
    ret, env, mock_set = _run("c:\\bar", index=-1, retval=True)
    assert ret is True
    assert env["PATH"] == _path_matches(orig_path)

    # Test adding path with a case-insensitive match already present, and
    # an index provided which does not match the current index, and is also
    # larger than the size of the PATH list. The match should be removed,
    # and the path should be added to the end of the list.
    ret, env, mock_set = _run("c:\\foo", index=5, retval=True)
    new_path = ("C:\\Bar", "c:\\foo")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)


def test_remove(pathsep):
    """
    Test win_path.remove
    """
    orig_path = ("C:\\Foo", "C:\\Bar", "C:\\Baz")

    # Helper function to make the env var easier to reuse
    def _env(path):
        return {"PATH": salt.utils.stringutils.to_str(pathsep.join(path))}

    def _run(name="c:\\salt", retval=True, path=None):
        if path is None:
            path = orig_path
        env = _env(path)
        # Mock getters and setters
        mock_get = MagicMock(return_value=list(path))
        mock_set = MagicMock(return_value=retval)

        patch_path_sep = patch.object(win_path, "PATHSEP", pathsep)
        patch_path = patch.object(win_path, "get_path", mock_get)
        patch_env = patch.object(os, "environ", env)
        patch_dict = patch.dict(win_path.__utils__, {"reg.set_value": mock_set})
        patch_rehash = patch.object(win_path, "rehash", MagicMock(return_value=True))
        with patch_path_sep, patch_path, patch_env, patch_dict, patch_rehash:
            return win_path.remove(name), env, mock_set

    def _path_matches(path):
        return salt.utils.stringutils.to_str(pathsep.join(path))

    # Test a successful reg update
    ret, env, mock_set = _run("C:\\Bar", retval=True)
    new_path = ("C:\\Foo", "C:\\Baz")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test a successful reg update with a case-insensitive match
    ret, env, mock_set = _run("c:\\bar", retval=True)
    new_path = ("C:\\Foo", "C:\\Baz")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test a successful reg update with multiple case-insensitive matches.
    # All matches should be removed.
    old_path = orig_path + ("C:\\BAR",)
    ret, env, mock_set = _run("c:\\bar", retval=True)
    new_path = ("C:\\Foo", "C:\\Baz")
    assert ret is True
    assert env["PATH"] == _path_matches(new_path)

    # Test an unsuccessful reg update
    ret, env, mock_set = _run("c:\\bar", retval=False)
    new_path = ("C:\\Foo", "C:\\Baz")
    assert ret is False
    # The local path should still have been modified even
    # though reg.set_value failed.
    assert env["PATH"] == _path_matches(new_path)

    # Test when no match found
    ret, env, mock_set = _run("C:\\NotThere", retval=True)
    assert ret is True
    assert env["PATH"] == _path_matches(orig_path)
