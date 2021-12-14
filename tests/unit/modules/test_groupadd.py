"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.groupadd as groupadd
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

try:
    import grp
except ImportError:
    pass


@skipIf(salt.utils.platform.is_windows(), "Module not available on Windows")
class GroupAddTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.groupadd
    """

    def setup_loader_modules(self):
        return {groupadd: {}}

    # 'add' function tests: 1

    def test_add(self):
        """
        Tests if specified group was added
        """
        mock = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
            self.assertTrue(groupadd.add("test", 100))

        with patch.dict(groupadd.__grains__, {"kernel": "Linux"}):
            with patch.dict(groupadd.__salt__, {"cmd.run_all": mock}):
                self.assertTrue(groupadd.add("test", 100, True))

    # 'info' function tests: 1

    def test_info(self):
        """
        Tests the return of group information
        """
        getgrnam = grp.struct_group(("foo", "*", 20, ["test"]))
        with patch("grp.getgrnam", MagicMock(return_value=getgrnam)):
            ret = {"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}
            self.assertEqual(groupadd.info("foo"), ret)

    # '_format_info' function tests: 1

    def test_format_info(self):
        """
        Tests the formatting of returned group information
        """
        group = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
        with patch("salt.modules.groupadd._format_info", MagicMock(return_value=group)):
            data = grp.struct_group(("wheel", "*", 0, ["root"]))
            ret = {"passwd": "*", "gid": 0, "name": "test", "members": ["root"]}
            self.assertDictEqual(groupadd._format_info(data), ret)

    # 'getent' function tests: 1

    def test_getent(self):
        """
        Tests the return of information on all groups
        """
        getgrnam = grp.struct_group(("foo", "*", 20, ["test"]))
        with patch("grp.getgrall", MagicMock(return_value=[getgrnam])):
            ret = [{"passwd": "*", "gid": 20, "name": "foo", "members": ["test"]}]
            self.assertEqual(groupadd.getent(), ret)

    # 'chgid' function tests: 2

    def test_chgid_gid_same(self):
        """
        Tests if the group id is the same as argument
        """
        mock = MagicMock(return_value={"gid": 10})
        with patch.object(groupadd, "info", mock):
            self.assertTrue(groupadd.chgid("test", 10))

    def test_chgid(self):
        """
        Tests the gid for a named group was changed
        """
        mock = MagicMock(return_value=None)
        with patch.dict(groupadd.__salt__, {"cmd.run": mock}):
            mock = MagicMock(side_effect=[{"gid": 10}, {"gid": 500}])
            with patch.object(groupadd, "info", mock):
                self.assertTrue(groupadd.chgid("test", 500))

    # 'delete' function tests: 1

    def test_delete(self):
        """
        Tests if the specified group was deleted
        """
        mock_ret = MagicMock(return_value={"retcode": 0})
        with patch.dict(groupadd.__salt__, {"cmd.run_all": mock_ret}):
            self.assertTrue(groupadd.delete("test"))

    # 'adduser' function tests: 1

    def test_adduser(self):
        """
        Tests if specified user gets added in the group.
        """
        os_version_list = [
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "RedHat",
                    "osmajorrelease": "5",
                },
                "cmd": ["gpasswd", "-a", "root", "test"],
            },
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "Suse",
                    "osmajorrelease": "11",
                },
                "cmd": ["usermod", "-A", "test", "root"],
            },
            {
                "grains": {"kernel": "Linux"},
                "cmd": ["gpasswd", "--add", "root", "test"],
            },
            {
                "grains": {"kernel": "OTHERKERNEL"},
                "cmd": ["usermod", "-G", "test", "root"],
            },
        ]

        for os_version in os_version_list:
            mock = MagicMock(return_value={"retcode": 0})
            with patch.dict(groupadd.__grains__, os_version["grains"]):
                with patch.dict(groupadd.__salt__, {"cmd.retcode": mock}):
                    self.assertFalse(groupadd.adduser("test", "root"))
                    groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                        os_version["cmd"], python_shell=False
                    )

    # 'deluser' function tests: 1

    def test_deluser(self):
        """
        Tests if specified user gets deleted from the group.
        """
        os_version_list = [
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "RedHat",
                    "osmajorrelease": "5",
                },
                "cmd": ["gpasswd", "-d", "root", "test"],
            },
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "Suse",
                    "osmajorrelease": "11",
                },
                "cmd": ["usermod", "-R", "test", "root"],
            },
            {
                "grains": {"kernel": "Linux"},
                "cmd": ["gpasswd", "--del", "root", "test"],
            },
            {"grains": {"kernel": "OpenBSD"}, "cmd": ["usermod", "-S", "foo", "root"]},
        ]

        for os_version in os_version_list:
            mock_retcode = MagicMock(return_value=0)
            mock_stdout = MagicMock(return_value="test foo")
            mock_info = MagicMock(
                return_value={
                    "passwd": "*",
                    "gid": 0,
                    "name": "test",
                    "members": ["root"],
                }
            )

            with patch.dict(groupadd.__grains__, os_version["grains"]):
                with patch.dict(
                    groupadd.__salt__,
                    {
                        "cmd.retcode": mock_retcode,
                        "group.info": mock_info,
                        "cmd.run_stdout": mock_stdout,
                    },
                ):
                    self.assertTrue(groupadd.deluser("test", "root"))
                    groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                        os_version["cmd"], python_shell=False
                    )

    # 'deluser' function tests: 1

    def test_members(self):
        """
        Tests if members of the group, get replaced with a provided list.
        """
        os_version_list = [
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "RedHat",
                    "osmajorrelease": "5",
                },
                "cmd": ["gpasswd", "-M", "foo", "test"],
            },
            {
                "grains": {
                    "kernel": "Linux",
                    "os_family": "Suse",
                    "osmajorrelease": "11",
                },
                "cmd": ["groupmod", "-A", "foo", "test"],
            },
            {
                "grains": {"kernel": "Linux"},
                "cmd": ["gpasswd", "--members", "foo", "test"],
            },
            {"grains": {"kernel": "OpenBSD"}, "cmd": ["usermod", "-G", "test", "foo"]},
        ]

        for os_version in os_version_list:
            mock_ret = MagicMock(return_value={"retcode": 0})
            mock_stdout = MagicMock(return_value={"cmd.run_stdout": 1})
            mock_info = MagicMock(
                return_value={
                    "passwd": "*",
                    "gid": 0,
                    "name": "test",
                    "members": ["root"],
                }
            )
            mock = MagicMock(return_value=True)

            with patch.dict(groupadd.__grains__, os_version["grains"]):
                with patch.dict(
                    groupadd.__salt__,
                    {
                        "cmd.retcode": mock_ret,
                        "group.info": mock_info,
                        "cmd.run_stdout": mock_stdout,
                        "cmd.run": mock,
                    },
                ):
                    self.assertFalse(groupadd.members("test", "foo"))
                    groupadd.__salt__["cmd.retcode"].assert_called_once_with(
                        os_version["cmd"], python_shell=False
                    )
