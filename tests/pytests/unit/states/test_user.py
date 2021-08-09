"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import logging

import pytest
import salt.states.user as user
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
        "file.group_to_gid": MagicMock(side_effect=["foo"]),
        "file.gid_to_group": MagicMock(side_effect=[5000, 5000]),
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
        "file.group_to_gid": MagicMock(side_effect=["foo"]),
        "file.gid_to_group": MagicMock(side_effect=[5000, 5000]),
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
    mock_group_to_gid = MagicMock(side_effect=["foo", "othergroup"])
    mock_gid_to_group = MagicMock(side_effect=[5000, 5000, 5001, 5001])
    dunder_salt = {
        "user.info": mock_info,
        "user.chuid": Mock(),
        "user.chgid": Mock(),
        "file.group_to_gid": mock_group_to_gid,
        "file.gid_to_group": mock_gid_to_group,
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
            "changes": {"gid": 5001, "uid": 5001, "groups": ["othergroup"]},
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

    def mock_exists(*args):
        return True

    with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
        user.__salt__, dunder_salt
    ), patch.dict(user.__opts__, {"test": False}), patch("os.path.isdir", mock_exists):
        ret = user._changes("foo", maxdays=999999, inactdays=0, warndays=7)
        assert ret == {
            "maxdays": 999999,
            "mindays": 0,
            "fullname": "",
            "warndays": 7,
            "inactdays": 0,
        }
