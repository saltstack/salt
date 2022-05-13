"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import pytest
from salt.exceptions import CommandExecutionError
from tests.support.case import ModuleCase
from tests.support.helpers import random_string, runs_on

# Create group name strings for tests
ADD_GROUP = random_string("RS-", lowercase=False)
DEL_GROUP = random_string("RS-", lowercase=False)
CHANGE_GROUP = random_string("RS-", lowercase=False)
ADD_USER = random_string("RS-", lowercase=False)
REP_USER_GROUP = random_string("RS-", lowercase=False)


@pytest.mark.skip_if_not_root
@runs_on(kernel="Darwin")
@pytest.mark.destructive_test
class MacGroupModuleTest(ModuleCase):
    """
    Integration tests for the mac_group module
    """

    def setUp(self):
        """
        Sets up test requirements
        """
        os_grain = self.run_function("grains.item", ["kernel"])
        if os_grain["kernel"] not in "Darwin":
            self.skipTest("Test not applicable to '{kernel}' kernel".format(**os_grain))

    @pytest.mark.slow_test
    def test_mac_group_add(self):
        """
        Tests the add group function
        """
        try:
            self.run_function("group.add", [ADD_GROUP, 3456])
            group_info = self.run_function("group.info", [ADD_GROUP])
            self.assertEqual(group_info["name"], ADD_GROUP)
        except CommandExecutionError:
            self.run_function("group.delete", [ADD_GROUP])
            raise

    @pytest.mark.slow_test
    def test_mac_group_delete(self):
        """
        Tests the delete group function
        """
        # Create a group to delete - If unsuccessful, skip the test
        if self.run_function("group.add", [DEL_GROUP, 4567]) is not True:
            self.run_function("group.delete", [DEL_GROUP])
            self.skipTest("Failed to create a group to delete")

        # Now try to delete the added group
        ret = self.run_function("group.delete", [DEL_GROUP])
        self.assertTrue(ret)

    @pytest.mark.slow_test
    def test_mac_group_chgid(self):
        """
        Tests changing the group id
        """
        # Create a group to delete - If unsuccessful, skip the test
        if self.run_function("group.add", [CHANGE_GROUP, 5678]) is not True:
            self.run_function("group.delete", [CHANGE_GROUP])
            self.skipTest("Failed to create a group to manipulate")

        try:
            self.run_function("group.chgid", [CHANGE_GROUP, 6789])
            group_info = self.run_function("group.info", [CHANGE_GROUP])
            self.assertEqual(group_info["gid"], 6789)
        except AssertionError:
            self.run_function("group.delete", [CHANGE_GROUP])
            raise

    @pytest.mark.slow_test
    def test_mac_adduser(self):
        """
        Tests adding user to the group
        """
        # Create a group to use for test - If unsuccessful, skip the test
        if self.run_function("group.add", [ADD_GROUP, 5678]) is not True:
            self.run_function("group.delete", [ADD_GROUP])
            self.skipTest("Failed to create a group to manipulate")

        try:
            self.run_function("group.adduser", [ADD_GROUP, ADD_USER])
            group_info = self.run_function("group.info", [ADD_GROUP])
            self.assertEqual(ADD_USER, "".join(group_info["members"]))
        except AssertionError:
            self.run_function("group.delete", [ADD_GROUP])
            raise

    @pytest.mark.slow_test
    def test_mac_deluser(self):
        """
        Test deleting user from a group
        """
        # Create a group to use for test - If unsuccessful, skip the test
        if (
            self.run_function("group.add", [ADD_GROUP, 5678])
            and self.run_function("group.adduser", [ADD_GROUP, ADD_USER]) is not True
        ):
            self.run_function("group.delete", [ADD_GROUP])
            self.skipTest("Failed to create a group to manipulate")

        delusr = self.run_function("group.deluser", [ADD_GROUP, ADD_USER])
        self.assertTrue(delusr)

        group_info = self.run_function("group.info", [ADD_GROUP])
        self.assertNotIn(ADD_USER, "".join(group_info["members"]))

    @pytest.mark.slow_test
    def test_mac_members(self):
        """
        Test replacing members of a group
        """
        if (
            self.run_function("group.add", [ADD_GROUP, 5678])
            and self.run_function("group.adduser", [ADD_GROUP, ADD_USER]) is not True
        ):
            self.run_function("group.delete", [ADD_GROUP])
            self.skipTest(
                "Failed to create the {} group or add user {} to group "
                "to manipulate".format(ADD_GROUP, ADD_USER)
            )

        rep_group_mem = self.run_function("group.members", [ADD_GROUP, REP_USER_GROUP])
        self.assertTrue(rep_group_mem)

        # ensure new user is added to group and previous user is removed
        group_info = self.run_function("group.info", [ADD_GROUP])
        self.assertIn(REP_USER_GROUP, str(group_info["members"]))
        self.assertNotIn(ADD_USER, str(group_info["members"]))

    @pytest.mark.slow_test
    def test_mac_getent(self):
        """
        Test returning info on all groups
        """
        if (
            self.run_function("group.add", [ADD_GROUP, 5678])
            and self.run_function("group.adduser", [ADD_GROUP, ADD_USER]) is not True
        ):
            self.run_function("group.delete", [ADD_GROUP])
            self.skipTest(
                "Failed to create the {} group or add user {} to group "
                "to manipulate".format(ADD_GROUP, ADD_USER)
            )

        getinfo = self.run_function("group.getent")
        self.assertTrue(getinfo)
        self.assertIn(ADD_GROUP, str(getinfo))
        self.assertIn(ADD_USER, str(getinfo))

    def tearDown(self):
        """
        Clean up after tests
        """
        # Delete ADD_GROUP
        add_info = self.run_function("group.info", [ADD_GROUP])
        if add_info:
            self.run_function("group.delete", [ADD_GROUP])

        # Delete DEL_GROUP if something failed
        del_info = self.run_function("group.info", [DEL_GROUP])
        if del_info:
            self.run_function("group.delete", [DEL_GROUP])

        # Delete CHANGE_GROUP
        change_info = self.run_function("group.info", [CHANGE_GROUP])
        if change_info:
            self.run_function("group.delete", [CHANGE_GROUP])
