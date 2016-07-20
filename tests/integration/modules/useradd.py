# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import string
import random

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)
ensure_in_syspath('../../')

# Import salt libs
import integration

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


class UseraddModuleTest(integration.ModuleCase):

    def setUp(self):
        super(UseraddModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in ('Linux', 'Darwin'):
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )

    def __random_string(self, size=6):
        return 'RS-' + ''.join(
            random.choice(string.ascii_uppercase + string.digits)
            for x in range(size)
        )

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @requires_system_grains
    def test_groups_includes_primary(self, grains=None):
        # Let's create a user, which usually creates the group matching the
        # name
        uname = self.__random_string()
        if self.run_function('user.add', [uname]) is not True:
            # Skip because creating is not what we're testing here
            self.run_function('user.delete', [uname, True, True])
            self.skipTest('Failed to create user')

        try:
            uinfo = self.run_function('user.info', [uname])
            if grains['os_family'] in ('Suse',):
                self.assertIn('users', uinfo['groups'])
            else:
                self.assertIn(uname, uinfo['groups'])

            # This uid is available, store it
            uid = uinfo['uid']

            self.run_function('user.delete', [uname, True, True])

            # Now, a weird group id
            gname = self.__random_string()
            if self.run_function('group.add', [gname]) is not True:
                self.run_function('group.delete', [gname, True, True])
                self.skipTest('Failed to create group')

            ginfo = self.run_function('group.info', [gname])

            # And create the user with that gid
            if self.run_function('user.add', [uname, uid, ginfo['gid']]) is False:
                # Skip because creating is not what we're testing here
                self.run_function('user.delete', [uname, True, True])
                self.skipTest('Failed to create user')

            uinfo = self.run_function('user.info', [uname])
            self.assertIn(gname, uinfo['groups'])

        except AssertionError:
            self.run_function('user.delete', [uname, True, True])
            raise


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UseraddModuleTest)
