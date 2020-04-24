# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    tests.integration.modules.pw_user
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, random_string, skip_if_not_root


@pytest.mark.skip_unless_on_freebsd
class PwUserModuleTest(ModuleCase):
    def setUp(self):
        super(PwUserModuleTest, self).setUp()
        os_grain = self.run_function("grains.item", ["kernel"])
        if os_grain["kernel"] != "FreeBSD":
            self.skipTest("Test not applicable to '{kernel}' kernel".format(**os_grain))

    @destructiveTest
    @skip_if_not_root
    def test_groups_includes_primary(self):
        # Let's create a user, which usually creates the group matching the name
        uname = random_string("PWU-", lowercase=False)
        if self.run_function("user.add", [uname]) is not True:
            # Skip because creating is not what we're testing here
            self.run_function("user.delete", [uname, True, True])
            self.skipTest("Failed to create user")

        try:
            uinfo = self.run_function("user.info", [uname])
            self.assertIn(uname, uinfo["groups"])

            # This uid is available, store it
            uid = uinfo["uid"]

            self.run_function("user.delete", [uname, True, True])

            # Now, a weird group id
            gname = random_string("PWU-", lowercase=False)
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
