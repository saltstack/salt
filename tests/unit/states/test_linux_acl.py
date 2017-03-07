# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import sys

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import linux_acl

linux_acl.__salt__ = {}
linux_acl.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not sys.platform.startswith('linux'), 'Test for Linux only')
class LinuxAclTestCase(TestCase):
    '''
    Test cases for salt.states.linux_acl
    '''
    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure a Linux ACL is present
        '''
        name = '/root'
        acl_type = 'users'
        acl_name = 'damian'
        perms = 'rwx'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[{name: {acl_type: [{acl_name:
                                                          {'octal': 'A'}}]}},
                                      {name: {acl_type: [{}]}},
                                      {name: {acl_type: ''}}])
        with patch.dict(linux_acl.__salt__, {'acl.getfacl': mock}):
            with patch.dict(linux_acl.__opts__, {'test': True}):
                comt = ('Permissions have been updated')
                ret.update({'comment': comt})
                self.assertDictEqual(linux_acl.present(name, acl_type, acl_name,
                                                       perms), ret)

                comt = ('Permissions will be applied')
                ret.update({'comment': comt})
                self.assertDictEqual(linux_acl.present(name, acl_type, acl_name,
                                                       perms), ret)

            comt = ('ACL Type does not exist')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(linux_acl.present(name, acl_type, acl_name,
                                                   perms), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        '''
        Test to ensure a Linux ACL does not exist
        '''
        name = '/root'
        acl_type = 'users'
        acl_name = 'damian'
        perms = 'rwx'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[{name: {acl_type: [{acl_name:
                                                          {'octal': 'A'}}]}},
                                      {name: {acl_type: ''}}])
        with patch.dict(linux_acl.__salt__, {'acl.getfacl': mock}):
            with patch.dict(linux_acl.__opts__, {'test': True}):
                comt = ('Removing permissions')
                ret.update({'comment': comt})
                self.assertDictEqual(linux_acl.absent(name, acl_type, acl_name,
                                                      perms), ret)

            comt = ('ACL Type does not exist')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(linux_acl.absent(name, acl_type, acl_name,
                                                  perms), ret)
