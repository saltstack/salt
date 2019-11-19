# -*- coding: utf-8 -*-
'''
Tests for salt.utils.group
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.utils.group


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GroupTestCase(TestCase):
    def setUp(self):
        self.init_group = {'id': os.getegid()}
        self.group1 = {'name': 'group1', 'id': 1331}
        self.group2 = {'name': 'group2', 'id': 1332}
        self.user1 = {'name': 'user1', 'id': 1221}
        self.user2 = {'name': 'user2', 'id': 1222}

        # Configure the system.
        os.system('groupadd -g {} {}'.format(self.group1['id'], self.group1['name']))
        os.system('groupadd -g {} {}'.format(self.group2['id'], self.group2['name']))
        os.system('useradd -g {} -G {} -u {} {}'.format(self.group1['id'], self.group1['name'], self.user1['id'], self.user1['name']))
        os.system('useradd -g {} -G {} -u {} {}'.format(self.group1['id'], self.group1['name'], self.user2['id'], self.user2['name']))

        # Set the current Execution group to the test group.
        os.setegid(self.group1['id'])

    def tearDown(self):
        # Set the current Execution group to the initial group.
        os.setegid(self.init_group['id'])

        # Remove users and groups used to test
        os.system('userdel -fr {}'.format(self.user2['name']))
        os.system('userdel -fr {}'.format(self.user1['name']))
        os.system('groupdel {}'.format(self.group1['name']))
        os.system('groupdel {}'.format(self.group2['name']))

        del self.group1
        del self.group2
        del self.user1
        del self.user2
        del self.init_group

    # METHOD : gid_to_group
    def test_gid_to_group_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual(self.group1['id'], salt.utils.group.gid_to_group(self.group1['id']))
        salt.utils.group.HAS_GRP = True

    def test_gid_to_group(self):
        self.assertEqual(self.group1['name'], salt.utils.group.gid_to_group(self.group1['id']))

    def test_gid_to_group_with_group(self):
        self.assertEqual(self.group1['name'], salt.utils.group.gid_to_group(self.group1['name']))

    # METHOD : group_to_gid
    def test_group_to_gid_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual(self.group1['name'], salt.utils.group.group_to_gid(self.group1['name']))
        salt.utils.group.HAS_GRP = True

    def test_group_to_gid(self):
        self.assertEqual(self.group1['id'], salt.utils.group.group_to_gid(self.group1['name']))

    def test_group_to_gid_with_gid(self):
        self.assertEqual(self.group1['id'], salt.utils.group.group_to_gid(self.group1['id']))

    # METHOD : get_group
    def test_get_group_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual(None, salt.utils.group.get_group())
        salt.utils.group.HAS_GRP = True

    def test_get_group(self):
        self.assertEqual(self.group1['name'], salt.utils.group.get_group())

    def test_get_group_with_gid(self):
        self.assertEqual(self.group2['name'], salt.utils.group.get_group(self.group2['id']))

    # METHOD : get_gid
    def test_get_gid_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual(None, salt.utils.group.get_gid())
        salt.utils.group.HAS_GRP = True

    def test_get_gid(self):
        self.assertEqual(self.group1['id'], salt.utils.group.get_gid())

    def test_get_gid_with_group(self):
        self.assertEqual(self.group2['id'], salt.utils.group.get_gid(self.group2['name']))

    # METHOD : get_all_group_name
    def test_get_all_group_name_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual([], salt.utils.group.get_all_group_name())
        salt.utils.group.HAS_GRP = True

    def test_get_all_group_name(self):
        self.assertIn(self.group1['name'], salt.utils.group.get_all_group_name())
        self.assertIn(self.group2['name'], salt.utils.group.get_all_group_name())

    # METHOD : get_user_list
    def test_get_user_list_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual([], salt.utils.group.get_user_list(self.group1['name']))
        salt.utils.group.HAS_GRP = True

    def test_get_user_list_with_group(self):
        self.assertEqual([self.user1['name'], self.user2['name']], salt.utils.group.get_user_list(self.group1['name']))

    def test_get_user_list_with_gid(self):
        self.assertEqual([self.user1['name'], self.user2['name']], salt.utils.group.get_user_list(self.group1['id']))

    # METHOD : get_uid_list
    def test_get_uid_list_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual([], salt.utils.group.get_uid_list(self.group1['name']))
        salt.utils.group.HAS_GRP = True

    def test_get_uid_list_with_group(self):
        self.assertEqual([self.user1['id'], self.user2['id']], salt.utils.group.get_uid_list(self.group1['name']))

    def test_get_uid_list_with_gid(self):
        self.assertEqual([self.user1['id'], self.user2['id']], salt.utils.group.get_uid_list(self.group1['id']))

    # METHOD : get_user_dict
    def test_get_user_dict_HAS_GRP_False(self):
        salt.utils.group.HAS_GRP = False
        self.assertEqual({}, salt.utils.group.get_user_dict(self.group1['name']))
        salt.utils.group.HAS_GRP = True

    def test_get_user_dict_with_group(self):
        self.assertEqual({self.user1['name']: self.user1['id'], self.user2['name']: self.user2['id']},
                         salt.utils.group.get_user_dict(self.group1['name']))

    def test_get_user_dict_with_gid(self):
        self.assertEqual({self.user1['name']: self.user1['id'], self.user2['name']: self.user2['id']},
                         salt.utils.group.get_user_dict(self.group1['id']))
