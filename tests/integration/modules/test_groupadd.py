import pytest
from saltfactories.utils import random_string

import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.case import ModuleCase

if not salt.utils.platform.is_windows():
    import grp


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.windows_whitelisted
@pytest.mark.skip_unless_on_platforms(linux=True, windows=True)
class GroupModuleTest(ModuleCase):
    """
    Validate the linux group system module
    """

    def setUp(self):
        """
        Get current settings
        """
        super().setUp()
        self._user = random_string("tg-", uppercase=False)
        self._user1 = random_string("tg-", uppercase=False)
        self._no_user = random_string("tg-", uppercase=False)
        self._group = random_string("tg-", uppercase=False)
        self._no_group = random_string("tg-", uppercase=False)
        _gid = _new_gid = None
        if not salt.utils.platform.is_windows():
            _gid = 64989
            _new_gid = 64998
        self._gid = _gid
        self._new_gid = _new_gid

    def tearDown(self):
        """
        Reset to original settings
        """
        self.run_function("user.delete", [self._user])
        self.run_function("user.delete", [self._user1])
        self.run_function("group.delete", [self._group])

    def __get_system_group_gid_range(self):
        """
        Returns (SYS_GID_MIN, SYS_GID_MAX)
        """
        try:
            login_defs = {}
            with salt.utils.files.fopen("/etc/login.defs") as defs_fd:
                for line in defs_fd:
                    line = salt.utils.stringutils.to_unicode(line).strip()
                    if line.startswith("#"):
                        continue
                    try:
                        key, val = line.split()
                    except ValueError:
                        pass
                    else:
                        login_defs[key] = val
        except OSError:
            login_defs = {"SYS_GID_MIN": 101, "SYS_GID_MAX": 999}

        gid_min = login_defs.get("SYS_GID_MIN", 101)
        gid_max = login_defs.get(
            "SYS_GID_MAX", int(login_defs.get("GID_MIN", 1000)) - 1
        )

        return int(gid_min), int(gid_max)

    def __get_free_system_gid(self):
        """
        Find a free system gid
        """

        gid_min, gid_max = self.__get_system_group_gid_range()

        busy_gids = [x.gr_gid for x in grp.getgrall() if gid_min <= x.gr_gid <= gid_max]

        # find free system gid
        for gid in range(gid_min, gid_max + 1):
            if gid not in busy_gids:
                return gid

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_add(self):
        """
        Test the add group function
        """
        # add a new group
        self.assertTrue(self.run_function("group.add", [self._group], gid=self._gid))
        group_info = self.run_function("group.info", [self._group])
        self.assertEqual(group_info["gid"], self._gid)
        self.assertEqual(group_info["name"], self._group)
        # try adding the group again
        self.assertFalse(self.run_function("group.add", [self._group], gid=self._gid))

    @pytest.mark.destructive_test
    @pytest.mark.skip_on_windows(reason="Skip on Windows")
    @pytest.mark.slow_test
    def test_add_system_group(self):
        """
        Test the add group function with system=True
        """

        gid_min, gid_max = self.__get_system_group_gid_range()

        # add a new system group
        self.assertTrue(self.run_function("group.add", [self._group, None, True]))
        group_info = self.run_function("group.info", [self._group])
        self.assertEqual(group_info["name"], self._group)
        self.assertTrue(gid_min <= group_info["gid"] <= gid_max)
        # try adding the group again
        self.assertFalse(self.run_function("group.add", [self._group]))

    @pytest.mark.destructive_test
    @pytest.mark.skip_on_windows(reason="Skip on Windows")
    @pytest.mark.slow_test
    def test_add_system_group_gid(self):
        """
        Test the add group function with system=True and a specific gid
        """

        gid = self.__get_free_system_gid()

        # add a new system group
        self.assertTrue(self.run_function("group.add", [self._group, gid, True]))
        group_info = self.run_function("group.info", [self._group])
        self.assertEqual(group_info["name"], self._group)
        self.assertEqual(group_info["gid"], gid)
        # try adding the group again
        self.assertFalse(self.run_function("group.add", [self._group, gid]))

    @pytest.mark.destructive_test
    @pytest.mark.slow_test
    def test_delete(self):
        """
        Test the delete group function
        """
        self.assertTrue(self.run_function("group.add", [self._group]))

        # correct functionality
        self.assertTrue(self.run_function("group.delete", [self._group]))

        # group does not exist
        self.assertFalse(self.run_function("group.delete", [self._no_group]))

    @pytest.mark.slow_test
    def test_info(self):
        """
        Test the info group function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.run_function("user.add", [self._user])
        self.run_function("group.adduser", [self._group, self._user])
        group_info = self.run_function("group.info", [self._group])

        self.assertEqual(group_info["name"], self._group)
        self.assertEqual(group_info["gid"], self._gid)
        self.assertIn(self._user, str(group_info["members"]))

    @pytest.mark.skip_on_windows(reason="gid test skipped on windows")
    @pytest.mark.slow_test
    def test_chgid(self):
        """
        Test the change gid function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.assertTrue(self.run_function("group.chgid", [self._group, self._new_gid]))
        group_info = self.run_function("group.info", [self._group])
        self.assertEqual(group_info["gid"], self._new_gid)

    @pytest.mark.slow_test
    def test_adduser(self):
        """
        Test the add user to group function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.run_function("user.add", [self._user])
        self.assertTrue(self.run_function("group.adduser", [self._group, self._user]))
        group_info = self.run_function("group.info", [self._group])
        self.assertIn(self._user, str(group_info["members"]))
        # try add a non existing user
        self.assertFalse(
            self.run_function("group.adduser", [self._group, self._no_user])
        )
        # try add a user to non existing group
        self.assertFalse(
            self.run_function("group.adduser", [self._no_group, self._user])
        )
        # try add a non existing user to a non existing group
        self.assertFalse(
            self.run_function("group.adduser", [self._no_group, self._no_user])
        )

    @pytest.mark.slow_test
    def test_deluser(self):
        """
        Test the delete user from group function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.run_function("user.add", [self._user])
        self.run_function("group.adduser", [self._group, self._user])
        self.assertTrue(self.run_function("group.deluser", [self._group, self._user]))
        group_info = self.run_function("group.info", [self._group])
        self.assertNotIn(self._user, str(group_info["members"]))

    @pytest.mark.slow_test
    def test_members(self):
        """
        Test the members function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.run_function("user.add", [self._user])
        self.run_function("user.add", [self._user1])
        m = "{},{}".format(self._user, self._user1)
        ret = self.run_function("group.members", [self._group, m])
        self.assertTrue(ret)
        group_info = self.run_function("group.info", [self._group])
        self.assertIn(self._user, str(group_info["members"]))
        self.assertIn(self._user1, str(group_info["members"]))

    @pytest.mark.slow_test
    def test_getent(self):
        """
        Test the getent function
        """
        self.run_function("group.add", [self._group], gid=self._gid)
        self.run_function("user.add", [self._user])
        self.run_function("group.adduser", [self._group, self._user])
        ginfo = self.run_function("user.getent")
        self.assertIn(self._group, str(ginfo))
        self.assertIn(self._user, str(ginfo))
        self.assertNotIn(self._no_group, str(ginfo))
        self.assertNotIn(self._no_user, str(ginfo))
