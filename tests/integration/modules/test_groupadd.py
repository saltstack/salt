# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import string
import random

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest

# Import salt libs
from salt.ext.six.moves import range
import salt.utils


class GroupModuleTest(ModuleCase):
    '''
    Validate the linux group system module
    '''

    def __init__(self, arg):
        super(self.__class__, self).__init__(arg)
        self._user = self.__random_string()
        self._user1 = self.__random_string()
        self._no_user = self.__random_string()
        self._group = self.__random_string()
        self._no_group = self.__random_string()
        self._gid = 64989
        self._new_gid = 64998

    def setUp(self):
        '''
        Get current settings
        '''
        super(GroupModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Linux':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )
        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Tests requires root')

    @destructiveTest
    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('user.delete', [self._user])
        self.run_function('user.delete', [self._user1])
        self.run_function('group.delete', [self._group])

    def __random_string(self, size=6):
        '''
        Generates a random names
        '''
        return 'tg-' + ''.join(
            random.choice(string.ascii_lowercase + string.digits)
            for x in range(size)
        )

    @destructiveTest
    def test_add(self):
        '''
        Test the add group function
        '''
        #add a new group
        self.assertTrue(self.run_function('group.add', [self._group, self._gid]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['name'], self._group)
        self.assertEqual(group_info['gid'], self._gid)
        #try adding the group again
        self.assertFalse(self.run_function('group.add', [self._group, self._gid]))

    @destructiveTest
    def test_delete(self):
        '''
        Test the delete group function
        '''
        self.assertTrue(self.run_function('group.add', [self._group]))

        #correct functionality
        self.assertTrue(self.run_function('group.delete', [self._group]))

        #group does not exist
        self.assertFalse(self.run_function('group.delete', [self._no_group]))

    @destructiveTest
    def test_info(self):
        '''
        Test the info group function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        group_info = self.run_function('group.info', [self._group])

        self.assertEqual(group_info['name'], self._group)
        self.assertEqual(group_info['gid'], self._gid)
        self.assertIn(self._user, group_info['members'])

    @destructiveTest
    def test_chgid(self):
        '''
        Test the change gid function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.assertTrue(self.run_function('group.chgid', [self._group, self._new_gid]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['gid'], self._new_gid)

    @destructiveTest
    def test_adduser(self):
        '''
        Test the add user to group function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.assertTrue(self.run_function('group.adduser', [self._group, self._user]))
        group_info = self.run_function('group.info', [self._group])
        self.assertIn(self._user, group_info['members'])
        #try add a non existing user
        self.assertFalse(self.run_function('group.adduser', [self._group, self._no_user]))
        #try add a user to non existing group
        self.assertFalse(self.run_function('group.adduser', [self._no_group, self._user]))
        #try add a non existing user to a non existing group
        self.assertFalse(self.run_function('group.adduser', [self._no_group, self._no_user]))

    @destructiveTest
    def test_deluser(self):
        '''
        Test the delete user from group function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        self.assertTrue(self.run_function('group.deluser', [self._group, self._user]))
        group_info = self.run_function('group.info', [self._group])
        self.assertNotIn(self._user, group_info['members'])

    @destructiveTest
    def test_members(self):
        '''
        Test the members function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.run_function('user.add', [self._user1])
        m = '{0},{1}'.format(self._user, self._user1)
        self.assertTrue(self.run_function('group.members', [self._group, m]))
        group_info = self.run_function('group.info', [self._group])
        self.assertIn(self._user, group_info['members'])
        self.assertIn(self._user1, group_info['members'])

    @destructiveTest
    def test_getent(self):
        '''
        Test the getent function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        ginfo = self.run_function('user.getent')
        self.assertIn(self._group, str(ginfo))
        self.assertIn(self._user, str(ginfo))
        self.assertNotIn(self._no_group, str(ginfo))
        self.assertNotIn(self._no_user, str(ginfo))
