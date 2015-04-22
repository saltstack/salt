# -*- coding: utf-8 -*-

'''
tests for user state
user absent
user present
user present with custom homedir
'''

# Import python libs
import os
import grp

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


class UserTest(integration.ModuleCase,
               integration.SaltReturnAssertsMixIn):
    '''
    test for user absent
    '''
    def test_user_absent(self):
        ret = self.run_state('user.absent', name='unpossible')
        self.assertSaltTrueReturn(ret)

    def test_user_if_present(self):
        ret = self.run_state('user.present', name='nobody')
        self.assertSaltTrueReturn(ret)

    def test_user_if_present_with_gid(self):
        if self.run_function('group.info', ['nobody']):
            ret = self.run_state('user.present', name='nobody', gid='nobody')
        elif self.run_function('group.info', ['nogroup']):
            ret = self.run_state('user.present', name='nobody', gid='nogroup')
        else:
            self.skipTest(
                'Neither \'nobody\' nor \'nogroup\' are valid groups'
            )
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_user_not_present(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        '''
        ret = self.run_state('user.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_user_present_when_home_dir_does_not_18843(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        '''
        HOMEDIR = '/tmp/home_of_salt_test'
        ret = self.run_state('user.present', name='salt_test',
                             home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

        self.run_function('file.absent', name=HOMEDIR)
        ret = self.run_state('user.present', name='salt_test',
                             home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_user_present_nondefault(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        '''
        ret = self.run_state('user.present', name='salt_test',
                             home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    @requires_system_grains
    def test_user_present_gid_from_name_default(self, grains=None):
        '''
        This is a DESTRUCTIVE TEST. It creates a new user on the on the minion.
        This is an integration test. Not all systems will automatically create
        a group of the same name as the user, but I don't have access to any.
        If you run the test and it fails, please fix the code it's testing to
        work on your operating system.
        '''
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        if grains['os_family'] in ('Suse',):
            self.assertEqual(group_name, 'users')
        else:
            self.assertEqual(group_name, 'salt_test')

        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_user_present_gid_from_name(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test. We create a group of the
        same name as the user beforehand, so it should all run smoothly.
        '''
        ret = self.run_state('group.present', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.present', name='salt_test',
                             gid_from_name=True, home='/var/lib/salt_test')
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', ['salt_test'])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir('/var/lib/salt_test'))
        self.assertEqual(group_name, 'salt_test')
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_user_present_gecos(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that numeric GECOS data will be properly coerced to strings,
        otherwise the state will fail because the GECOS fields are written as
        strings (and show up in the user.info output as such). Thus the
        comparison will fail, since '12345' != 12345.
        '''
        ret = self.run_state(
            'user.present', name='salt_test', fullname=12345, roomnumber=123,
            workphone=1234567890, homephone=1234567890
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.absent', name='salt_test')
        self.assertSaltTrueReturn(ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UserTest)
