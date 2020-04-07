# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt Libs
import salt.states.user as user

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class UserTestCase(TestCase, LoaderModuleMockMixin):
    """
        Validate the user state
    """

    def setup_loader_modules(self):
        return {user: {}}

    def test_present(self):
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
                ret.update(
                    {"comment": "The following group(s) are" " not present: salt"}
                )
                self.assertDictEqual(user.present("salt", groups=["salt"]), ret)

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
                                "comment": "The following user attributes are set "
                                "to be changed:\n"
                                "key: value\n",
                                "result": None,
                            }
                        )
                        self.assertDictEqual(user.present("salt"), ret)

                    with patch.dict(user.__opts__, {"test": False}):
                        # pylint: disable=repr-flag-used-in-string
                        comment = "These values could not be changed: {0!r}".format(
                            {"key": "value"}
                        )
                        # pylint: enable=repr-flag-used-in-string
                        ret.update({"comment": comment, "result": False})
                        self.assertDictEqual(user.present("salt"), ret)

                        with patch.dict(user.__opts__, {"test": True}):
                            ret.update(
                                {
                                    "comment": "User salt set to" " be added",
                                    "result": None,
                                }
                            )
                            self.assertDictEqual(user.present("salt"), ret)

                        with patch.dict(user.__opts__, {"test": False}):
                            ret.update(
                                {
                                    "comment": "Failed to create new" " user salt",
                                    "result": False,
                                }
                            )
                            self.assertDictEqual(user.present("salt"), ret)

    def test_present_invalid_uid_change(self):
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
            "file.gid_to_group": MagicMock(side_effect=[5000]),
        }
        # side_effect used because these mocks should only be called once
        with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
            user.__salt__, dunder_salt
        ):
            ret = user.present("foo", uid=5001)
            # State should have failed
            self.assertFalse(ret["result"])
            # Only one of uid/gid should have been flagged in the comment
            self.assertEqual(ret["comment"].count("not permitted"), 1)

    def test_present_invalid_gid_change(self):
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
            "file.gid_to_group": MagicMock(side_effect=[5000]),
        }
        # side_effect used because these mocks should only be called once
        with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
            user.__salt__, dunder_salt
        ):
            ret = user.present("foo", gid=5001)
            # State should have failed
            self.assertFalse(ret["result"])
            # Only one of uid/gid should have been flagged in the comment
            self.assertEqual(ret["comment"].count("not permitted"), 1)

    def test_present_invalid_uid_gid_change(self):
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
            "file.gid_to_group": MagicMock(side_effect=[5000]),
        }
        # side_effect used because these mocks should only be called once
        with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
            user.__salt__, dunder_salt
        ):
            ret = user.present("foo", uid=5001, gid=5001)
            # State should have failed
            self.assertFalse(ret["result"])
            # Both the uid and gid should have been flagged in the comment
            self.assertEqual(ret["comment"].count("not permitted"), 2)

    def test_present_uid_gid_change(self):
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
        mock_gid_to_group = MagicMock(side_effect=[5000, 5001])
        dunder_salt = {
            "user.info": mock_info,
            "user.chuid": Mock(),
            "user.chgid": Mock(),
            "file.group_to_gid": mock_group_to_gid,
            "file.gid_to_group": mock_gid_to_group,
        }
        # side_effect used because these mocks should only be called once
        with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
            user.__salt__, dunder_salt
        ), patch.dict(user.__opts__, {"test": False}), patch(
            "os.path.isdir", MagicMock(return_value=True)
        ):
            ret = user.present(
                "foo", uid=5001, gid=5001, allow_uid_change=True, allow_gid_change=True
            )
            self.assertEqual(
                ret,
                {
                    "comment": "Updated user foo",
                    "changes": {"gid": 5001, "uid": 5001, "groups": ["othergroup"]},
                    "name": "foo",
                    "result": True,
                },
            )

    def test_absent(self):
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
                self.assertDictEqual(user.absent("salt"), ret)

            with patch.dict(user.__opts__, {"test": False}):
                ret.update({"comment": "Failed to remove user salt", "result": False})
                self.assertDictEqual(user.absent("salt"), ret)

            ret.update({"comment": "User salt is not present", "result": True})
            self.assertDictEqual(user.absent("salt"), ret)

    def test_changes(self):
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
            "file.gid_to_group": MagicMock(side_effect=[5000]),
        }

        def mock_exists(*args):
            return True

        # side_effect used because these mocks should only be called once
        with patch.dict(user.__grains__, {"kernel": "Linux"}), patch.dict(
            user.__salt__, dunder_salt
        ), patch.dict(user.__opts__, {"test": False}), patch(
            "os.path.isdir", mock_exists
        ):
            ret = user._changes("foo", maxdays=999999, inactdays=0, warndays=7)
            assert ret == {
                "maxdays": 999999,
                "mindays": 0,
                "fullname": "",
                "warndays": 7,
                "inactdays": 0,
            }
