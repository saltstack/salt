# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import random
import string

import salt.ext.six as six
import salt.ext.six as six

# Import Salt Libs
import salt.utils.files
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import Salt Testing Libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root


def __random_string(size=6):
    """
    Generates a random username
    """
    return "RS-" + "".join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(size)
    )


# Create user strings for tests
ADD_USER = __random_string()
DEL_USER = __random_string()
PRIMARY_GROUP_USER = __random_string()
CHANGE_USER = __random_string()


@destructiveTest
@skip_if_not_root
class MacUserModuleTest(ModuleCase):
    """
    Integration tests for the mac_user module
    """

    def setUp(self):
        """
        Sets up test requirements
        """
        super(MacUserModuleTest, self).setUp()
        os_grain = self.run_function("grains.item", ["kernel"])
        if os_grain["kernel"] not in "Darwin":
            self.skipTest("Test not applicable to '{kernel}' kernel".format(**os_grain))

    def test_mac_user_add(self):
        """
        Tests the add function
        """
        try:
            self.run_function("user.add", [ADD_USER])
            user_info = self.run_function("user.info", [ADD_USER])
            self.assertEqual(ADD_USER, user_info["name"])
        except CommandExecutionError:
            self.run_function("user.delete", [ADD_USER])
            raise

    def test_mac_user_delete(self):
        """
        Tests the delete function
        """

        # Create a user to delete - If unsuccessful, skip the test
        if self.run_function("user.add", [DEL_USER]) is not True:
            self.run_function("user.delete", [DEL_USER])
            self.skipTest("Failed to create a user to delete")

        # Now try to delete the added user
        ret = self.run_function("user.delete", [DEL_USER])
        self.assertTrue(ret)

    def test_mac_user_primary_group(self):
        """
        Tests the primary_group function
        """

        # Create a user to test primary group function
        if self.run_function("user.add", [PRIMARY_GROUP_USER]) is not True:
            self.run_function("user.delete", [PRIMARY_GROUP_USER])
            self.skipTest("Failed to create a user")

        try:
            # Test mac_user.primary_group
            primary_group = self.run_function(
                "user.primary_group", [PRIMARY_GROUP_USER]
            )
            uid_info = self.run_function("user.info", [PRIMARY_GROUP_USER])
            self.assertIn(primary_group, uid_info["groups"])

        except AssertionError:
            self.run_function("user.delete", [PRIMARY_GROUP_USER])
            raise

    def test_mac_user_changes(self):
        """
        Tests mac_user functions that change user properties
        """
        # Create a user to manipulate - if unsuccessful, skip the test
        if self.run_function("user.add", [CHANGE_USER]) is not True:
            self.run_function("user.delete", [CHANGE_USER])
            self.skipTest("Failed to create a user")

        try:
            # Test mac_user.chuid
            self.run_function("user.chuid", [CHANGE_USER, 4376])
            uid_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(uid_info["uid"], 4376)

            # Test mac_user.chgid
            self.run_function("user.chgid", [CHANGE_USER, 4376])
            gid_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(gid_info["gid"], 4376)

            # Test mac.user.chshell
            self.run_function("user.chshell", [CHANGE_USER, "/bin/zsh"])
            shell_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(shell_info["shell"], "/bin/zsh")

            # Test mac_user.chhome
            self.run_function("user.chhome", [CHANGE_USER, "/Users/foo"])
            home_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(home_info["home"], "/Users/foo")

            # Test mac_user.chfullname
            self.run_function("user.chfullname", [CHANGE_USER, "Foo Bar"])
            fullname_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(fullname_info["fullname"], "Foo Bar")

            # Test mac_user.chgroups
            self.run_function("user.chgroups", [CHANGE_USER, "wheel"])
            groups_info = self.run_function("user.info", [CHANGE_USER])
            self.assertEqual(groups_info["groups"], ["wheel"])

        except AssertionError:
            self.run_function("user.delete", [CHANGE_USER])
            raise

    def test_mac_user_enable_auto_login(self):
        """
        Tests mac_user functions that enable auto login
        """
        # Make sure auto login is disabled before we start
        if self.run_function("user.get_auto_login"):
            self.skipTest("Auto login already enabled")

        try:
            # Does enable return True
            self.assertTrue(
                self.run_function(
                    "user.enable_auto_login", ["Spongebob", "Squarepants"]
                )
            )

            # Did it set the user entry in the plist file
            self.assertEqual(self.run_function("user.get_auto_login"), "Spongebob")

            # Did it generate the `/etc/kcpassword` file
            self.assertTrue(os.path.exists("/etc/kcpassword"))

            # Are the contents of the file correct
            if six.PY2:
                test_data = b".\xf8'B\xa0\xd9\xad\x8b\xcd\xcdl"
            else:
                test_data = (
                    b".\xc3\xb8'B\xc2\xa0\xc3\x99\xc2\xad\xc2\x8b\xc3\x8d\xc3\x8dl"
                )
            with salt.utils.files.fopen(
                "/etc/kcpassword", "r" if six.PY2 else "rb"
            ) as f:
                file_data = f.read()
            self.assertEqual(test_data, file_data)

            # Does disable return True
            self.assertTrue(self.run_function("user.disable_auto_login"))

            # Does it remove the user entry in the plist file
            self.assertFalse(self.run_function("user.get_auto_login"))

            # Is the `/etc/kcpassword` file removed
            self.assertFalse(os.path.exists("/etc/kcpassword"))

        finally:
            # Make sure auto_login is disabled
            self.assertTrue(self.run_function("user.disable_auto_login"))

            # Make sure autologin is disabled
            if self.run_function("user.get_auto_login"):
                raise Exception("Failed to disable auto login")

    def test_mac_user_disable_auto_login(self):
        """
        Tests mac_user functions that disable auto login
        """
        # Make sure auto login is enabled before we start
        # Is there an existing setting
        if self.run_function("user.get_auto_login"):
            self.skipTest("Auto login already enabled")

        try:
            # Enable auto login for the test
            self.run_function("user.enable_auto_login", ["Spongebob", "Squarepants"])

            # Make sure auto login got set up
            if not self.run_function("user.get_auto_login") == "Spongebob":
                raise Exception("Failed to enable auto login")

            # Does disable return True
            self.assertTrue(self.run_function("user.disable_auto_login"))

            # Does it remove the user entry in the plist file
            self.assertFalse(self.run_function("user.get_auto_login"))

            # Is the `/etc/kcpassword` file removed
            self.assertFalse(os.path.exists("/etc/kcpassword"))

        finally:
            # Make sure auto login is disabled
            self.assertTrue(self.run_function("user.disable_auto_login"))

            # Make sure auto login is disabled
            if self.run_function("user.get_auto_login"):
                raise Exception("Failed to disable auto login")

    def tearDown(self):
        """
        Clean up after tests
        """

        # Delete ADD_USER
        add_info = self.run_function("user.info", [ADD_USER])
        if add_info:
            self.run_function("user.delete", [ADD_USER])

        # Delete DEL_USER if something failed
        del_info = self.run_function("user.info", [DEL_USER])
        if del_info:
            self.run_function("user.delete", [DEL_USER])

        # Delete CHANGE_USER
        change_info = self.run_function("user.info", [CHANGE_USER])
        if change_info:
            self.run_function("user.delete", [CHANGE_USER])
