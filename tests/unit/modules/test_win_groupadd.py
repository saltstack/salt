"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.win_groupadd as win_groupadd
import salt.utils.win_functions
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase, skipIf

# pylint: disable=unused-import
try:
    import win32com
    import pythoncom
    import pywintypes

    PYWINTYPES_ERROR = pywintypes.com_error(
        -1234, "Exception occurred.", (0, None, "C", None, 0, -2147352567), None
    )
    HAS_WIN_LIBS = True
except ImportError:
    HAS_WIN_LIBS = False
# pylint: enable=unused-import


class MockMember:
    def __init__(self, name):
        self.ADSPath = name


class MockGroupObj:
    def __init__(self, ads_name, ads_users):
        self._members = [MockMember(x) for x in ads_users]
        self.Name = ads_name

    def members(self):
        return self._members

    def Add(self, name):
        """
        This should be a no-op unless we want to test raising an error, in
        which case this should be overridden in a subclass.
        """

    def Remove(self, name):
        """
        This should be a no-op unless we want to test raising an error, in
        which case this should be overridden in a subclass.
        """


@skipIf(
    not HAS_WIN_LIBS,
    "win_groupadd unit tests can only be run if win32com, pythoncom, and pywintypes are"
    " installed",
)
class WinGroupTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_groupadd
    """

    def setup_loader_modules(self):
        self.sam_mock = MagicMock(side_effect=lambda x: "HOST\\" + x)
        return {win_groupadd: {"__opts__": {"test": False}}}

    def test_add(self):
        """
        Test adding a new group
        """
        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", Mock()
        ):
            self.assertTrue(win_groupadd.add("foo"))

    def test_add_group_exists(self):
        """
        Test adding a new group if the group already exists
        """
        info = MagicMock(
            return_value={
                "name": "foo",
                "passwd": None,
                "gid": None,
                "members": ["HOST\\spongebob"],
            }
        )
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", Mock()
        ):
            self.assertFalse(win_groupadd.add("foo"))

    def test_add_error(self):
        """
        Test adding a group and encountering an error
        """

        class CompObj:
            def Create(self, type, name):
                raise PYWINTYPES_ERROR

        obj_comp_mock = MagicMock(return_value=CompObj())
        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", obj_comp_mock
        ):
            self.assertFalse(win_groupadd.add("foo"))

    def test_delete(self):
        """
        Test removing a group
        """
        info = MagicMock(
            return_value={
                "name": "foo",
                "passwd": None,
                "gid": None,
                "members": ["HOST\\spongebob"],
            }
        )
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", Mock()
        ):
            self.assertTrue(win_groupadd.delete("foo"))

    def test_delete_no_group(self):
        """
        Test removing a group that doesn't exists
        """
        info = MagicMock(return_value=False)
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", Mock()
        ):
            self.assertFalse(win_groupadd.delete("foo"))

    def test_delete_error(self):
        """
        Test removing a group and encountering an error
        """

        class CompObj:
            def Delete(self, type, name):
                raise PYWINTYPES_ERROR

        obj_comp_mock = MagicMock(return_value=CompObj())
        info = MagicMock(
            return_value={
                "name": "foo",
                "passwd": None,
                "gid": None,
                "members": ["HOST\\spongebob"],
            }
        )
        with patch.object(win_groupadd, "info", info), patch.object(
            win_groupadd, "_get_computer_object", obj_comp_mock
        ):
            self.assertFalse(win_groupadd.delete("foo"))

    def test_info(self):
        """
        Test if it return information about a group.
        """
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("salt", ["WinNT://HOST/steve"])
        )
        with patch.object(win_groupadd, "_get_group_object", obj_group_mock):
            self.assertDictEqual(
                win_groupadd.info("salt"),
                {
                    "gid": None,
                    "members": ["HOST\\steve"],
                    "passwd": None,
                    "name": "salt",
                },
            )

    def test_getent(self):
        obj_group_mock = MagicMock(
            return_value=[
                MockGroupObj("salt", ["WinNT://HOST/steve"]),
                MockGroupObj("salty", ["WinNT://HOST/spongebob"]),
            ]
        )
        mock_g_to_g = MagicMock(side_effect=[1, 2])
        with patch.object(win_groupadd, "_get_all_groups", obj_group_mock), patch.dict(
            win_groupadd.__salt__, {"file.group_to_gid": mock_g_to_g}
        ):
            self.assertListEqual(
                win_groupadd.getent(),
                [
                    {
                        "gid": 1,
                        "members": ["HOST\\steve"],
                        "name": "salt",
                        "passwd": "x",
                    },
                    {
                        "gid": 2,
                        "members": ["HOST\\spongebob"],
                        "name": "salty",
                        "passwd": "x",
                    },
                ],
            )

    def test_getent_context(self):
        """
        Test group.getent is using the values in __context__
        """
        with patch.dict(win_groupadd.__context__, {"group.getent": True}):
            self.assertTrue(win_groupadd.getent())

    def test_adduser(self):
        """
        Test adding a user to a group
        """
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("foo", ["WinNT://HOST/steve"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertTrue(win_groupadd.adduser("foo", "spongebob"))

    def test_adduser_already_exists(self):
        """
        Test adding a user that already exists
        """
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("foo", ["WinNT://HOST/steve"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertFalse(win_groupadd.adduser("foo", "steve"))

    def test_adduser_error(self):
        """
        Test adding a user and encountering an error
        """
        msg = "An unknown directory object was requested"
        error = pywintypes.com_error(
            -1234, "Exception occurred.", (0, None, msg, None, 0, -2147352567), None
        )

        # Create mock group object with mocked Add function which raises the
        # exception we need in order to test the error case.
        class GroupObj(MockGroupObj):
            def Add(self, name):
                raise error

        obj_group_mock = MagicMock(return_value=GroupObj("foo", ["WinNT://HOST/steve"]))
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            with TstSuiteLoggingHandler() as handler:
                self.assertFalse(win_groupadd.adduser("foo", "username"))
                expected = (
                    "ERROR:Failed to add HOST\\username to group foo. An unknown"
                    " directory object was requested"
                )
                self.assertIn(expected, handler.messages)

    def test_adduser_group_does_not_exist(self):
        obj_group_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(win_groupadd, "_get_group_object", obj_group_mock):
            self.assertFalse(win_groupadd.adduser("foo", "spongebob"))

    def test_deluser(self):
        """
        Test removing a user from a group
        """
        # Test removing a user
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("foo", ["WinNT://HOST/spongebob"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertTrue(win_groupadd.deluser("foo", "spongebob"))

    def test_deluser_no_user(self):
        """
        Test removing a user from a group and that user is not a member of the
        group
        """
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("foo", ["WinNT://HOST/steve"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertFalse(win_groupadd.deluser("foo", "spongebob"))

    def test_deluser_error(self):
        """
        Test removing a user and encountering an error
        """

        class GroupObj(MockGroupObj):
            def Remove(self, name):
                raise PYWINTYPES_ERROR

        obj_group_mock = MagicMock(
            return_value=GroupObj("foo", ["WinNT://HOST/spongebob"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertFalse(win_groupadd.deluser("foo", "spongebob"))

    def test_deluser_group_does_not_exist(self):
        obj_group_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(win_groupadd, "_get_group_object", obj_group_mock):
            self.assertFalse(win_groupadd.deluser("foo", "spongebob"))

    def test_members(self):
        """
        Test adding a list of members to a group, all existing users removed
        """
        obj_group_mock = MagicMock(
            return_value=MockGroupObj("foo", ["WinNT://HOST/steve"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertTrue(win_groupadd.members("foo", "spongebob,patrick,squidward"))
            obj_group_mock.assert_called_once_with("foo")

    def test_members_correct_membership(self):
        """
        Test adding a list of users where the list of users already exists
        """
        members_list = [
            "WinNT://HOST/spongebob",
            "WinNT://HOST/squidward",
            "WinNT://HOST/patrick",
        ]
        obj_group_mock = MagicMock(return_value=MockGroupObj("foo", members_list))
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertTrue(win_groupadd.members("foo", "spongebob,patrick,squidward"))
            obj_group_mock.assert_called_once_with("foo")

    def test_members_group_does_not_exist(self):
        """
        Test adding a list of users where the group does not exist
        """
        obj_group_mock = MagicMock(side_effect=PYWINTYPES_ERROR)
        with patch.object(
            salt.utils.win_functions, "get_sam_name", self.sam_mock
        ), patch.object(win_groupadd, "_get_group_object", obj_group_mock):
            self.assertFalse(win_groupadd.members("foo", "spongebob"))

    def test_members_fail_to_remove(self):
        """
        Test adding a list of members and fail to remove members not in the list
        """

        class GroupObj(MockGroupObj):
            def Remove(self, name):
                raise PYWINTYPES_ERROR

        obj_group_mock = MagicMock(
            return_value=GroupObj("foo", ["WinNT://HOST/spongebob"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertFalse(win_groupadd.members("foo", "patrick"))
            obj_group_mock.assert_called_once_with("foo")

    def test_members_fail_to_add(self):
        """
        Test adding a list of members and failing to add
        """

        class GroupObj(MockGroupObj):
            def Add(self, name):
                raise PYWINTYPES_ERROR

        obj_group_mock = MagicMock(
            return_value=GroupObj("foo", ["WinNT://HOST/spongebob"])
        )
        with patch.object(
            win_groupadd, "_get_group_object", obj_group_mock
        ), patch.object(salt.utils.win_functions, "get_sam_name", self.sam_mock):
            self.assertFalse(win_groupadd.members("foo", "patrick"))
            obj_group_mock.assert_called_once_with("foo")

    def test_list_groups(self):
        """
        Test that list groups returns a list of groups by name
        """
        obj_group_mock = MagicMock(
            return_value=[
                MockGroupObj("salt", ["WinNT://HOST/steve"]),
                MockGroupObj("salty", ["WinNT://HOST/Administrator"]),
            ]
        )
        with patch.object(win_groupadd, "_get_all_groups", obj_group_mock):
            self.assertListEqual(win_groupadd.list_groups(), ["salt", "salty"])

    def test_list_groups_context(self):
        """
        Test group.list_groups is using the values in __context__
        """
        with patch.dict(win_groupadd.__context__, {"group.list_groups": True}):
            self.assertTrue(win_groupadd.list_groups())

    def test__get_computer_object(self):
        """
        Test the _get_computer_object function. Should return a Com object, but
        we're going to mock just an object
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch(
            "win32com.client.Dispatch", autospec=True
        ) as com_obj:
            com_obj.GetObject = [object]
            test = win_groupadd._get_computer_object()
            assert isinstance(test, object)

    def test__get_group_object(self):
        """
        Test the _get_group_object function. Should return a Com object, but
        we're going to mock just an object
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch(
            "win32com.client.Dispatch", autospec=True
        ) as com_obj:
            com_obj.GetObject = [object]
            test = win_groupadd._get_group_object("steve")
            assert isinstance(test, object)

    def test__get_all_groups(self):
        """
        Test the _get_all_groups function. It doesn't actually return a list.
        It returns a Com Object that is an iterator, so we're just going to mock
        an object
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch(
            "win32com.client.Dispatch", autospec=True
        ) as com_obj:
            com_obj.GetObject = [object]
            test = win_groupadd._get_all_groups()
            assert isinstance(test, object)
