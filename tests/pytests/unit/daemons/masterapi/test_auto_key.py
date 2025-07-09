import contextlib
import io
import stat

import pytest

import salt.config
import salt.daemons.masterapi as masterapi
import salt.utils.platform
from tests.support.mock import MagicMock, patch


def gen_permissions(owner="", group="", others=""):
    """
    Helper method to generate file permission bits
    Usage: gen_permissions('rw', 'r', 'r')
    """
    ret = 0
    for c in owner:
        ret |= getattr(stat, f"S_I{c.upper()}USR", 0)
    for c in group:
        ret |= getattr(stat, f"S_I{c.upper()}GRP", 0)
    for c in others:
        ret |= getattr(stat, f"S_I{c.upper()}OTH", 0)
    return ret


@contextlib.contextmanager
def patch_check_permissions(
    auto_key, stats, uid=1, groups=None, is_windows=False, permissive_pki=False
):
    def os_stat_mock(filename):
        fmode = MagicMock()
        fstats = stats.get(filename, {})
        fmode.st_mode = fstats.get("mode", 0)
        fmode.st_gid = fstats.get("gid", 0)
        return fmode

    if not groups:
        groups = [uid]

    auto_key.opts["permissive_pki_access"] = permissive_pki
    if salt.utils.platform.is_windows():
        with patch("salt.utils.platform.is_windows", MagicMock(return_value=True)):
            yield
    else:
        with patch("os.stat", os_stat_mock), patch(
            "os.getuid", MagicMock(return_value=uid)
        ), patch("salt.utils.user.get_gid_list", MagicMock(return_value=groups)), patch(
            "salt.utils.platform.is_windows", MagicMock(return_value=is_windows)
        ):
            yield


@pytest.fixture
def auto_key():
    opts = salt.config.master_config(None)
    opts["user"] = "test_user"
    return masterapi.AutoKey(opts)


@pytest.fixture
def local_funcs():
    opts = salt.config.master_config(None)
    return masterapi.LocalFuncs(opts, "test-key")


def test_check_permissions_windows(auto_key):
    """
    Assert that all files are accepted on windows
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("rwx", "rwx", "rwx"),
            "gid": 2,
        },
    }
    with patch_check_permissions(auto_key, stats, uid=0, is_windows=True):
        assert auto_key.check_permissions("testfile") is True


def test_check_permissions_others_can_write(auto_key):
    """
    Assert that no file is accepted, when others can write to it
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("", "", "w"),
            "gid": 1,
        },
    }
    with patch_check_permissions(auto_key, stats, permissive_pki=True):
        if salt.utils.platform.is_windows():
            assert auto_key.check_permissions("testfile") is True
        else:
            assert auto_key.check_permissions("testfile") is False


def test_check_permissions_group_can_write_not_permissive(auto_key):
    """
    Assert that a file is accepted, when group can write to it and
    permissive_pki_access=False
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "w", ""),
            "gid": 1,
        },
    }
    with patch_check_permissions(auto_key, stats):
        if salt.utils.platform.is_windows():
            assert auto_key.check_permissions("testfile") is True
        else:
            assert auto_key.check_permissions("testfile") is False


def test_check_permissions_group_can_write_permissive(auto_key):
    """
    Assert that a file is accepted, when group can write to it and
    permissive_pki_access=True
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "w", ""),
            "gid": 1,
        },
    }

    with patch_check_permissions(auto_key, stats, permissive_pki=True):
        assert auto_key.check_permissions("testfile") is True


def test_check_permissions_group_can_write_permissive_root_in_group(auto_key):
    """
    Assert that a file is accepted, when group can write to it,
    permissive_pki_access=False, salt is root and in the file owning group
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "w", ""),
            "gid": 0,
        },
    }
    with patch_check_permissions(auto_key, stats, uid=0, permissive_pki=True):
        assert auto_key.check_permissions("testfile") is True


def test_check_permissions_group_can_write_permissive_root_not_in_group(auto_key):
    """
    Assert that no file is accepted, when group can write to it,
    permissive_pki_access=False, salt is root and **not** in the file owning
    group
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "w", ""),
            "gid": 1,
        },
    }
    with patch_check_permissions(auto_key, stats, uid=0, permissive_pki=True):
        if salt.utils.platform.is_windows():
            assert auto_key.check_permissions("testfile") is True
        else:
            assert auto_key.check_permissions("testfile") is False


def test_check_permissions_only_owner_can_write(auto_key):
    """
    Assert that a file is accepted, when only the owner can write to it
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "", ""),
            "gid": 1,
        },
    }
    with patch_check_permissions(auto_key, stats):
        assert auto_key.check_permissions("testfile") is True


def test_check_permissions_only_owner_can_write_root(auto_key):
    """
    Assert that a file is accepted, when only the owner can write to it and salt is root
    """
    stats = {
        "testfile": {
            "mode": gen_permissions("w", "", ""),
            "gid": 0,
        },
    }
    with patch_check_permissions(auto_key, stats, uid=0):
        assert auto_key.check_permissions("testfile") is True


def _test_check_autosign_grains(
    test_func,
    auto_key,
    file_content="test_value",
    file_name="test_grain",
    autosign_grains_dir="test_dir",
    permissions_ret=True,
):
    """
    Helper function for testing autosign_grains().

    Patches ``os.walk`` to return only ``file_name`` and ``salt.utils.files.fopen`` to open a
    mock file with ``file_content`` as content. Optionally sets ``opts`` values.
    Then executes test_func. The ``os.walk`` and ``salt.utils.files.fopen`` mock objects
    are passed to the function as arguments.
    """
    if autosign_grains_dir:
        auto_key.opts["autosign_grains_dir"] = autosign_grains_dir
    mock_file = io.StringIO(file_content)
    mock_dirs = [(None, None, [file_name])]

    with patch("os.walk", MagicMock(return_value=mock_dirs)) as mock_walk, patch(
        "salt.utils.files.fopen", MagicMock(return_value=mock_file)
    ) as mock_open, patch(
        "salt.daemons.masterapi.AutoKey.check_permissions",
        MagicMock(return_value=permissions_ret),
    ) as mock_permissions:
        test_func(mock_walk, mock_open, mock_permissions)


def test_check_autosign_grains_no_grains(auto_key):
    """
    Asserts that autosigning from grains fails when no grain values are passed.
    """

    def test_func(mock_walk, mock_open, mock_permissions):
        assert auto_key.check_autosign_grains(None) is False
        assert mock_walk.call_count == 0
        assert mock_open.call_count == 0
        assert mock_permissions.call_count == 0

        assert auto_key.check_autosign_grains({}) is False
        assert mock_walk.call_count == 0
        assert mock_open.call_count == 0
        assert mock_permissions.call_count == 0

    _test_check_autosign_grains(test_func, auto_key)


def test_check_autosign_grains_no_autosign_grains_dir(auto_key):
    """
    Asserts that autosigning from grains fails when the \'autosign_grains_dir\' config option
    is undefined.
    """

    def test_func(mock_walk, mock_open, mock_permissions):
        assert auto_key.check_autosign_grains({"test_grain": "test_value"}) is False
        assert mock_walk.call_count == 0
        assert mock_open.call_count == 0
        assert mock_permissions.call_count == 0

    _test_check_autosign_grains(test_func, auto_key, autosign_grains_dir=None)


def test_check_autosign_grains_accept(auto_key):
    """
    Asserts that autosigning from grains passes when a matching grain value is in an
    autosign_grain file.
    """

    def test_func(*args):
        assert auto_key.check_autosign_grains({"test_grain": "test_value"}) is True

    file_content = "#test_ignore\ntest_value"
    _test_check_autosign_grains(test_func, auto_key, file_content=file_content)


def test_check_autosign_grains_accept_not(auto_key):
    """
    Asserts that autosigning from grains fails when the grain value is not in the
    autosign_grain files.
    """

    def test_func(*args):
        assert auto_key.check_autosign_grains({"test_grain": "test_invalid"}) is False

    file_content = "#test_invalid\ntest_value"
    _test_check_autosign_grains(test_func, auto_key, file_content=file_content)


def test_check_autosign_grains_invalid_file_permissions(auto_key):
    """
    Asserts that autosigning from grains fails when the grain file has the wrong permissions.
    """

    def test_func(*args):
        assert auto_key.check_autosign_grains({"test_grain": "test_value"}) is False

    file_content = "#test_ignore\ntest_value"
    _test_check_autosign_grains(
        test_func, auto_key, file_content=file_content, permissions_ret=False
    )
