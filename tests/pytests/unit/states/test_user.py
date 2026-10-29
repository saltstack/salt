"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import logging

import pytest

import salt.states.user as user
import salt.utils.platform
from tests.support.mock import MagicMock, Mock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {user: {}}


def test_present():
    """
    Test to ensure that the named user is present with
    the specified properties
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    mock_false = MagicMock(return_value=False)
    mock_empty_list = MagicMock(return_value=[])
    with patch.dict(user.__grains__, {"kernel": "Linux"}):
        with patch.dict(
            user.__salt__,
            {
                "group.info": mock_false,
                "user.info": mock_empty_list,
                "user.chkey": mock_empty_list,
                "user.add": mock_false,
            },
        ):
            ret.update({"comment": "The following group(s) are not present: salt"})
            assert user.present("salt", groups=["salt"]) == ret

            mock_false = MagicMock(
                side_effect=[
                    {"key": "value"},
                    {"key": "value"},
                    {"key": "value"},
                    False,
                    False,
                ]
            )
            with patch.object(user, "_changes", mock_false):
                with patch.dict(user.__opts__, {"test": True}):
                    ret.update(
                        {
                            "comment": (
                                "The following user attributes are set to be changed:\n"
                                "key: value\n"
                            ),
                            "result": None,
                        }
                    )
                    assert user.present("salt") == ret

                with patch.dict(user.__opts__, {"test": False}):
                    comment = "These values could not be changed: {!r}".format(
                        {"key": "value"}
                    )
                    ret.update({"comment": comment, "result": False})
                    assert user.present("salt") == ret

                    with patch.dict(user.__opts__, {"test": True}):
                        ret.update(
                            {"comment": "User salt set to be added", "result": None}
                        )
                        assert user.present("salt") == ret

                    with patch.dict(user.__opts__, {"test": False}):
                        ret.update(
                            {
                                "comment": "Failed to create new user salt",
                                "result": False,
                            }
                        )
                        assert user.present("salt") == ret


def test_present_invalid_uid_change():
    mock_info = MagicMock(
        side_effect=[
            {
                "uid": 5000,
                "gid": 5000,
                "groups": ["foo"],
                "home": "/home/foo",
                "fullname": "Foo Bar",
            }
        ]
    )
    dunder_salt = {
        "user.info": mock_info,
        "file.group_to_gid": MagicMock(side_effect=["foo"]),
        "file.gid_to_group": MagicMock(side_effect=[5000, 5000]),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ):
        ret = user.present("foo", uid=5001)
        assert not ret["result"]
        assert ret["comment"].count("not permitted") == 1


def test_present_invalid_gid_change():
    mock_info = MagicMock(
        side_effect=[
            {
                "uid": 5000,
                "gid": 5000,
                "groups": ["foo"],
                "home": "/home/foo",
                "fullname": "Foo Bar",
            }
        ]
    )
    dunder_salt = {
        "user.info": mock_info,
        "file.group_to_gid": MagicMock(return_value="foo"),
        "file.gid_to_group": MagicMock(return_value=5000),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ):
        ret = user.present("foo", gid=5001)
        assert not ret["result"]
        assert ret["comment"].count("not permitted") == 1


def test_present_invalid_uid_gid_change():
    mock_info = MagicMock(
        side_effect=[
            {
                "uid": 5000,
                "gid": 5000,
                "groups": ["foo"],
                "home": "/home/foo",
                "fullname": "Foo Bar",
            }
        ]
    )
    dunder_salt = {
        "user.info": mock_info,
        "file.group_to_gid": MagicMock(return_value="foo"),
        "file.gid_to_group": MagicMock(return_value=5000),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ):
        ret = user.present("foo", uid=5001, gid=5001)
        assert not ret["result"]
        assert ret["comment"].count("not permitted") == 2


def test_present_uid_gid_change():
    before = {
        "uid": 5000,
        "gid": 5000,
        "groups": ["foo"],
        "home": "/home/foo",
        "fullname": "Foo Bar",
    }
    after = {
        "uid": 5001,
        "gid": 5001,
        "groups": ["othergroup"],
        "home": "/home/foo",
        "fullname": "Foo Bar",
    }
    # user.info should be called 4 times. Once the first time that
    # _changes() is called, once before and after changes are applied (to
    # get the before/after for the changes dict, and one last time to
    # confirm that no changes still need to be made.
    mock_info = MagicMock(side_effect=[before, before, after, after])
    mock_group_to_gid = MagicMock(side_effect=[5000, 5000, 5001, 5001])
    mock_gid_to_group = MagicMock(
        side_effect=["othergroup", "foo", "othergroup", "othergroup"]
    )
    dunder_salt = {
        "user.info": mock_info,
        "user.chuid": Mock(),
        "user.chgid": Mock(),
        "file.group_to_gid": mock_group_to_gid,
        "file.gid_to_group": mock_gid_to_group,
        "group.info": MagicMock(return_value=after),
        "user.chgroups": MagicMock(return_value=True),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        ret = user.present(
            "foo", uid=5001, gid=5001, allow_uid_change=True, allow_gid_change=True
        )
        assert ret == {
            "comment": "Updated user foo",
            "changes": {"gid": 5001, "uid": 5001, "groups": []},
            "name": "foo",
            "result": True,
        }


def test_absent():
    """
    Test to ensure that the named user is absent
    """
    ret = {"name": "salt", "changes": {}, "result": None, "comment": ""}
    mock = MagicMock(side_effect=[True, True, False])
    mock1 = MagicMock(return_value=False)
    with patch.dict(
        user.__salt__,
        {"user.info": mock, "user.delete": mock1, "group.info": mock1},
    ):
        with patch.dict(user.__opts__, {"test": True}):
            ret.update({"comment": "User salt set for removal"})
            assert user.absent("salt") == ret

        with patch.dict(user.__opts__, {"test": False}):
            ret.update({"comment": "Failed to remove user salt", "result": False})
            assert user.absent("salt") == ret

        ret.update({"comment": "User salt is not present", "result": True})
        assert user.absent("salt") == ret


def test_changes():
    """
    Test salt.states.user._changes
    """
    mock_info = MagicMock(
        return_value={
            "uid": 5000,
            "gid": 5000,
            "groups": ["foo"],
            "home": "/home/foo",
            "fullname": "Foo Bar",
        }
    )
    shadow_info = MagicMock(
        return_value={"min": 2, "max": 88888, "inact": 77, "warn": 14}
    )
    shadow_hash = MagicMock(return_value="abcd")
    dunder_salt = {
        "user.info": mock_info,
        "shadow.info": shadow_info,
        "shadow.default_hash": shadow_hash,
        "file.group_to_gid": MagicMock(side_effect=["foo"]),
        "file.gid_to_group": MagicMock(side_effect=[5000, 5000]),
    }

    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch(
        "os.path.isdir", MagicMock(return_value=True)
    ):
        ret = user._changes("foo", maxdays=999999, inactdays=0, warndays=7)
        assert ret == {
            "maxdays": 999999,
            "mindays": 0,
            "fullname": "",
            "warndays": 7,
            "inactdays": 0,
        }


def test_gecos_field_changes_in_user_present():
    """
    Test if the gecos fields change in salt.states.user.present
    """
    shadow_info = MagicMock(
        return_value={"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""}
    )
    shadow_hash = MagicMock(return_value="abcd")
    mock_info = MagicMock(
        side_effect=[
            {
                "uid": 5000,
                "gid": 5000,
                "groups": ["foo"],
                "home": "/home/foo",
                "fullname": "Foo Bar",
                "homephone": "667788",
            },
            {
                "uid": 5000,
                "gid": 5000,
                "groups": ["foo"],
                "home": "/home/foo",
                "fullname": "Bar Bar",
                "homephone": "44566",
            },
        ]
    )
    mock_changes = MagicMock(side_effect=[{"homephone": "667788"}, None])
    dunder_salt = {
        "user.info": mock_info,
        "user.chhomephone": MagicMock(return_value=True),
        "shadow.info": shadow_info,
        "shadow.default_hash": shadow_hash,
        "file.group_to_gid": MagicMock(side_effect=["foo"]),
        "file.gid_to_group": MagicMock(side_effect=[5000, 5000]),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch.object(
        user, "_changes", mock_changes
    ):
        res = user.present("Foo", homephone=44566, fullname="Bar Bar")
        assert res["changes"] == {"homephone": "44566", "fullname": "Bar Bar"}


def test_present_password_lock_test_mode():
    ret = {
        "name": "salt",
        "changes": {},
        "result": True,
        "comment": "User salt is present and up to date",
    }
    mock_info = MagicMock(
        return_value={
            "uid": 5000,
            "gid": 5000,
            "groups": [],
            "home": "/home/salt",
            "fullname": "Salty McSalterson",
        }
    )
    shadow_info = MagicMock(
        side_effect=[
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": "!"},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""},
        ]
    )
    shadow_hash = MagicMock(return_value="abcd")

    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__,
        {
            "shadow.default_hash": shadow_hash,
            "shadow.info": shadow_info,
            "user.info": mock_info,
            "file.gid_to_group": MagicMock(return_value=5000),
        },
    ), patch.dict(user.__opts__, {"test": True}):
        assert user.present("salt", createhome=False, password_lock=True) == ret
        ret.update(
            {
                "comment": "The following user attributes are set to be changed:\npassword_lock: True\n"
            }
        )
        ret.update({"result": None})
        assert user.present("salt", createhome=False, password_lock=True) == ret


def test_present_password_lock():
    ret = {
        "name": "salt",
        "changes": {"passwd": "XXX-REDACTED-XXX"},
        "result": True,
        "comment": "Updated user salt",
    }
    mock_info = MagicMock(
        return_value={
            "uid": 5000,
            "gid": 5000,
            "groups": [],
            "home": "/home/salt",
            "fullname": "Salty McSalterson",
        }
    )
    shadow_info = MagicMock(
        side_effect=[
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": "!"},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": "!"},
        ]
    )
    shadow_hash = MagicMock(return_value="abcd")

    unlock_account = MagicMock()
    unlock_password = MagicMock()
    lock_password = MagicMock()

    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__,
        {
            "shadow.default_hash": shadow_hash,
            "shadow.info": shadow_info,
            "user.info": mock_info,
            "file.gid_to_group": MagicMock(return_value=5000),
            "shadow.unlock_account": unlock_account,
            "shadow.unlock_password": unlock_password,
            "shadow.lock_password": lock_password,
        },
    ), patch.dict(user.__opts__, {"test": False}):
        assert user.present("salt", createhome=False, password_lock=True) == ret
        unlock_password.assert_not_called()
        unlock_account.assert_not_called()
        if salt.utils.platform.is_windows():
            lock_password.assert_not_called()
        else:
            lock_password.assert_called_once()


def test_present_password_unlock():
    ret = {
        "name": "salt",
        "changes": {"passwd": "XXX-REDACTED-XXX"},
        "result": True,
        "comment": "Updated user salt",
    }
    mock_info = MagicMock(
        return_value={
            "uid": 5000,
            "gid": 5000,
            "groups": [],
            "home": "/home/salt",
            "fullname": "Salty McSalterson",
        }
    )
    shadow_info = MagicMock(
        side_effect=[
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": "!"},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": "!"},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""},
            {"min": 2, "max": 88888, "inact": 77, "warn": 14, "passwd": ""},
        ]
    )
    shadow_hash = MagicMock(return_value="abcd")

    unlock_account = MagicMock()
    unlock_password = MagicMock()
    lock_password = MagicMock()
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__,
        {
            "shadow.default_hash": shadow_hash,
            "shadow.info": shadow_info,
            "user.info": mock_info,
            "file.gid_to_group": MagicMock(return_value=5000),
            "shadow.unlock_account": unlock_account,
            "shadow.unlock_password": unlock_password,
            "shadow.lock_password": lock_password,
        },
    ), patch.dict(user.__opts__, {"test": False}):
        assert user.present("salt", createhome=False, password_lock=False) == ret
        lock_password.assert_not_called()
        if salt.utils.platform.is_windows():
            unlock_account.assert_called_once()
            unlock_password.assert_not_called()
        else:
            unlock_password.assert_called_once()
            unlock_account.assert_not_called()


def test_present_test_mode_missing_group_new_user():
    """
    Regression test for #68110: user.present should not fail in test mode
    when a referenced group does not yet exist (e.g. it will be created by
    a group.present requisite during the actual run). When the user also
    does not yet exist, the state should report it would be added and that
    the missing groups are pending.
    """
    mock_false = MagicMock(return_value=False)
    mock_empty_list = MagicMock(return_value=[])
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__,
        {
            "group.info": mock_false,
            "user.info": mock_empty_list,
            "user.chkey": mock_empty_list,
            "user.add": mock_false,
        },
    ), patch.dict(user.__opts__, {"test": True}):
        ret = user.present("foo", groups=["foo"])
        assert ret["result"] is None, ret
        assert "set to be added" in ret["comment"], ret
        assert "foo" in ret["comment"], ret


def test_present_test_mode_missing_group_existing_user():
    """
    Regression test for #68110: when the user already exists, a missing
    required group should not cause a hard failure in test mode. The
    pending group(s) should appear in the test-mode comment.
    """
    mock_info = MagicMock(
        return_value={
            "uid": 5000,
            "gid": 5000,
            "groups": ["bar"],
            "home": "/home/baz",
            "fullname": "Baz",
        }
    )
    # group.info: "foo" missing, "bar" exists.
    group_info = MagicMock(
        side_effect=lambda name: False if name == "foo" else {"gid": 5000}
    )
    dunder_salt = {
        "group.info": group_info,
        "user.info": mock_info,
        "file.group_to_gid": MagicMock(return_value=5000),
        "file.gid_to_group": MagicMock(return_value="bar"),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": True}):
        ret = user.present("baz", groups=["foo", "bar"])
        assert ret["result"] is not False, ret
        assert "not present" not in ret["comment"], ret
        # Pending group should be reported somewhere in the comment.
        assert "foo" in ret["comment"], ret


@pytest.mark.parametrize(
    "current,wanted,remove,return_value,expected",
    [
        (["grp1"], ["grp1"], False, MagicMock(return_value={"gid": 100}), False),
        (
            ["grp1"],
            ["grp1", "grp2"],
            False,
            MagicMock(side_effect=[{"gid": 100}, {"gid": 200}]),
            True,
        ),
        (
            ["grp1"],
            ["grp1", "grp2"],
            False,
            MagicMock(side_effect=[{"gid": 100}, {"gid": 100}]),
            False,
        ),
        (
            ["grp1", "grp2"],
            ["grp1"],
            True,
            MagicMock(side_effect=[{"gid": 100}, {"gid": 200}]),
            True,
        ),
        (
            ["grp1", "grp2"],
            ["grp1"],
            True,
            MagicMock(side_effect=[{"gid": 100}, {"gid": 100}]),
            False,
        ),
    ],
)
def test__group_changes(current, wanted, remove, return_value, expected):
    with patch.dict(user.__salt__, {"group.info": return_value}):
        ret = user._group_changes(current, wanted, remove)
    assert ret == expected


def test_present_windows_group_name_collision():
    """
    Regression test for #58442: Windows shares one namespace for local users
    and local groups, so creating a user with the same name as an existing
    local group must fail fast with a clear message instead of ever calling
    user.add/NetUserAdd.
    """
    mock_add = MagicMock()
    dunder_salt = {
        "user.info": MagicMock(return_value={}),
        "group.info": MagicMock(return_value={"gid": "S-1-5-32-547"}),
        "user.add": mock_add,
    }
    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = user.present("bob114")
        assert ret["result"] is False
        assert "bob114" in ret["comment"]
        assert "already exists" in ret["comment"]
        mock_add.assert_not_called()


def test_present_windows_group_name_collision_test_mode():
    """
    The group/user name collision on Windows is a hard OS restriction that
    cannot be resolved by a later group.present requisite (unlike
    missing_groups), so it must fail fast even in test mode.
    """
    mock_add = MagicMock()
    dunder_salt = {
        "user.info": MagicMock(return_value={}),
        "group.info": MagicMock(return_value={"gid": "S-1-5-32-547"}),
        "user.add": mock_add,
    }
    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": True}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = user.present("bob114")
        assert ret["result"] is False
        assert "already exists" in ret["comment"]
        mock_add.assert_not_called()


def test_present_no_group_collision_on_posix():
    """
    The Windows-only group/user name collision check must never fire on
    POSIX, where a same-named user and primary group is the normal idiom.
    """
    mock_add = MagicMock(return_value=True)
    dunder_salt = {
        "user.info": MagicMock(return_value={}),
        "group.info": MagicMock(return_value={"gid": 5000}),
        "user.add": mock_add,
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch(
        "salt.utils.platform.is_windows", return_value=False
    ):
        ret = user.present("bob114")
        assert ret["result"] is True
        mock_add.assert_called_once()


def _windows_lusr(**overrides):
    lusr = {
        "uid": 5000,
        "gid": 5000,
        "groups": [],
        "home": None,
        "fullname": "Foo Bar",
        "homedrive": None,
        "profile": None,
        "logonscript": None,
        "description": None,
        "password_never_expires": False,
        "disallow_change_password": False,
        "account_disabled": False,
        "account_locked": False,
        "expiration_date": "Never",
    }
    lusr.update(overrides)
    return lusr


def test_changes_windows_fields():
    """
    Test salt.states.user._changes diff logic for the new Windows-only
    win_password_never_expires/win_disallow_change_password/
    win_account_disabled/win_unlock_account/win_expiration_date parameters.
    """
    dunder_salt = {
        "user.info": MagicMock(return_value=_windows_lusr()),
        "file.group_to_gid": MagicMock(return_value=5000),
        "file.gid_to_group": MagicMock(return_value="somegroup"),
    }
    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = user._changes(
            "foo",
            fullname=None,
            createhome=False,
            win_password_never_expires=True,
            win_disallow_change_password=True,
            win_account_disabled=True,
            win_unlock_account=True,
            win_expiration_date="2030-01-01",
        )
        assert ret == {
            "win_password_never_expires": True,
            "win_disallow_change_password": True,
            "win_account_disabled": True,
            "win_expiration_date": "2030-01-01",
        }

        # Nothing requested -> no diff keys.
        ret = user._changes("foo", fullname=None, createhome=False)
        assert ret == {}

        # Matching current state -> no diff keys.
        ret = user._changes(
            "foo",
            fullname=None,
            createhome=False,
            win_password_never_expires=False,
            win_disallow_change_password=False,
            win_account_disabled=False,
        )
        assert ret == {}


def test_changes_win_unlock_account_asymmetry():
    """
    win_useradd.update()'s unlock_account only supports unlocking (True);
    _changes() must only surface a change when the account is currently
    locked and the desired state is True, never for False, and never when
    already unlocked.
    """
    dunder_salt_base = {
        "file.group_to_gid": MagicMock(return_value=5000),
        "file.gid_to_group": MagicMock(return_value="somegroup"),
    }

    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__opts__, {"test": False}
    ), patch("salt.utils.platform.is_windows", return_value=True):
        # Not locked + unlock requested -> no change.
        with patch.dict(
            user.__salt__,
            {
                **dunder_salt_base,
                "user.info": MagicMock(
                    return_value=_windows_lusr(account_locked=False)
                ),
            },
        ):
            ret = user._changes(
                "foo", fullname=None, createhome=False, win_unlock_account=True
            )
            assert "win_unlock_account" not in ret

        # Locked + unlock requested -> change.
        with patch.dict(
            user.__salt__,
            {
                **dunder_salt_base,
                "user.info": MagicMock(return_value=_windows_lusr(account_locked=True)),
            },
        ):
            ret = user._changes(
                "foo", fullname=None, createhome=False, win_unlock_account=True
            )
            assert ret["win_unlock_account"] is True

        # Locked + win_unlock_account=False -> never emits a change (documented no-op).
        with patch.dict(
            user.__salt__,
            {
                **dunder_salt_base,
                "user.info": MagicMock(return_value=_windows_lusr(account_locked=True)),
            },
        ):
            ret = user._changes(
                "foo", fullname=None, createhome=False, win_unlock_account=False
            )
            assert "win_unlock_account" not in ret


def test_present_dispatches_windows_update_fields():
    """
    When _changes() reports a win_account_disabled-style change, present()
    must dispatch it via user.update with the plain (non win_-prefixed)
    kwarg name.
    """
    mock_changes = MagicMock(
        side_effect=[
            {"win_account_disabled": True},
            {},
        ]
    )
    mock_update = MagicMock(return_value=True)
    dunder_salt = {
        "user.info": MagicMock(return_value=_windows_lusr()),
        "user.update": mock_update,
    }
    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch.object(
        user, "_changes", mock_changes
    ), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        user.present("bob")
        mock_update.assert_any_call(name="bob", account_disabled=True)


def test_gecos_comma_check_skipped_on_windows():
    """
    Bonus fix: Windows "Full Name" is not comma-delimited GECOS data, so a
    comma in fullname must not be rejected there.
    """
    dunder_salt = {
        "group.info": MagicMock(return_value=False),
        "user.info": MagicMock(return_value={}),
        "user.add": MagicMock(return_value=True),
    }
    with patch.dict(user.__grains__, {"kernel": "Windows"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": True}), patch(
        "salt.utils.platform.is_windows", return_value=True
    ):
        ret = user.present("bob", fullname="Doe, John")
        assert "Unsupported char" not in ret["comment"]


def test_gecos_comma_check_rejected_on_posix():
    """
    The comma-in-GECOS-field restriction must still apply on POSIX.
    """
    dunder_salt = {
        "group.info": MagicMock(return_value=False),
        "user.info": MagicMock(return_value={}),
        "user.add": MagicMock(return_value=True),
    }
    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": True}), patch(
        "salt.utils.platform.is_windows", return_value=False
    ):
        ret = user.present("bob", fullname="Doe, John")
        assert ret["result"] is False
        assert "Unsupported char" in ret["comment"]
