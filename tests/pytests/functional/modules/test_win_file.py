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
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    link = os.path.join(tmp_path, "l")
    assert win_file.is_link(link) is False
    win_file.symlink(file, link, force=True)
    assert os.path.isfile(file) is True
    assert win_file.is_link(link) is True


@skip_not_windows_admin
def test_symlink_atomic(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    link = os.path.join(tmp_path, "l")
    assert win_file.is_link(link) is False
    win_file.symlink(file, link, force=True, atomic=True)
    assert os.path.isfile(file) is True
    assert win_file.is_link(link) is True


def test_is_not_link(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.is_link(tmp_path) is False
    assert win_file.is_link(os.path.join(tmp_path, "made_up_path")) is False


def test_get_user(tmp_path, windows_user):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    assert win_file.mkdir(path, owner=windows_user) is True
    assert os.path.isdir(path)
    assert win_file.get_user(path) in windows_user


def test_fake_user(tmp_path, windows_user):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    windows_user = windows_user + "_fake"
    with pytest.raises(CommandExecutionError):
        win_file.mkdir(path, owner=windows_user)


def test_uid_user(tmp_path):
    path = str(tmp_path)
    uid = win_file.get_uid(path)
    assert "-" in uid
    assert win_file.user_to_uid(win_file.uid_to_user(uid)) == uid


def test_gid_group(tmp_path, windows_user):
    path = str(tmp_path)
    gid = win_file.get_gid(path)
    assert isinstance(gid, str)
    group = win_file.get_group(path)
    assert isinstance(group, str)
    assert win_file.gid_to_group(gid) == group
    assert win_file.group_to_gid(group) == gid


def test_get_pgroup(tmp_path):
    path = str(tmp_path)
    pgroup = win_file.get_pgroup(path)
    assert pgroup == "None"


def test_get_pgid(tmp_path):
    path = str(tmp_path)
    pgid = win_file.get_pgid(path)
    assert "-" in pgid


def test_mode(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.get_mode(tmp_path) is None


def test_lchown(tmp_path, windows_user):
    path = str(tmp_path)
    assert win_file.lchown(path, windows_user) is True
    assert win_file.get_user(path) == windows_user


def test_chown(tmp_path, windows_user):
    path = str(tmp_path)
    assert win_file.chown(path, windows_user) is True
    assert win_file.get_user(path) == windows_user


def test_chpgrp(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.chpgrp(tmp_path, "Administrators") is True
    assert win_file.get_pgroup(tmp_path) == "Administrators"


def test_chgrp(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.chgrp(tmp_path, "Administrators") is None


def test_stats(tmp_path, windows_user):
    tmp_path = str(tmp_path)
    stats = win_file.stats(tmp_path)
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


def test_version():
    assert len(win_file.version("C:\\Windows\\System32\\wow64.dll").split(".")) == 4


def test_version_empty(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.version(file) == ""


def test_version_details():
    details = win_file.version_details("C:\\Windows\\System32\\wow64.dll")
    assert isinstance(details, dict) is True
    assert details["Comments"] is None
    assert details["CompanyName"] == "Microsoft Corporation"
    assert isinstance(details["FileDescription"], str) is True


def test_get_attributes(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    attributes = win_file.get_attributes(file)
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
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert (
        win_file.set_attributes(
            file,
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
    attributes = win_file.get_attributes(file)
    assert attributes["archive"] is True
    assert attributes["hidden"] is True
    assert attributes["normal"] is False
    assert attributes["notIndexed"] is True
    assert attributes["readonly"] is True
    assert attributes["system"] is True
    assert attributes["temporary"] is True
    assert (
        win_file.set_attributes(
            file,
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
    attributes = win_file.get_attributes(file)
    assert attributes["archive"] is False
    assert attributes["hidden"] is False
    assert attributes["normal"] is True
    assert attributes["notIndexed"] is False
    assert attributes["readonly"] is False
    assert attributes["system"] is False
    assert attributes["temporary"] is False


def test_set_mode(tmp_path):
    path = str(tmp_path)
    assert win_file.set_mode(path, "") is None


def test_remove(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.remove(file) is True
    assert os.path.isfile(file) is False


def test_remove_force(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.remove(file, force=True) is True
    assert os.path.isfile(file) is False


def test_mkdir(tmp_path):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    assert win_file.mkdir(path) is True
    assert os.path.isdir(path)


def test_makedirs_(tmp_path):
    tmp_path = str(tmp_path)
    parent = os.path.join(tmp_path, "dir1\\dir2")
    path = os.path.join(parent, "dir3")
    assert win_file.makedirs_(path) is True
    assert os.path.isdir(parent) is True
    assert os.path.isdir(path) is False


def test_makedirs_perms(tmp_path):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir1\\dir2")
    assert win_file.makedirs_perms(path) is True
    assert os.path.isdir(path)


def test_check_perms(tmp_path, windows_user):
    path = str(tmp_path)
    ret = {}
    perms = win_file.check_perms(path, ret, windows_user)
    assert ret == {}
    assert perms["comment"] == ""
    assert isinstance(perms["changes"], dict)
    assert isinstance(perms["name"], str) and len(perms["name"]) != 0
    assert perms["result"] is True


def test_set_perms(tmp_path):
    path = str(tmp_path)
    assert win_file.set_perms(path) == {}