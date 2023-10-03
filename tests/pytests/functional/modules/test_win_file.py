import os

import pytest

import salt.utils.files
import salt.utils.user
from salt.exceptions import CommandExecutionError
from salt.modules import win_file

pytestmark = [
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def user():
    return salt.utils.user.get_user()


def test_is_link(tmp_path):
    tmp_path = str(tmp_path)
    assert (
        win_file.is_link(tmp_path) is True
    )  # THIS should be false TODO make bug report
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
    assert win_file.get_user(path) == user
    assert win_file.get_group(path) == user
    assert isinstance(win_file.get_gid(path), int) is True


def test_fake_user(tmp_path, user):
    tmp_path = str(tmp_path)
    path = os.path.join(tmp_path, "dir")
    user = user + "_fake"
    with pytest.raises(CommandExecutionError):
        win_file.mkdir(path, owner=user)


def test_version(tmp_path):
    tmp_path = str(tmp_path)
    file = os.path.join(tmp_path, "t.txt")
    with salt.utils.files.fopen(file):
        pass
    assert os.path.isfile(file) is True
    assert win_file.version(file) == ""
