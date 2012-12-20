# Import python libs
import os
import string
import random

# Import salt libs
import integration
from saltunittest import destructiveTest, skipIf


class UseraddModuleTest(integration.ModuleCase):

    def setUp(self):
        super(UseraddModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain != 'FreeBSD':
            self.skipTest(
                'Test not applicable to \'{0}\' kernel'.format(
                    os_grain
                )
            )

    def __random_string(self, size=6):
        return ''.join(
            random.choice(string.ascii_uppercase + string.digits)
            for x in range(size)
        )

    @destructiveTest
    @skipIf(os.geteuid() is not 0, 'you must be root to run this test')
    def test_groups_includes_primary(self):
        # Let's create a user, which usually creates the group matching the
        # name
        uname = self.__random_string()
        if self.run_function('user.add', [uname]) is not True:
            # Skip because creating is not what we're testing here
            self.skipTest('Failed to create user')

        uinfo = self.run_function('user.info', [uname])
        self.assertIn(uname, uinfo['groups'])

        # This uid is available, store it
        uid = uinfo['uid']

        self.run_function('user.delete', [uname, True, True])

        # Now, a weird group id
        gname = self.__random_string()
        if self.run_function('group.add', [gname]) is not True:
            self.skipTest('Failed to create group')

        ginfo = self.run_function('group.info', [gname])

        # And create the user with that gid
        if self.run_function('user.add', [uname, uid, ginfo['gid']]) is False:
            # Skip because creating is not what we're testing here
            self.skipTest('Failed to create user')

        uinfo = self.run_function('user.info', [uname])
        self.assertIn(gname, uinfo['groups'])

        self.run_function('user.delete', [uname, True, True])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UseraddModuleTest)
