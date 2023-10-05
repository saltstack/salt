import os

import pytest

import salt.utils.files
import salt.utils.user
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
            "__opts__": minion_opts,
            "__salt__": modules,
            "__utils__": utils,
        },
    }


@pytest.fixture
def user():
    return salt.utils.user.get_user()


@pytest.mark.flaky_jail
def test_symlink(tmp_path): # TODO only test when priv are given
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


def test_is_link_false(tmp_path):
    tmp_path = str(tmp_path)
    assert win_file.is_link(tmp_path) is False
    assert win_file.is_link(os.path.join(tmp_path, "made_up_path")) is False


def test_mkdir(tmp_path):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    assert win_file.mkdir(path) is True
    assert os.path.isdir(path)


def test_user(tmp_path, user):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    assert win_file.mkdir(path, owner=user) is True
    assert os.path.isdir(path)
    assert win_file.get_user(path) in user


def test_fake_user(tmp_path, user):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    user = user + "_fake"
    with pytest.raises(CommandExecutionError):
        win_file.mkdir(path, owner=user)


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
    assert attributes["archive"] == True
    assert attributes["reparsePoint"] == False
    assert attributes["compressed"] == False
    assert attributes["directory"] == False
    assert attributes["encrypted"] == False
    assert attributes["hidden"] == False
    assert attributes["normal"] == False
    assert attributes["notIndexed"] == False
    assert attributes["offline"] == False
    assert attributes["readonly"] == False
    assert attributes["system"] == False
    assert attributes["temporary"] == False
    assert attributes["mountedVolume"] == False
    assert attributes["symbolicLink"] == False


def test_set_attributes(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.set_attributes(
        file,
        archive=True,
        hidden=True,
        normal=False,
        notIndexed=True,
        readonly=True,
        system=True,
        temporary=True) is True
    attributes = win_file.get_attributes(file)
    assert attributes["archive"] is True
    assert attributes["hidden"] is True
    assert attributes["normal"] is False
    assert attributes["notIndexed"] is True
    assert attributes["readonly"] is True
    assert attributes["system"] is True
    assert attributes["temporary"] is True
    assert win_file.set_attributes(
        file,
        archive=False,
        hidden=False,
        normal=True,
        notIndexed=False,
        readonly=False,
        system=False,
        temporary=False) is True
    attributes = win_file.get_attributes(file)
    assert attributes["archive"] is False
    assert attributes["hidden"] is False
    assert attributes["normal"] is True
    assert attributes["notIndexed"] is False
    assert attributes["readonly"] is False
    assert attributes["system"] is False
    assert attributes["temporary"] is False

def test_remove(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.remove(file) is True

def test_remove_force(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file, "w"):
        pass
    assert os.path.isfile(file) is True
    assert win_file.remove(file, force=True) is True
