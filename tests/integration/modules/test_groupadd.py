# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import grp
import random
import string

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root

# Import Salt libs
from salt.ext import six
from salt.ext.six.moves import range
import salt.utils.files
import salt.utils.stringutils


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
        self._gid = 64989
        self._new_gid = 64998
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Linux':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
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

    def __get_system_group_gid_range(self):
        '''
        Returns (SYS_GID_MIN, SYS_GID_MAX)
        '''
        try:
            login_defs = {}
            with salt.utils.files.fopen('/etc/login.defs') as defs_fd:
                for line in defs_fd:
                    line = salt.utils.stringutils.to_unicode(line).strip()
                    if line.startswith('#'):
                        continue
                    try:
                        key, val = line.split()
                    except ValueError:
                        pass
                    else:
                        login_defs[key] = val
        except OSError:
            login_defs = {'SYS_GID_MIN': 101,
                          'SYS_GID_MAX': 999}

        gid_min = login_defs.get('SYS_GID_MIN', 101)
        gid_max = login_defs.get('SYS_GID_MAX',
                                 int(login_defs.get('GID_MIN', 1000)) - 1)

        return int(gid_min), int(gid_max)

    def __get_free_system_gid(self):
        '''
        Find a free system gid
        '''

        gid_min, gid_max = self.__get_system_group_gid_range()

        busy_gids = [x.gr_gid
                     for x in grp.getgrall()
                     if gid_min <= x.gr_gid <= gid_max]

        # find free system gid
        for gid in range(gid_min, gid_max + 1):
            if gid not in busy_gids:
                return gid

    @destructiveTest
    def test_add(self):
        '''
        Test the add group function
        '''
        # add a new group
        self.assertTrue(self.run_function('group.add', [self._group, self._gid]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['name'], self._group)
        self.assertEqual(group_info['gid'], self._gid)
        # try adding the group again
        self.assertFalse(self.run_function('group.add', [self._group, self._gid]))

    @destructiveTest
    def test_add_system_group(self):
        '''
        Test the add group function with system=True
        '''

        gid_min, gid_max = self.__get_system_group_gid_range()

        # add a new system group
        self.assertTrue(self.run_function('group.add',
                                          [self._group, None, True]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['name'], self._group)
        self.assertTrue(gid_min <= group_info['gid'] <= gid_max)
        # try adding the group again
        self.assertFalse(self.run_function('group.add',
                                           [self._group]))

    @destructiveTest
    def test_add_system_group_gid(self):
        '''
        Test the add group function with system=True and a specific gid
        '''

        gid = self.__get_free_system_gid()

        # add a new system group
        self.assertTrue(self.run_function('group.add',
                                          [self._group, gid, True]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['name'], self._group)
        self.assertEqual(group_info['gid'], gid)
        # try adding the group again
        self.assertFalse(self.run_function('group.add',
                                           [self._group, gid]))

    @destructiveTest
    def test_delete(self):
        '''
        Test the delete group function
        '''
        self.assertTrue(self.run_function('group.add', [self._group]))

        # correct functionality
        self.assertTrue(self.run_function('group.delete', [self._group]))

        # group does not exist
        self.assertFalse(self.run_function('group.delete', [self._no_group]))

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

    def test_chgid(self):
        '''
        Test the change gid function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.assertTrue(self.run_function('group.chgid', [self._group, self._new_gid]))
        group_info = self.run_function('group.info', [self._group])
        self.assertEqual(group_info['gid'], self._new_gid)

    def test_adduser(self):
        '''
        Test the add user to group function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.assertTrue(self.run_function('group.adduser', [self._group, self._user]))
        group_info = self.run_function('group.info', [self._group])
        self.assertIn(self._user, group_info['members'])
        # try to add a non existing user
        self.assertFalse(self.run_function('group.adduser', [self._group, self._no_user]))
        # try to add a user to non existing group
        self.assertFalse(self.run_function('group.adduser', [self._no_group, self._user]))
        # try to add a non existing user to a non existing group
        self.assertFalse(self.run_function('group.adduser', [self._no_group, self._no_user]))

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

    def test_getent(self):
        '''
        Test the getent function
        '''
        self.run_function('group.add', [self._group, self._gid])
        self.run_function('user.add', [self._user])
        self.run_function('group.adduser', [self._group, self._user])
        ginfo = self.run_function('user.getent')
        self.assertIn(self._group, six.text_type(ginfo))
        self.assertIn(self._user, six.text_type(ginfo))
        self.assertNotIn(self._no_group, six.text_type(ginfo))
        self.assertNotIn(self._no_user, six.text_type(ginfo))
