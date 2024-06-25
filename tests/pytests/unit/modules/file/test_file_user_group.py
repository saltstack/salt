import logging
import os

import pytest

import salt.modules.file as filemod

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {filemod: {}}


@pytest.fixture
def user_account():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


def test_gid_to_group(user_account):
    """
    test basic functionality of file.gid_to_group
    """
    ret = filemod.gid_to_group(user_account.info.gid)
    assert ret == user_account.group_name


def test_gid_to_group_non_int(user_account):
    """
    test file.gid_to_group when group is not an int
    """
    ret = filemod.gid_to_group(user_account.group_name)
    assert ret == user_account.group_name


def test_gid_to_group_none(user_account):
    """
    test file.gid_to_group when group is nothing
    """
    ret = filemod.gid_to_group("")
    assert ret == ""


def test_get_gid(user_account, tmp_path):
    """
    test basic functionality of get_gid
    """
    path = tmp_path / "path"
    path.write_text("")
    os.chown(path, user_account.info.uid, user_account.info.gid)
    ret = filemod.get_gid(path)
    assert ret == user_account.info.gid


def test_get_uid(user_account, tmp_path):
    """
    test basic functionality of get_uid
    """
    path = tmp_path / "path"
    path.write_text("")
    os.chown(path, user_account.info.uid, user_account.info.gid)
    ret = filemod.get_uid(path)
    assert ret == user_account.info.uid


def test_lchown_user_group_doesnotexist(tmp_path):
    """
    test lchown when the user and group does not exist
    """
    path = tmp_path / "path"
    user = "doesnotexist"
    group = "groupdoesntexist"
    ret = filemod.lchown(path, user, group)
    assert ret == "User does not exist\nGroup does not exist\n"
