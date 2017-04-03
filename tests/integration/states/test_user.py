# -*- coding: utf-8 -*-

'''
tests for user state
user absent
user present
user present with custom homedir
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
from random import randint
import grp

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest, requires_system_grains
from tests.support.mixins import SaltReturnAssertsMixin

# Import salt libs
import salt.utils

if salt.utils.is_darwin():
    USER = 'macuser'
    GROUP = 'macuser'
    GID = randint(400, 500)
    NOGROUPGID = randint(400, 500)
else:
    USER = 'nobody'
    GROUP = 'nobody'
    GID = 'nobody'
    NOGROUPGID = 'nogroup'


@destructiveTest
@skipIf(os.geteuid() != 0, 'you must be root to run this test')
class UserTest(ModuleCase, SaltReturnAssertsMixin):
    '''
    test for user absent
    '''
    user_name = 'salt_test'
    user_home = '/var/lib/salt_test'

    def setUp(self):
        if salt.utils.is_darwin():
            #on mac we need to add user, because there is
            #no creationtime for nobody user.
            add_user = self.run_function('user.add', [USER], gid=GID)

    def test_user_absent(self):
        ret = self.run_state('user.absent', name='unpossible')
        self.assertSaltTrueReturn(ret)

    def test_user_if_present(self):
        ret = self.run_state('user.present', name=USER)
        self.assertSaltTrueReturn(ret)

    def test_user_if_present_with_gid(self):
        if self.run_function('group.info', [USER]):
            ret = self.run_state('user.present', name=USER, gid=GID)
        elif self.run_function('group.info', ['nogroup']):
            ret = self.run_state('user.present', name=USER, gid=NOGROUPGID)
        else:
            self.skipTest(
                'Neither \'nobody\' nor \'nogroup\' are valid groups'
            )
        self.assertSaltTrueReturn(ret)

    def test_user_not_present(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        '''
        ret = self.run_state('user.present', name=self.user_name)
        self.assertSaltTrueReturn(ret)

    def test_user_present_when_home_dir_does_not_18843(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the minion.
        And then destroys that user.
        Assume that it will break any system you run it on.
        '''
        if salt.utils.is_darwin():
            HOMEDIR = '/Users/home_of_' + self.user_name
        else:
            HOMEDIR = '/home/home_of_' + self.user_name
        ret = self.run_state('user.present', name=self.user_name,
                             home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

        self.run_function('file.absent', name=HOMEDIR)
        ret = self.run_state('user.present', name=self.user_name,
                             home=HOMEDIR)
        self.assertSaltTrueReturn(ret)

    def test_user_present_nondefault(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        '''
        ret = self.run_state('user.present', name=self.user_name,
                             home=self.user_home)
        self.assertSaltTrueReturn(ret)
        self.assertTrue(os.path.isdir(self.user_home))

    @requires_system_grains
    def test_user_present_gid_from_name_default(self, grains=None):
        '''
        This is a DESTRUCTIVE TEST. It creates a new user on the on the minion.
        This is an integration test. Not all systems will automatically create
        a group of the same name as the user, but I don't have access to any.
        If you run the test and it fails, please fix the code it's testing to
        work on your operating system.
        '''
        # MacOS users' primary group defaults to staff (20), not the name of
        # user
        gid_from_name = False if grains['os_family'] == 'MacOS' else True

        ret = self.run_state('user.present', name=self.user_name,
                             gid_from_name=gid_from_name, home=self.user_home)
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir(self.user_home))
        if grains['os_family'] in ('Suse',):
            self.assertEqual(group_name, 'users')
        elif grains['os_family'] == 'MacOS':
            self.assertEqual(group_name, 'staff')
        else:
            self.assertEqual(group_name, self.user_name)

    def test_user_present_gid_from_name(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.
        This is a unit test, NOT an integration test. We create a group of the
        same name as the user beforehand, so it should all run smoothly.
        '''
        ret = self.run_state('group.present', name=self.user_name)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('user.present', name=self.user_name,
                             gid_from_name=True, home=self.user_home)
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        group_name = grp.getgrgid(ret['gid']).gr_name

        self.assertTrue(os.path.isdir(self.user_home))
        self.assertEqual(group_name, self.user_name)
        ret = self.run_state('user.absent', name=self.user_name)
        self.assertSaltTrueReturn(ret)
        ret = self.run_state('group.absent', name=self.user_name)
        self.assertSaltTrueReturn(ret)

    @skipIf(sys.getfilesystemencoding().startswith('ANSI'), 'A system encoding which supports Unicode characters must be set. Current setting is: {0}. Try setting $LANG=\'en_US.UTF-8\''.format(sys.getfilesystemencoding()))
    def test_user_present_unicode(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that unicode GECOS data will be properly handled, without
        any encoding-related failures.
        '''
        ret = self.run_state(
            'user.present',
            name=self.user_name,
            fullname=u'Sålt Test',
            roomnumber=u'①②③',
            workphone=u'١٢٣٤',
            homephone=u'६७८'
        )
        self.assertSaltTrueReturn(ret)
        # Ensure updating a user also works
        ret = self.run_state(
            'user.present',
            name=self.user_name,
            fullname=u'Sølt Test',
            roomnumber=u'①③②',
            workphone=u'٣٤١٢',
            homephone=u'६८७'
        )
        self.assertSaltTrueReturn(ret)

    def test_user_present_gecos(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that numeric GECOS data will be properly coerced to strings,
        otherwise the state will fail because the GECOS fields are written as
        strings (and show up in the user.info output as such). Thus the
        comparison will fail, since '12345' != 12345.
        '''
        ret = self.run_state(
            'user.present',
            name=self.user_name,
            fullname=12345,
            roomnumber=123,
            workphone=1234567890,
            homephone=1234567890
        )
        self.assertSaltTrueReturn(ret)

    def test_user_present_gecos_none_fields(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new user on the on the minion.

        It ensures that if no GECOS data is supplied, the fields will be coerced
        into empty strings as opposed to the string "None".
        '''
        ret = self.run_state(
            'user.present',
            name=self.user_name,
            fullname=None,
            roomnumber=None,
            workphone=None,
            homephone=None
        )
        self.assertSaltTrueReturn(ret)

        ret = self.run_function('user.info', [self.user_name])
        self.assertReturnNonEmptySaltType(ret)
        self.assertEqual('', ret['fullname'])
        # MacOS does not supply the following GECOS fields
        if not salt.utils.is_darwin():
            self.assertEqual('', ret['roomnumber'])
            self.assertEqual('', ret['workphone'])
            self.assertEqual('', ret['homephone'])

    def tearDown(self):
        if salt.utils.is_darwin():
            check_user = self.run_function('user.list_users')
            if USER in check_user:
                del_user = self.run_function('user.delete', [USER], remove=True)
        self.assertSaltTrueReturn(
            self.run_state('user.absent', name=self.user_name)
        )
