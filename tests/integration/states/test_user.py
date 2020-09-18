"""
tests for user state
user absent
user present
user present with custom homedir
"""


import os
import sys
from random import randint

import pytest
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import (
    destructiveTest,
    requires_system_grains,
    skip_if_not_root,
    slowTest,
)
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.unit import skipIf

try:
    import grp
except ImportError:
    grp = None

if salt.utils.platform.is_darwin():
    USER = "macuser"
    GROUP = "macuser"
    GID = randint(400, 500)
    NOGROUPGID = randint(400, 500)
elif salt.utils.platform.is_windows():
    USER = "winuser"
    GROUP = "winuser"
    GID = randint(400, 500)
    NOGROUPGID = randint(400, 500)
else:
    USER = "nobody"
    GROUP = "nobody"
    GID = "nobody"
    NOGROUPGID = "nogroup"


@destructiveTest
@skip_if_not_root
@pytest.mark.windows_whitelisted
class UserTest(ModuleCase, SaltReturnAssertsMixin):
    """
    test for user absent
    """

    user_name = "salt-test"
    alt_group = "salt-test-altgroup"
    user_home = (
        "/var/lib/{}".format(user_name)
        if not salt.utils.platform.is_windows()
        else os.path.join("tmp", user_name)
    )

    @slowTest
    def test_user_absent(self):
        ret = self.run_state("user.absent", name="unpossible")
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_user_if_present(self):
        ret = self.run_state("user.present", name=USER)
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_user_if_present_with_gid(self):
        if self.run_function("group.info", [USER]):
            ret = self.run_state("user.present", name=USER, gid=GID)
        elif self.run_function("group.info", ["nogroup"]):
            ret = self.run_state("user.present", name=USER, gid=NOGROUPGID)
        else:
            self.skipTest("Neither 'nobody' nor 'nogroup' are valid groups")
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_user_not_present(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        """
        ret = self.run_state("user.present", name=self.user_name)
        self.assertSaltTrueReturn(ret)

    @slowTest
    def test_user_present_when_home_dir_does_not_18843(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        """
        if salt.utils.platform.is_darwin():
            HOMEDIR = "/Users/home_of_" + self.user_name
        else:
            HOMEDIR = "/home/home_of_" + self.user_name
        ret = self.run_state("user.present", name=self.user_name, home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

        self.run_function("file.absent", name=HOMEDIR)
        ret = self.run_state("user.present", name=self.user_name, home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

    @requires_system_grains
    @slowTest
    def test_user_present_nondefault(self, grains=None):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        """
        ret = self.run_state("user.present", name=self.user_name, home=self.user_home)
        self.assertSaltTrueReturn(ret)
        ret = self.run_function("user.info", [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        if salt.utils.platform.is_windows():
            group_name = self.run_function("user.list_groups", [self.user_name])
        else:
            group_name = grp.getgrgid(ret["gid"]).gr_name

        if not salt.utils.platform.is_darwin() and not salt.utils.platform.is_windows():
            self.assertTrue(os.path.isdir(self.user_home))
        if grains["os_family"] in ("Suse",):
            self.assertEqual(group_name, "users")
        elif grains["os_family"] == "MacOS":
            self.assertEqual(group_name, "staff")
        elif salt.utils.platform.is_windows():
            self.assertEqual([], group_name)
        else:
            self.assertEqual(group_name, self.user_name)

    @skipIf(
        salt.utils.platform.is_windows(), "windows minion does not support usergroup"
    )
    @slowTest
    def test_user_present_usergroup_false(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test. We create a group of the
        same name as the user beforehand, so it should all run smoothly.
        """
        # MacOS users' primary group defaults to staff (20), not the name of
        # user
        ret = self.run_state("group.present", name=self.user_name)
        self.assertSaltTrueReturn(ret)
        if salt.utils.platform.is_darwin():
            gid = grp.getgrnam("staff").gr_gid
        else:
            gid = self.user_name
        ret = self.run_state(
            "user.present",
            name=self.user_name,
            gid=gid,
            usergroup=False,
            home=self.user_home,
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_function("user.info", [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret["gid"]).gr_name
        if not salt.utils.platform.is_darwin():
            self.assertTrue(os.path.isdir(self.user_home))
            self.assertEqual(group_name, self.user_name)
        ret = self.run_state("user.absent", name=self.user_name)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state("group.absent", name=self.user_name)
        self.assertSaltTrueReturn(ret)

    @skipIf(
        salt.utils.platform.is_windows(),
        "windows minion does not support gid_from_name",
    )
    @skipIf(
        salt.utils.platform.is_windows(), "windows minion does not support usergroup"
    )
    def test_user_present_usergroup(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test.
        """
        ret = self.run_state(
            "user.present", name=self.user_name, usergroup=True, home=self.user_home
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_function("user.info", [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret["gid"]).gr_name

        if not salt.utils.platform.is_darwin():
            self.assertTrue(os.path.isdir(self.user_home))
        if salt.utils.platform.is_darwin():
            group_name = "staff"
        else:
            group_name = self.user_name
        self.assertEqual(group_name, group_name)
        ret = self.run_state("user.absent", name=self.user_name)
        self.assertSaltTrueReturn(ret)
        if not salt.utils.platform.is_darwin():
            ret = self.run_state("group.absent", name=self.user_name)
            self.assertSaltTrueReturn(ret)

    @skipIf(
        sys.getfilesystemencoding().startswith("ANSI"),
        "A system encoding which supports Unicode characters must be set. Current setting is: {}. Try setting $LANG='en_US.UTF-8'".format(
            sys.getfilesystemencoding()
        ),
    )
    @slowTest
    def test_user_present_unicode(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that unicode GECOS data will be properly handled, without
        any encoding-related failures.
        """
        ret = self.run_state(
            "user.present",
            name=self.user_name,
            fullname="Sålt Test",
            roomnumber="①②③",
            workphone="١٢٣٤",
            homephone="६७८",
        )
        self.assertSaltTrueReturn(ret)
        # Ensure updating a user also works
        ret = self.run_state(
            "user.present",
            name=self.user_name,
            fullname="Sølt Test",
            roomnumber="①③②",
            workphone="٣٤١٢",
            homephone="६८७",
        )
        self.assertSaltTrueReturn(ret)

    @skipIf(
        salt.utils.platform.is_windows(),
        "windows minion does not support roomnumber or phone",
    )
    @slowTest
    def test_user_present_gecos(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that numeric GECOS data will be properly coerced to strings,
        otherwise the state will fail because the GECOS fields are written as
        strings (and show up in the user.info output as such). Thus the
        comparison will fail, since '12345' != 12345.
        """
        ret = self.run_state(
            "user.present",
            name=self.user_name,
            fullname=12345,
            roomnumber=123,
            workphone=1234567890,
            homephone=1234567890,
        )
        self.assertSaltTrueReturn(ret)

    @skipIf(
        salt.utils.platform.is_windows(),
        "windows minion does not support roomnumber or phone",
    )
    @slowTest
    def test_user_present_gecos_empty_fields(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that if no GECOS data is supplied, the fields will be coerced
        into empty strings as opposed to the string "None".
        """
        ret = self.run_state(
            "user.present",
            name=self.user_name,
            fullname="",
            roomnumber="",
            workphone="",
            homephone="",
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_function("user.info", [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual("", ret["fullname"])
        # MacOS does not supply the following GECOS fields
        if not salt.utils.platform.is_darwin():
            self.assertEqual("", ret["roomnumber"])
            self.assertEqual("", ret["workphone"])
            self.assertEqual("", ret["homephone"])

    @skipIf(
        salt.utils.platform.is_windows(), "windows minion does not support createhome"
    )
    @slowTest
    def test_user_present_home_directory_created(self):
        """
        This is a DESTRUCTIVE TEST it creates a new user on the minion.

        It ensures that the home directory is created.
        """
        ret = self.run_state("user.present", name=self.user_name, createhome=True)
        self.assertSaltTrueReturn(ret)

        user_info = self.run_function("user.info", [self.user_name])
        self.assertTrue(os.path.exists(user_info["home"]))

    @skipIf(not salt.utils.platform.is_linux(), "only supported on linux")
    def test_user_present_gid_from_name(self):
        """
        Test that gid_from_name results in warning, while it is on a
        deprecation path.
        """
        # Add the user
        ret = self.run_state("user.present", name=self.user_name, gid_from_name=True)
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        expected = [
            "The 'gid_from_name' argument in the user.present state has been "
            "replaced with 'usergroup'. Update your SLS file to get rid of "
            "this warning."
        ]
        assert ret["warnings"] == expected, ret["warnings"]

    @skipIf(not salt.utils.platform.is_linux(), "only supported on linux")
    def test_user_present_gid_from_name_and_usergroup(self):
        """
        Test that gid_from_name results in warning, while it is on a
        deprecation path.
        """
        # Add the user
        ret = self.run_state(
            "user.present", name=self.user_name, usergroup=True, gid_from_name=True
        )
        self.assertSaltTrueReturn(ret)
        ret = ret[next(iter(ret))]
        expected = [
            "The 'gid_from_name' argument in the user.present state has been "
            "replaced with 'usergroup'. Ignoring since 'usergroup' was also "
            "used."
        ]
        assert ret["warnings"] == expected, ret["warnings"]

    @skipIf(
        salt.utils.platform.is_windows() or salt.utils.platform.is_darwin(),
        "groups/gid not fully supported",
    )
    def test_user_present_change_gid_but_keep_group(self):
        """
        This tests the case in which the default group is changed at the same
        time as it is also moved into the "groups" list.
        """
        try:
            # Add the groups
            ret = self.run_state("group.present", name=self.user_name)
            self.assertSaltTrueReturn(ret)
            ret = self.run_state("group.present", name=self.alt_group)
            self.assertSaltTrueReturn(ret)

            user_name_gid = self.run_function("file.group_to_gid", [self.user_name])
            alt_group_gid = self.run_function("file.group_to_gid", [self.alt_group])

            # Add the user
            ret = self.run_state("user.present", name=self.user_name, gid=alt_group_gid)

            # Check that the initial user addition set the gid and groups as
            # expected.
            new_gid = self.run_function("file.group_to_gid", [self.user_name])
            uinfo = self.run_function("user.info", [self.user_name])

            assert uinfo["gid"] == alt_group_gid, uinfo["gid"]
            assert uinfo["groups"] == [self.alt_group], uinfo["groups"]

            # Now change the gid and move alt_group to the groups list in the
            # same salt run.
            ret = self.run_state(
                "user.present",
                name=self.user_name,
                gid=user_name_gid,
                groups=[self.alt_group],
                allow_gid_change=True,
            )
            self.assertSaltTrueReturn(ret)

            # Be sure that we did what we intended
            new_gid = self.run_function("file.group_to_gid", [self.user_name])
            uinfo = self.run_function("user.info", [self.user_name])

            assert uinfo["gid"] == new_gid, uinfo["gid"]
            assert uinfo["groups"] == [self.user_name, self.alt_group], uinfo["groups"]

        finally:
            # Do the cleanup here so we don't have to put all of this in the
            # tearDown to be executed after each test.
            self.assertSaltTrueReturn(
                self.run_state("user.absent", name=self.user_name)
            )
            self.assertSaltTrueReturn(
                self.run_state("group.absent", name=self.user_name)
            )
            self.assertSaltTrueReturn(
                self.run_state("group.absent", name=self.alt_group)
            )

    def tearDown(self):
        if salt.utils.platform.is_darwin():
            check_user = self.run_function("user.list_users")
            if USER in check_user:
                del_user = self.run_function("user.delete", [USER], remove=True)
        self.assertSaltTrueReturn(self.run_state("user.absent", name=self.user_name))
        self.assertSaltTrueReturn(self.run_state("group.absent", name=self.user_name))


@destructiveTest
@skip_if_not_root
@skipIf(not salt.utils.platform.is_windows(), "Windows only tests")
@pytest.mark.windows_whitelisted
class WinUserTest(ModuleCase, SaltReturnAssertsMixin):
    """
    test for user absent
    """

    def tearDown(self):
        self.assertSaltTrueReturn(self.run_state("user.absent", name=USER))

    @slowTest
    def test_user_present_existing(self):
        ret = self.run_state(
            "user.present",
            name=USER,
            win_homedrive="U:",
            win_profile="C:\\User\\{}".format(USER),
            win_logonscript="C:\\logon.vbs",
            win_description="Test User Account",
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "user.present",
            name=USER,
            win_homedrive="R:",
            win_profile="C:\\Users\\{}".format(USER),
            win_logonscript="C:\\Windows\\logon.vbs",
            win_description="Temporary Account",
        )
        self.assertSaltTrueReturn(ret)
        self.assertSaltStateChangesEqual(ret, "R:", keys=["homedrive"])
        self.assertSaltStateChangesEqual(
            ret, "C:\\Users\\{}".format(USER), keys=["profile"]
        )
        self.assertSaltStateChangesEqual(
            ret, "C:\\Windows\\logon.vbs", keys=["logonscript"]
        )
        self.assertSaltStateChangesEqual(ret, "Temporary Account", keys=["description"])
