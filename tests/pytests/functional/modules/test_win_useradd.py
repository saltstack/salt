import pytest
from saltfactories.utils import random_string

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def user(modules):
    return modules.user


@pytest.fixture
def username_str(user):
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
def username_int(user):
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
def account_str(user, username_str):
    with pytest.helpers.create_account(username=username_str) as account:
        user.addgroup(account.username, "Users")
        yield account


@pytest.fixture
def account_int(user, username_int):
    with pytest.helpers.create_account(username=username_int) as account:
        user.addgroup(account.username, "Users")
        yield account


def test_add_str(user, username_str):
    ret = user.add(name=username_str)
    assert ret is True
    assert username_str in user.list_users()


def test_add_int(user, username_int):
    ret = user.add(name=username_int)
    assert ret is True
    assert username_int in user.list_users()


def test_addgroup_str(user, account_str):
    ret = user.addgroup(account_str.username, "Backup Operators")
    assert ret is True
    ret = user.info(account_str.username)
    assert "Backup Operators" in ret["groups"]


def test_addgroup_int(user, account_int):
    ret = user.addgroup(account_int.username, "Backup Operators")
    assert ret is True
    ret = user.info(account_int.username)
    assert "Backup Operators" in ret["groups"]


def test_chfullname_str(user, account_str):
    ret = user.chfullname(account_str.username, "New Full Name")
    assert ret is True
    ret = user.info(account_str.username)
    assert ret["fullname"] == "New Full Name"


def test_chfullname_int(user, account_int):
    ret = user.chfullname(account_int.username, "New Full Name")
    assert ret is True
    ret = user.info(account_int.username)
    assert ret["fullname"] == "New Full Name"


def test_chgroups_single_str(user, account_str):
    groups = ["Backup Operators"]
    ret = user.chgroups(account_str.username, groups=groups)
    assert ret is True
    ret = user.info(account_str.username)
    groups.append("Users")
    assert sorted(ret["groups"]) == sorted(groups)


def test_chgroups_single_int(user, account_int):
    groups = ["Backup Operators"]
    ret = user.chgroups(account_int.username, groups=groups)
    assert ret is True
    ret = user.info(account_int.username)
    groups.append("Users")
    assert sorted(ret["groups"]) == sorted(groups)


def test_chgroups_list_str(user, account_str):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_str.username, groups=groups)
    assert ret is True
    ret = user.info(account_str.username)
    groups.append("Users")
    assert sorted(ret["groups"]) == sorted(groups)


def test_chgroups_list_int(user, account_int):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_int.username, groups=groups)
    assert ret is True
    ret = user.info(account_int.username)
    groups.append("Users")
    assert sorted(ret["groups"]) == sorted(groups)


def test_chgroups_list_append_false_str(user, account_str):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_str.username, groups=groups, append=False)
    assert ret is True
    ret = user.info(account_str.username)
    assert sorted(ret["groups"]) == sorted(groups)


def test_chgroups_list_append_false_int(user, account_int):
    groups = ["Backup Operators", "Guests"]
    ret = user.chgroups(account_int.username, groups=groups, append=False)
    assert ret is True
    ret = user.info(account_int.username)
    assert sorted(ret["groups"]) == sorted(groups)


def test_chhome_str(user, account_str):
    home = r"C:\spongebob\squarepants"
    ret = user.chhome(name=account_str.username, home=home)
    assert ret is True
    ret = user.info(name=account_str.username)
    assert ret["home"] == home


def test_chhome_int(user, account_int):
    home = r"C:\spongebob\squarepants"
    ret = user.chhome(name=account_int.username, home=home)
    assert ret is True
    ret = user.info(name=account_int.username)
    assert ret["home"] == home


def test_chprofile_str(user, account_str):
    profile = r"C:\spongebob\squarepants"
    ret = user.chprofile(name=account_str.username, profile=profile)
    assert ret is True
    ret = user.info(name=account_str.username)
    assert ret["profile"] == profile


def test_chprofile_int(user, account_int):
    profile = r"C:\spongebob\squarepants"
    ret = user.chprofile(name=account_int.username, profile=profile)
    assert ret is True
    ret = user.info(name=account_int.username)
    assert ret["profile"] == profile


def test_delete_str(user, account_str):
    ret = user.delete(name=account_str.username)
    assert ret is True
    assert user.info(name=account_str.username) == {}


def test_delete_int(user, account_int):
    ret = user.delete(name=account_int.username)
    assert ret is True
    assert user.info(name=account_int.username) == {}


def test_get_user_sid_str(user, account_str):
    ret = user.get_user_sid(account_str.username)
    assert ret.startswith("S-1-5")


def test_get_user_sid_int(user, account_int):
    ret = user.get_user_sid(account_int.username)
    assert ret.startswith("S-1-5")


def test_info_str(user, account_str):
    ret = user.info(account_str.username)
    assert ret["name"] == account_str.username
    assert ret["uid"].startswith("S-1-5")


def test_info_int(user, account_int):
    ret = user.info(account_int.username)
    assert ret["name"] == account_int.username
    assert ret["uid"].startswith("S-1-5")


def test_list_groups_str(user, account_str):
    ret = user.list_groups(account_str.username)
    assert ret == ["Users"]


def test_list_groups_int(user, account_int):
    ret = user.list_groups(account_int.username)
    assert ret == ["Users"]


def test_list_users(user):
    ret = user.list_users()
    assert "Administrator" in ret


def test_removegroup_str(user, account_str):
    ret = user.removegroup(account_str.username, "Users")
    assert ret is True
    ret = user.info(account_str.username)
    assert ret["groups"] == []


def test_removegroup_int(user, account_int):
    ret = user.removegroup(account_int.username, "Users")
    assert ret is True
    ret = user.info(account_int.username)
    assert ret["groups"] == []


def test_rename_str(user, account_str):
    new_name = random_string("test-account-", uppercase=False)
    ret = user.rename(name=account_str.username, new_name=new_name)
    assert ret is True
    assert new_name in user.list_users()
    # Let's set it back so that it gets cleaned up...
    ret = user.rename(name=new_name, new_name=account_str.username)
    assert ret is True


def test_rename_str_missing(user, account_str):
    missing = random_string("test-account-", uppercase=False)
    with pytest.raises(CommandExecutionError):
        user.rename(name=missing, new_name="spongebob")


def test_rename_str_existing(user, account_str):
    new_existing = random_string("test-account-", uppercase=False)
    ret = user.add(name=new_existing)
    assert ret is True
    with pytest.raises(CommandExecutionError):
        user.rename(name=account_str.username, new_name=new_existing)
    # We need to clean this up because it wasn't created in a fixture
    ret = user.delete(name=new_existing, purge=True, force=True)
    assert ret is True
    assert new_existing not in user.list_users()


def test_rename_int(user, account_int):
    new_name = random_string("", uppercase=False, lowercase=False, digits=True)
    ret = user.rename(name=account_int.username, new_name=new_name)
    assert ret is True
    assert new_name in user.list_users()
    # Let's set it back so that it gets cleaned up...
    ret = user.rename(name=new_name, new_name=account_int.username)
    assert ret is True


def test_rename_int_missing(user, account_int):
    missing = random_string("", uppercase=False, lowercase=False, digits=True)
    with pytest.raises(CommandExecutionError):
        user.rename(name=missing, new_name="spongebob")


def test_rename_int_existing(user, account_int):
    new_existing = random_string("", uppercase=False, lowercase=False, digits=True)
    ret = user.add(name=new_existing)
    assert ret is True
    with pytest.raises(CommandExecutionError):
        user.rename(name=account_int.username, new_name=new_existing)
    # We need to clean this up because it wasn't created in a fixture
    ret = user.delete(name=new_existing, purge=True, force=True)
    assert ret is True
    assert new_existing not in user.list_users()


def test_setpassword_str(user, account_str):
    ret = user.setpassword(account_str.username, password="Sup3rS3cret")
    # We have no way of verifying the password was changed on Windows, so the
    # best we can do is check that the command completed successfully
    assert ret is True


def test_setpassword_int(user, account_int):
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
        ("account_disabled", True, "", None),
        ("account_disabled", False, "", None),
        ("unlock_account", True, "account_locked", False),
        ("password_never_expires", True, "", None),
        ("password_never_expires", False, "", None),
        ("expired", True, "", None),
        ("expired", False, "", None),
        ("disallow_change_password", True, "", None),
        ("disallow_change_password", False, "", None),
    ],
)
def test_update_str(user, value_name, new_value, info_field, expected, account_str):
    setting = {value_name: new_value}
    # You can't expire an account if the password never expires
    if value_name == "expired":
        setting.update({"password_never_expires": not new_value})
    ret = user.update(account_str.username, **setting)
    assert ret is True
    ret = user.info(account_str.username)
    info_field = info_field if info_field else value_name
    expected = expected if expected is not None else new_value
    assert ret[info_field] == expected
