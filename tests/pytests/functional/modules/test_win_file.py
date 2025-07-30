import ctypes
import os
import platform

import pytest

import salt.modules.win_useradd
import salt.utils.files
from salt.exceptions import CommandExecutionError
from salt.modules import win_file

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules(minion_opts, modules):
    utils = salt.loader.utils(minion_opts)
    return {
        win_file: {
            "__salt__": modules,
            "__utils__": utils,
        },
    }


skip_not_windows_admin = pytest.mark.skipif(
    platform.system() != "Windows" or not ctypes.windll.shell32.IsUserAnAdmin(),
    reason="user needs windows admin rights",
)


@pytest.fixture
def windows_user():
    return salt.modules.win_useradd.current()


@skip_not_windows_admin
def test_symlink(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    link = tmp_path / "l"
    assert win_file.is_link(str(link)) is False
    assert win_file.symlink(str(file), str(link)) is True
    assert file.is_file() is True
    assert win_file.is_link(str(link)) is True


@skip_not_windows_admin
def test_symlink_path_taken(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    link = tmp_path / "l"
    link.touch()
    assert link.is_file() is True
    # symlink should raise error if path name is all ready taken
    pytest.raises(CommandExecutionError, win_file.symlink, str(file), str(link))


@skip_not_windows_admin
def test_symlink_force(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    link = tmp_path / "l"
    assert win_file.is_link(str(link)) is False
    assert win_file.symlink(str(file), str(link), force=True) is True
    assert file.is_file() is True
    assert win_file.is_link(str(link)) is True
    # check that symlink returns ture if link is all ready-made
    assert win_file.symlink(str(file), str(link), force=True) is True


@skip_not_windows_admin
def test_symlink_atomic(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    link = tmp_path / "l"
    assert win_file.is_link(str(link)) is False
    assert win_file.symlink(str(file), str(link), force=True, atomic=True) is True
    assert file.is_file() is True
    assert win_file.is_link(str(link)) is True
    # check that symlink returns ture if link is all ready-made
    assert win_file.symlink(str(file), str(link), force=True, atomic=True) is True


def test_is_not_link(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.is_link(tmp_path) is False
    assert win_file.is_link(os.path.join(tmp_path, "made_up_path")) is False


@skip_not_windows_admin
def test__resolve_symlink(tmp_path):
    link = tmp_path / "l"
    assert win_file.symlink(str(tmp_path), str(link)) is True
    assert win_file._resolve_symlink(str(link)) == str(tmp_path)


def test_get_user(tmp_path, windows_user):
    path = tmp_path / "dir"
    assert win_file.mkdir(str(path), owner=windows_user) is True
    assert path.is_dir() is True
    assert win_file.get_user(str(path)) in windows_user


def test_fake_user(tmp_path, windows_user):
    path = tmp_path / "dir"
    windows_user = windows_user + "_fake"
    pytest.raises(
        CommandExecutionError,
        win_file.mkdir,
        str(path),
        owner=windows_user,
    )


def test_uid_user(tmp_path):
    path = str(tmp_path)
    uid = win_file.get_uid(path)
    assert "-" in uid
    assert win_file.user_to_uid(win_file.uid_to_user(uid)) == uid


def test_uid_to_user_none(tmp_path):
    assert win_file.uid_to_user(None) == ""


def test_gid_group(tmp_path, windows_user):
    path = str(tmp_path)
    gid = win_file.get_gid(path)
    assert isinstance(gid, str)
    group = win_file.get_group(path)
    assert isinstance(group, str)
    assert win_file.gid_to_group(gid) == group
    assert win_file.group_to_gid(group) == gid


def test_gid_group_none(tmp_path):
    assert win_file.group_to_gid(None) == ""


def test_get_pgroup(tmp_path):
    path = str(tmp_path)
    pgroup = win_file.get_pgroup(path)
    assert pgroup == "None"


def test_get_pgid(tmp_path):
    path = str(tmp_path)
    pgid = win_file.get_pgid(path)
    assert "-" in pgid


def test_get_uid_path_not_found(tmp_path):
    path = tmp_path / "dir"
    pytest.raises(CommandExecutionError, win_file.get_uid, str(path))


def test_get_user_path_not_found(tmp_path):
    path = tmp_path / "dir"
    pytest.raises(CommandExecutionError, win_file.get_user, str(path))


def test_mode(tmp_path):
    assert win_file.get_mode(str(tmp_path)) is None


def test_mode_path_not_found(tmp_path):
    path = tmp_path / "dir"
    pytest.raises(CommandExecutionError, win_file.get_mode, str(path))


def test_lchown(tmp_path, windows_user):
    assert win_file.lchown(str(tmp_path), windows_user) is True
    assert win_file.get_user(str(tmp_path)) == windows_user


def test_chown(tmp_path, windows_user):
    assert win_file.chown(str(tmp_path), windows_user) is True
    assert win_file.get_user(str(tmp_path)) == windows_user


def test_chpgrp(tmp_path):
    assert win_file.chpgrp(str(tmp_path), "Administrators") is True
    assert win_file.get_pgroup(str(tmp_path)) == "Administrators"


def test_chgrp(tmp_path):
    assert win_file.chgrp(str(tmp_path), "Administrators") is None


def test_stats(tmp_path, windows_user):
    stats = win_file.stats(str(tmp_path))
    assert isinstance(stats, dict)
    assert stats["type"] == "dir"
    assert isinstance(stats["inode"], int)
    assert isinstance(stats["uid"], str)
    assert isinstance(stats["gid"], str)
    assert isinstance(stats["user"], str)
    assert isinstance(stats["group"], str)
    assert isinstance(stats["pgroup"], str)
    assert isinstance(stats["atime"], (float, int))
    assert isinstance(stats["mtime"], (float, int))
    assert isinstance(stats["ctime"], (float, int))
    assert isinstance(stats["size"], int)
    assert isinstance(stats["mode"], str)
    assert isinstance(stats["target"], str)


def test_stats_path_not_found(tmp_path, windows_user):
    path = tmp_path / "dir"
    pytest.raises(CommandExecutionError, win_file.stats, str(path))


def test_version():
    assert len(win_file.version("C:\\Windows\\System32\\cmd.exe").split(".")) == 4


def test_version_empty(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    assert win_file.version(str(file)) == ""


def test_version_path_not_found(tmp_path):
    file = tmp_path / "t.txt"
    assert file.is_file() is False
    pytest.raises(CommandExecutionError, win_file.version, str(file))


def test_version_dir(tmp_path):
    path = tmp_path / "dir"
    path.mkdir()
    pytest.raises(CommandExecutionError, win_file.version, str(path))


def test_version_details():
    details = win_file.version_details("C:\\Windows\\System32\\cmd.exe")
    assert isinstance(details, dict) is True
    assert details["Comments"] is None
    assert details["CompanyName"] == "Microsoft Corporation"
    assert isinstance(details["FileDescription"], str) is True


def test_get_attributes(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    attributes = win_file.get_attributes(str(file))
    assert isinstance(attributes, dict) is True
    assert attributes["archive"] is True
    assert attributes["reparsePoint"] is False
    assert attributes["compressed"] is False
    assert attributes["directory"] is False
    assert attributes["encrypted"] is False
    assert attributes["hidden"] is False
    assert attributes["normal"] is False
    assert attributes["notIndexed"] is False
    assert attributes["offline"] is False
    assert attributes["readonly"] is False
    assert attributes["system"] is False
    assert attributes["temporary"] is False
    assert attributes["mountedVolume"] is False
    assert attributes["symbolicLink"] is False


def test_set_attributes(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    assert (
        win_file.set_attributes(
            str(file),
            archive=True,
            hidden=True,
            normal=False,
            notIndexed=True,
            readonly=True,
            system=True,
            temporary=True,
        )
        is True
    )
    attributes = win_file.get_attributes(str(file))
    assert attributes["archive"] is True
    assert attributes["hidden"] is True
    assert attributes["normal"] is False
    assert attributes["notIndexed"] is True
    assert attributes["readonly"] is True
    assert attributes["system"] is True
    assert attributes["temporary"] is True
    assert (
        win_file.set_attributes(
            str(file),
            archive=False,
            hidden=False,
            normal=True,
            notIndexed=False,
            readonly=False,
            system=False,
            temporary=False,
        )
        is True
    )
    attributes = win_file.get_attributes(str(file))
    assert attributes["archive"] is False
    assert attributes["hidden"] is False
    assert attributes["normal"] is True
    assert attributes["notIndexed"] is False
    assert attributes["readonly"] is False
    assert attributes["system"] is False
    assert attributes["temporary"] is False


def test_set_mode(tmp_path):
    assert win_file.set_mode(str(tmp_path), "") is None


def test_remove(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    assert win_file.remove(str(file)) is True
    assert file.is_file() is False


def test_remove_force(tmp_path):
    file = tmp_path / "t.txt"
    file.touch()
    assert file.is_file() is True
    assert win_file.remove(str(file), force=True) is True
    assert file.is_file() is False


def test_mkdir(tmp_path):
    path = tmp_path / "dir"
    assert path.is_dir() is False
    assert win_file.mkdir(str(path)) is True
    assert path.is_dir() is True


def test_mkdir_error(tmp_path):
    # dirs can't contain illegal characters on Windows
    illegal_name = "illegal*name"
    path = tmp_path / illegal_name
    pytest.raises(CommandExecutionError, win_file.mkdir, str(path))
    assert path.is_dir() is False

    # cant make dir if parent is not made
    path = tmp_path / "a" / "b" / "c" / "salt"
    pytest.raises(CommandExecutionError, win_file.mkdir, str(path))
    assert path.is_dir() is False


def test_makedirs_(tmp_path):
    parent = tmp_path / "dir1" / "dir2"
    path = parent / "dir3"
    assert win_file.makedirs_(str(path)) is True
    assert parent.is_dir() is True
    assert path.is_dir() is False


def test_makedirs__path_exists(tmp_path):
    parent = tmp_path / "dir1" / "dir2"
    path = parent / "dir3"
    parent.mkdir(parents=True)
    assert parent.is_dir() is True
    # makedirs_ should return message that path already exists
    result = win_file.makedirs_(str(path))
    assert "already exists" in result


def test_makedirs_perms(tmp_path):
    path = tmp_path / "dir1" / "dir2"
    assert win_file.makedirs_perms(str(path)) is True
    assert path.is_dir() is True
    # make sure makedirs does not fail if path exists
    assert win_file.makedirs_perms(str(path)) is True
    assert path.is_dir() is True


def test_check_perms_path_not_found(tmp_path, windows_user):
    path = tmp_path / "dir1"
    assert path.is_dir() is False
    # check_perms will fail due to path not being made
    pytest.raises(
        CommandExecutionError, win_file.check_perms, str(path), {}, windows_user
    )


def test_set_perms(tmp_path, windows_user):
    perms = {windows_user: {"perms": "read_execute", "applies_to": "this_folder_only"}}
    expected = {
        "grant": {
            windows_user: {"applies_to": "this_folder_only", "perms": "read_execute"}
        }
    }
    result = win_file.set_perms(str(tmp_path), grant_perms=perms)
    assert result == expected
