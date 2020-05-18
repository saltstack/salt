# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    random_string,
    requires_system_grains,
    runs_on,
    skip_if_not_root,
    slowTest,
)


@destructiveTest
@skip_if_not_root
@runs_on(kernel="Linux")
class UseraddModuleTestLinux(ModuleCase):
    @requires_system_grains
    @slowTest
    def test_groups_includes_primary(self, grains):
        # Let's create a user, which usually creates the group matching the
        # name
        uname = random_string("RS-", lowercase=False)
        if self.run_function("user.add", [uname]) is not True:
            # Skip because creating is not what we're testing here
            self.run_function("user.delete", [uname, True, True])
            self.skipTest("Failed to create user")

        try:
            uinfo = self.run_function("user.info", [uname])
            if grains["os_family"] in ("Suse",):
                self.assertIn("users", uinfo["groups"])
            else:
                self.assertIn(uname, uinfo["groups"])

            # This uid is available, store it
            uid = uinfo["uid"]

            self.run_function("user.delete", [uname, True, True])

            # Now, a weird group id
            gname = random_string("RS-", lowercase=False)
            if self.run_function("group.add", [gname]) is not True:
                self.run_function("group.delete", [gname, True, True])
                self.skipTest("Failed to create group")

            ginfo = self.run_function("group.info", [gname])

            # And create the user with that gid
            if self.run_function("user.add", [uname, uid, ginfo["gid"]]) is False:
                # Skip because creating is not what we're testing here
                self.run_function("user.delete", [uname, True, True])
                self.skipTest("Failed to create user")

            uinfo = self.run_function("user.info", [uname])
            self.assertIn(gname, uinfo["groups"])

        except AssertionError:
            self.run_function("user.delete", [uname, True, True])
            raise

    @slowTest
    def test_user_primary_group(self):
        """
        Tests the primary_group function
        """
        name = "saltyuser"

        # Create a user to test primary group function
        if self.run_function("user.add", [name]) is not True:
            self.run_function("user.delete", [name])
            self.skipTest("Failed to create a user")

        try:
            # Test useradd.primary_group
            primary_group = self.run_function("user.primary_group", [name])
            uid_info = self.run_function("user.info", [name])
            self.assertIn(primary_group, uid_info["groups"])

        except Exception:  # pylint: disable=broad-except
            self.run_function("user.delete", [name])
            raise


@destructiveTest
@skip_if_not_root
@runs_on(kernel="Windows")
@pytest.mark.windows_whitelisted
class UseraddModuleTestWindows(ModuleCase):
    def setUp(self):
        self.user_name = random_string("RS-", lowercase=False)
        self.group_name = random_string("RS-", lowercase=False)

    def tearDown(self):
        self.run_function("user.delete", [self.user_name, True, True])
        self.run_function("group.delete", [self.group_name])

    def _add_user(self):
        """
        helper class to add user
        """
        if self.run_function("user.add", [self.user_name]) is False:
            # Skip because creating is not what we're testing here
            self.skipTest("Failed to create user")

    def _add_group(self):
        """
        helper class to add group
        """
        if self.run_function("group.add", [self.group_name]) is False:
            # Skip because creating is not what we're testing here
            self.skipTest("Failed to create group")

    @slowTest
    def test_add_user(self):
        """
        Test adding a user
        """
        self._add_user()
        user_list = self.run_function("user.list_users")
        self.assertIn(self.user_name, user_list)

    @slowTest
    def test_add_group(self):
        """
        Test adding a user
        """
        self._add_group()
        group_list = self.run_function("group.list_groups")
        self.assertIn(self.group_name, group_list)

    @slowTest
    def test_add_user_to_group(self):
        """
        Test adding a user to a group
        """
        self._add_group()
        # And create the user as a member of that group
        self.run_function("user.add", [self.user_name], groups=self.group_name)
        user_info = self.run_function("user.info", [self.user_name])
        self.assertIn(self.group_name, user_info["groups"])

    @slowTest
    def test_add_user_addgroup(self):
        """
        Test adding a user to a group with groupadd
        """
        self._add_group()
        self._add_user()
        self.run_function("user.addgroup", [self.user_name, self.group_name])
        info = self.run_function("user.info", [self.user_name])
        self.assertEqual(info["groups"], [self.group_name])

    @slowTest
    def test_user_chhome(self):
        """
        Test changing a users home dir
        """
        self._add_user()
        user_dir = r"c:\salt"
        self.run_function("user.chhome", [self.user_name, user_dir])
        info = self.run_function("user.info", [self.user_name])
        self.assertEqual(info["home"], user_dir)

    @slowTest
    def test_user_chprofile(self):
        """
        Test changing a users profile
        """
        self._add_user()
        config = r"c:\salt\config"
        self.run_function("user.chprofile", [self.user_name, config])
        info = self.run_function("user.info", [self.user_name])
        self.assertEqual(info["profile"], config)

    @slowTest
    def test_user_chfullname(self):
        """
        Test changing a users fullname
        """
        self._add_user()
        name = "Salt Test"
        self.run_function("user.chfullname", [self.user_name, name])
        info = self.run_function("user.info", [self.user_name])
        self.assertEqual(info["fullname"], name)

    @slowTest
    def test_user_delete(self):
        """
        Test deleting a user
        """
        self._add_user()
        self.assertTrue(self.run_function("user.info", [self.user_name])["active"])
        self.run_function("user.delete", [self.user_name])
        self.assertEqual({}, self.run_function("user.info", [self.user_name]))

    @slowTest
    def test_user_removegroup(self):
        """
        Test removing a group
        """
        self._add_user()
        self._add_group()
        self.run_function("user.addgroup", [self.user_name, self.group_name])
        self.assertIn(
            self.group_name, self.run_function("user.list_groups", [self.user_name])
        )
        self.run_function("user.removegroup", [self.user_name, self.group_name])
        self.assertNotIn(
            self.group_name, self.run_function("user.list_groups", [self.user_name])
        )

    @slowTest
    def test_user_rename(self):
        """
        Test changing a users name
        """
        self._add_user()
        name = "newuser"
        self.run_function("user.rename", [self.user_name, name])
        info = self.run_function("user.info", [name])
        self.assertTrue(info["active"])

        # delete new user
        self.run_function("user.delete", [name, True, True])

    @slowTest
    def test_user_setpassword(self):
        """
        Test setting a password
        """
        self._add_user()
        passwd = "sup3rs3cr3T!"
        self.assertTrue(self.run_function("user.setpassword", [self.user_name, passwd]))
