# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.mac_group as mac_group
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

HAS_GRP = True
try:
    import grp
except ImportError:
    HAS_GRP = False


@skipIf(not HAS_GRP, "Missing required library 'grp'")
class MacGroupTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for the salt.modules.mac_group module
    """

    def setup_loader_modules(self):
        return {mac_group: {}}

    # 'add' function tests: 6

    def test_add_group_exists(self):
        """
        Tests if the group already exists or not
        """
        mock_group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        with patch("salt.modules.mac_group.info", MagicMock(return_value=mock_group)):
            self.assertRaises(CommandExecutionError, mac_group.add, "test")

    def test_add_whitespace(self):
        """
        Tests if there is whitespace in the group name
        """
        with patch("salt.modules.mac_group.info", MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_group.add, "white space")

    def test_add_underscore(self):
        """
        Tests if the group name starts with an underscore or not
        """
        with patch("salt.modules.mac_group.info", MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_group.add, "_Test")

    def test_add_gid_int(self):
        """
        Tests if the gid is an int or not
        """
        with patch("salt.modules.mac_group.info", MagicMock(return_value={})):
            self.assertRaises(SaltInvocationError, mac_group.add, "foo", "foo")

    def test_add_gid_exists(self):
        """
        Tests if the gid is already in use or not
        """
        with patch("salt.modules.mac_group.info", MagicMock(return_value={})), patch(
            "salt.modules.mac_group._list_gids", MagicMock(return_value=["3456"])
        ):
            self.assertRaises(CommandExecutionError, mac_group.add, "foo", 3456)

    def test_add(self):
        """
        Tests if specified group was added
        """
        mock_ret = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__, {"cmd.retcode": mock_ret}), patch(
            "salt.modules.mac_group.info", MagicMock(return_value={})
        ), patch("salt.modules.mac_group._list_gids", MagicMock(return_value=[])):
            self.assertTrue(mac_group.add("test", 500))

    # 'delete' function tests: 4

    def test_delete_whitespace(self):
        """
        Tests if there is whitespace in the group name
        """
        self.assertRaises(SaltInvocationError, mac_group.delete, "white space")

    def test_delete_underscore(self):
        """
        Tests if the group name starts with an underscore or not
        """
        self.assertRaises(SaltInvocationError, mac_group.delete, "_Test")

    def test_delete_group_exists(self):
        """
        Tests if the group to be deleted exists or not
        """
        with patch("salt.modules.mac_group.info", MagicMock(return_value={})):
            self.assertTrue(mac_group.delete("test"))

    def test_delete(self):
        """
        Tests if the specified group was deleted
        """
        mock_ret = MagicMock(return_value=0)
        mock_group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        with patch.dict(mac_group.__salt__, {"cmd.retcode": mock_ret}), patch(
            "salt.modules.mac_group.info", MagicMock(return_value=mock_group)
        ):
            self.assertTrue(mac_group.delete("test"))

    # 'info' function tests: 2

    def test_info_whitespace(self):
        """
        Tests if there is whitespace in the group name
        """
        self.assertRaises(SaltInvocationError, mac_group.info, "white space")

    def test_info(self):
        """
        Tests the return of group information
        """
        mock_getgrall = [grp.struct_group(("foo", "*", 20, ["test"]))]
        with patch("grp.getgrall", MagicMock(return_value=mock_getgrall)):
            ret = {"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}
            self.assertEqual(mac_group.info("foo"), ret)

    # '_format_info' function tests: 1

    def test_format_info(self):
        """
        Tests the formatting of returned group information
        """
        data = grp.struct_group(("wheel", "*", 0, ["root"]))
        ret = {"passwd": "*", "gid": 0, "name": "wheel", "members": ["root"]}
        self.assertEqual(mac_group._format_info(data), ret)

    # 'getent' function tests: 1

    def test_getent(self):
        """
        Tests the return of information on all groups
        """
        mock_getgrall = [grp.struct_group(("foo", "*", 20, ["test"]))]
        with patch("grp.getgrall", MagicMock(return_value=mock_getgrall)):
            ret = [{"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}]
            self.assertEqual(mac_group.getent(), ret)

    # 'chgid' function tests: 4

    def test_chgid_gid_int(self):
        """
        Tests if gid is an integer or not
        """
        self.assertRaises(SaltInvocationError, mac_group.chgid, "foo", "foo")

    def test_chgid_group_exists(self):
        """
        Tests if the group id exists or not
        """
        mock_pre_gid = MagicMock(return_value="")
        with patch.dict(mac_group.__salt__, {"file.group_to_gid": mock_pre_gid}), patch(
            "salt.modules.mac_group.info", MagicMock(return_value={})
        ):
            self.assertRaises(CommandExecutionError, mac_group.chgid, "foo", 4376)

    def test_chgid_gid_same(self):
        """
        Tests if the group id is the same as argument
        """
        mock_group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        mock_pre_gid = MagicMock(return_value=0)
        with patch.dict(mac_group.__salt__, {"file.group_to_gid": mock_pre_gid}), patch(
            "salt.modules.mac_group.info", MagicMock(return_value=mock_group)
        ):
            self.assertTrue(mac_group.chgid("test", 0))

    def test_chgid(self):
        """
        Tests the gid for a named group was changed
        """
        mock_group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        mock_pre_gid = MagicMock(return_value=0)
        mock_ret = MagicMock(return_value=0)
        with patch.dict(
            mac_group.__salt__, {"file.group_to_gid": mock_pre_gid}
        ), patch.dict(mac_group.__salt__, {"cmd.retcode": mock_ret}), patch(
            "salt.modules.mac_group.info", MagicMock(return_value=mock_group)
        ):
            self.assertTrue(mac_group.chgid("test", 500))
