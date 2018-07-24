# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import string
import random

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root
from tests.support.unit import skipIf

# Import 3rd-party libs
from salt.ext.six.moves import range
import salt.utils


@skip_if_not_root
@destructiveTest
class GroupModuleTest(ModuleCase):
    '''
    Validate the linux group system module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        super(GroupModuleTest, self).setUp()
        self._user = self.__random_string()
        self._user1 = self.__random_string()
        self._no_user = self.__random_string()
        self._group = self.__random_string()
        self._no_group = self.__random_string()
        self.os_grain = self.run_function('grains.item', ['kernel'])
        self._gid = 64989 if 'Windows' not in self.os_grain['kernel'] else None
        self._new_gid = 64998 if 'Windows' not in self.os_grain['kernel'] else None
        if self.os_grain['kernel'] not in ('Linux', 'Windows'):
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **self.os_grain
                )
            )

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

    def test_add(self):
        '''
        Test the add group function
        '''
        # add a new group
        self.assertTrue(self.run_function('group.add', [self._group], gid=self._gid))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['gid'], self._gid)
        self.assertEqual(group_info['name'], self._group)
        # try adding the group again
        if self.os_grain['kernel'] == 'Windows':
            add_group = self.run_function('group.add', [self._group], gid=self._gid)
            self.assertEqual(add_group['result'], None)
            self.assertEqual(add_group['comment'], 'The group {0} already exists.'.format(self._group))
            self.assertEqual(add_group['changes'], [])
        else:
            self.assertFalse(self.run_function('group.add', [self._group], gid=self._gid))

    def test_delete(self):
        '''
        Test the delete group function
        '''
        self.assertTrue(self.run_function('group.add', [self._group]))

        # correct functionality
        self.assertTrue(self.run_function('group.delete', [self._group]))

        # group does not exist
        if self.os_grain['kernel'] == 'Windows':
            del_group = self.run_function('group.delete', [self._no_group])
            self.assertEqual(del_group['changes'], [])
            self.assertEqual(del_group['comment'], 'The group {0} does not exists.'.format(self._no_group))
        else:
            self.assertFalse(self.run_function('group.delete', [self._no_group]))

    def test_info(self):
        '''
        Test the info group function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        group_info = self.run_function('group.info', [self._group])

        self.assertEqual(group_info['name'], self._group)
        self.assertEqual(group_info['gid'], self._gid)
        self.assertIn(self._user, str(group_info['members']))

    @skipIf(salt.utils.is_windows(), 'gid test skipped on windows')
    def test_chgid(self):
        '''
        Test the change gid function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.assertTrue(self.run_function('group.chgid', [self._group, self._new_gid]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['gid'], self._new_gid)

    def test_adduser(self):
        '''
        Test the add user to group function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.run_function('user.add', [self._user])
        self.assertTrue(self.run_function('group.adduser', [self._group, self._user]))
        group_info = self.run_function('group.info', [self._group])
        self.assertIn(self._user, str(group_info['members']))
        if self.os_grain['kernel'] == 'Windows':
            no_group = self.run_function('group.adduser', [self._no_group, self._no_user])
            no_user = self.run_function('group.adduser', [self._group, self._no_user])
            funcs = [no_group, no_user]
            for func in funcs:
                self.assertIn('Fail', func['comment'])
                self.assertFalse(func['result'])
        else:
            # try add a non existing user
            self.assertFalse(self.run_function('group.adduser', [self._group, self._no_user]))
            # try add a user to non existing group
            self.assertFalse(self.run_function('group.adduser', [self._no_group, self._user]))
            # try add a non existing user to a non existing group
            self.assertFalse(self.run_function('group.adduser', [self._no_group, self._no_user]))

    def test_deluser(self):
        '''
        Test the delete user from group function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        self.assertTrue(self.run_function('group.deluser', [self._group, self._user]))
        group_info = self.run_function('group.info', [self._group])
        self.assertNotIn(self._user, str(group_info['members']))

    def test_members(self):
        '''
        Test the members function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.run_function('user.add', [self._user])
        self.run_function('user.add', [self._user1])
        m = '{0},{1}'.format(self._user, self._user1)
        self.assertTrue(self.run_function('group.members', [self._group, m]))
        group_info = self.run_function('group.info', [self._group])
        self.assertIn(self._user, str(group_info['members']))
        self.assertIn(self._user1, str(group_info['members']))

    def test_getent(self):
        '''
        Test the getent function
        '''
        self.run_function('group.add', [self._group], gid=self._gid)
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        ginfo = self.run_function('user.getent')
        self.assertIn(self._group, str(ginfo))
        self.assertIn(self._user, str(ginfo))
        self.assertNotIn(self._no_group, str(ginfo))
        self.assertNotIn(self._no_user, str(ginfo))
