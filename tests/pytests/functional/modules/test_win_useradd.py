import pytest
from saltfactories.utils import random_string

import salt.modules.cmdmod
import salt.modules.win_useradd as user
import salt.utils.data
from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def configure_loader_modules():
    return {user: {"__salt__": {"cmd.run_all": salt.modules.cmdmod.run_all}}}


@pytest.fixture
def username_str():
    _username = random_string("test-account-", uppercase=False)
    try:
        yield _username
    finally:
        try:
            user.delete(_username, purge=True, force=True)
        except Exception:  # pylint: disable=broad-except
            # The point here is just system cleanup. It can fail if no account was created
            pass


@pytest.fixture
def username_int():
    _username = random_string("", uppercase=False, lowercase=False, digits=True)
    try:
        yield _username
    finally:
        try:
            user.delete(_username, purge=True, force=True)
        except Exception:  # pylint: disable=broad-except
            # The point here is just system cleanup. It can fail if no account was created
            pass


@pytest.fixture
def account_str(username_str):
    with pytest.helpers.create_account(username=username_str) as account:
        user.addgroup(account.username, "Users")
        yield account


@pytest.fixture
def account_int(username_int):
    with pytest.helpers.create_account(username=username_int) as account:
        user.addgroup(account.username, "Users")
        yield account


def test_add_str(username_str):
    ret = user.add(name=username_str)
    assert ret is True
    assert username_str in user.list_users()


def test_add_int(username_int):
    ret = user.add(name=username_int)
    assert ret is True
    assert username_int in user.list_users()


def test_addgroup_str(account_str):
    ret = user.addgroup(account_str.username, "Backup Operators")
    assert ret is True
    ret = user.info(account_str.username)
    assert "Backup Operators" in ret["groups"]


def test_addgroup_int(account_int):
    ret = user.addgroup(account_int.username, "Backup Operators")
    assert ret is True
    ret = user.info(account_int.username)
    assert "Backup Operators" in ret["groups"]


def test_chfullname_str(account_str):
    ret = user.chfullname(account_str.username, "New Full Name")
    assert ret is True
    ret = user.info(account_str.username)
    assert ret["fullname"] == "New Full Name"


def test_chfullname_int(account_int):
    ret = user.chfullname(account_int.username, "New Full Name")
    assert ret is True
    ret = user.info(account_int.username)
    assert ret["fullname"] == "New Full Name"


def test_chgroups_single_str(account_str):
    groups = ["Backup Operators"]
    ret = user.chgroups(account_str.username, groups=groups)
    assert ret is True
    ret = user.info(account_str.username)
    groups.append("Users")
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chgroups_single_int(account_int):
    groups = ["Backup Operators"]
    ret = user.chgroups(account_int.username, groups=groups)
    assert ret is True
    ret = user.info(account_int.username)
    groups.append("Users")
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chgroups_list_str(account_str):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_str.username, groups=groups)
    assert ret is True
    ret = user.info(account_str.username)
    groups.append("Users")
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chgroups_list_int(account_int):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_int.username, groups=groups)
    assert ret is True
    ret = user.info(account_int.username)
    groups.append("Users")
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chgroups_list_append_false_str(account_str):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_str.username, groups=groups, append=False)
    assert ret is True
    ret = user.info(account_str.username)
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chgroups_list_append_false_int(account_int):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_int.username, groups=groups, append=False)
    assert ret is True
    ret = user.info(account_int.username)
    assert salt.utils.data.compare_lists(ret["groups"], groups) == {}


def test_chhome_str(account_str):
    home = r"C:\spongebob\squarepants"
    ret = user.chhome(name=account_str.username, home=home)
    assert ret is True
    ret = user.info(name=account_str.username)
    assert ret["home"] == home


def test_chhome_int(account_int):
    home = r"C:\spongebob\squarepants"
    ret = user.chhome(name=account_int.username, home=home)
    assert ret is True
    ret = user.info(name=account_int.username)
    assert ret["home"] == home


def test_chprofile_str(account_str):
    profile = r"C:\spongebob\squarepants"
    ret = user.chprofile(name=account_str.username, profile=profile)
    assert ret is True
    ret = user.info(name=account_str.username)
    assert ret["profile"] == profile


def test_chprofile_int(account_int):
    profile = r"C:\spongebob\squarepants"
    ret = user.chprofile(name=account_int.username, profile=profile)
    assert ret is True
    ret = user.info(name=account_int.username)
    assert ret["profile"] == profile


def test_delete_str(account_str):
    ret = user.delete(name=account_str.username)
    assert ret is True
    assert user.info(name=account_str.username) == {}


def test_delete_int(account_int):
    ret = user.delete(name=account_int.username)
    assert ret is True
    assert user.info(name=account_int.username) == {}


def test_getUserSig_str(account_str):
    ret = user.getUserSid(account_str.username)
    assert ret.startswith("S-1-5")


def test_getUserSig_int(account_int):
    ret = user.getUserSid(account_int.username)
    assert ret.startswith("S-1-5")


def test_info_str(account_str):
    ret = user.info(account_str.username)
    assert ret["name"] == account_str.username
    assert ret["uid"].startswith("S-1-5")


def test_info_int(account_int):
    ret = user.info(account_int.username)
    assert ret["name"] == account_int.username
    assert ret["uid"].startswith("S-1-5")


def test_list_groups_str(account_str):
    ret = user.list_groups(account_str.username)
    assert ret == ["Users"]


def test_list_groups_int(account_int):
    ret = user.list_groups(account_int.username)
    assert ret == ["Users"]


def test_list_users():
    ret = user.list_users()
    assert "Administrator" in ret


def test_removegroup_str(account_str):
    ret = user.removegroup(account_str.username, "Users")
    assert ret is True
    ret = user.info(account_str.username)
    assert ret["groups"] == []


def test_removegroup_int(account_int):
    ret = user.removegroup(account_int.username, "Users")
    assert ret is True
    ret = user.info(account_int.username)
    assert ret["groups"] == []


def test_rename_str(account_str):
    new_name = random_string("test-account-", uppercase=False)
    ret = user.rename(name=account_str.username, new_name=new_name)
    assert ret is True
    assert new_name in user.list_users()
    # Let's set it back so that it gets cleaned up...
    ret = user.rename(name=new_name, new_name=account_str.username)
    assert ret is True


def test_rename_str_missing(account_str):
    missing = random_string("test-account-", uppercase=False)
    with pytest.raises(CommandExecutionError):
        user.rename(name=missing, new_name="spongebob")


def test_rename_str_existing(account_str):
    new_existing = random_string("test-account-", uppercase=False)
    ret = user.add(name=new_existing)
    assert ret is True
    with pytest.raises(CommandExecutionError):
        user.rename(name=account_str.username, new_name=new_existing)
    # We need to clean this up because it wasn't created in a fixture
    ret = user.delete(name=new_existing, purge=True, force=True)
    assert ret is True
    assert new_existing not in user.list_users()


def test_rename_int(account_int):
    new_name = random_string("", uppercase=False, lowercase=False, digits=True)
    ret = user.rename(name=account_int.username, new_name=new_name)
    assert ret is True
    assert new_name in user.list_users()
    # Let's set it back so that it gets cleaned up...
    ret = user.rename(name=new_name, new_name=account_int.username)
    assert ret is True


def test_rename_int_missing(account_int):
    missing = random_string("", uppercase=False, lowercase=False, digits=True)
    with pytest.raises(CommandExecutionError):
        user.rename(name=missing, new_name="spongebob")


def test_rename_int_existing(account_int):
    new_existing = random_string("", uppercase=False, lowercase=False, digits=True)
    ret = user.add(name=new_existing)
    assert ret is True
    with pytest.raises(CommandExecutionError):
        user.rename(name=account_int.username, new_name=new_existing)
    # We need to clean this up because it wasn't created in a fixture
    ret = user.delete(name=new_existing, purge=True, force=True)
    assert ret is True
    assert new_existing not in user.list_users()


def test_setpassword_str(account_str):
    ret = user.setpassword(account_str.username, password="Sup3rS3cret")
    # We have no way of verifying the password was changed on Windows, so the
    # best we can do is check that the command completed successfully
    assert ret is True


def test_setpassword_int(account_int):
    ret = user.setpassword(account_int.username, password="Sup3rS3cret")
    # We have no way of verifying the password was changed on Windows, so the
    # best we can do is check that the command completed successfully
    assert ret is True


@pytest.mark.parametrize(
    "value_name, new_value, info_field, expected",
    [
        ("description", "New description", "", None),
        ("homedrive", "H:", "", None),
        ("logonscript", "\\\\server\\script.cmd", "", None),
        ("expiration_date", "3/19/2024", "", "2024-03-19 00:00:00"),
        ("expiration_date", "Never", "", None),
        ("expired", True, "", None),
        ("expired", False, "", None),
        ("account_disabled", True, "", None),
        ("account_disabled", False, "", None),
        ("unlock_account", True, "account_locked", False),
        ("password_never_expires", True, "", None),
        ("password_never_expires", False, "", None),
        ("disallow_change_password", True, "", None),
        ("disallow_change_password", False, "", None),
    ],
)
def test_update_str(value_name, new_value, info_field, expected, account_str):
    setting = {value_name: new_value}
    ret = user.update(account_str.username, **setting)
    assert ret is True
    ret = user.info(account_str.username)
    info_field = info_field if info_field else value_name
    expected = expected if expected is not None else new_value
    assert ret[info_field] == expected
