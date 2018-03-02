# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)


# Import Salt Libs
import salt.states.linux_acl as linux_acl
from salt.exceptions import CommandExecutionError


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not sys.platform.startswith('linux'), 'Test for Linux only')
class LinuxAclTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.linux_acl
    '''
    def setup_loader_modules(self):
        return {linux_acl: {}}

    # 'present' function tests: 1

    def test_present(self):
        '''
        Test to ensure a Linux ACL is present
        '''
        self.maxDiff = None
        name = '/root'
        acl_type = 'users'
        acl_name = 'damian'
        perms = 'rwx'

        mock = MagicMock(side_effect=[{name: {acl_type: [{acl_name:
                                                         {'octal': 'A'}}]}},
                                      {name: {acl_type: [{acl_name:
                                                         {'octal': 'A'}}]}},
                                      {name: {acl_type: [{acl_name:
                                                         {'octal': 'A'}}]}},
                                      {name: {acl_type: [{}]}},
                                      {name: {acl_type: [{}]}},
                                      {name: {acl_type: [{}]}},
                                      {name: {acl_type: ''}}])
        mock_modfacl = MagicMock(return_value=True)

        with patch.dict(linux_acl.__salt__, {'acl.getfacl': mock}):
            # Update - test=True
            with patch.dict(linux_acl.__opts__, {'test': True}):
                comt = ('Updated permissions will be applied for {0}: A -> {1}'
                        ''.format(acl_name, perms))
                ret = {'name': name,
                       'comment': comt,
                       'changes': {},
                       'pchanges': {'new': {'acl_name': acl_name,
                                            'acl_type': acl_type,
                                            'perms': perms},
                                    'old': {'acl_name': acl_name,
                                            'acl_type': acl_type,
                                            'perms': 'A'}},
                       'result': None}

                self.assertDictEqual(linux_acl.present(name, acl_type, acl_name,
                                                       perms), ret)
            # Update - test=False
            with patch.dict(linux_acl.__salt__, {'acl.modfacl': mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {'test': False}):
                    comt = ('Updated permissions for {0}'.format(acl_name))
                    ret = {'name': name,
                           'comment': comt,
                           'changes': {'new': {'acl_name': acl_name,
                                               'acl_type': acl_type,
                                               'perms': perms},
                                       'old': {'acl_name': acl_name,
                                               'acl_type': acl_type,
                                               'perms': 'A'}},
                           'pchanges': {},
                           'result': True}
                    self.assertDictEqual(linux_acl.present(name, acl_type,
                                                           acl_name, perms),
                                         ret)
            # Update - modfacl error
            with patch.dict(linux_acl.__salt__, {'acl.modfacl': MagicMock(
                    side_effect=CommandExecutionError('Custom err'))}):
                with patch.dict(linux_acl.__opts__, {'test': False}):
                    comt = ('Error updating permissions for {0}: Custom err'
                            ''.format(acl_name))
                    ret = {'name': name,
                           'comment': comt,
                           'changes': {},
                           'pchanges': {},
                           'result': False}
                    self.assertDictEqual(linux_acl.present(name, acl_type,
                                                           acl_name, perms),
                                         ret)
            # New - test=True
            with patch.dict(linux_acl.__salt__, {'acl.modfacl': mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {'test': True}):
                    comt = ('New permissions will be applied '
                            'for {0}: {1}'.format(acl_name, perms))
                    ret = {'name': name,
                           'comment': comt,
                           'changes': {},
                           'pchanges': {'new': {'acl_name': acl_name,
                                                'acl_type': acl_type,
                                                'perms': perms}},
                           'result': None}
                    self.assertDictEqual(linux_acl.present(name, acl_type,
                                                           acl_name, perms),
                                         ret)
            # New - test=False
            with patch.dict(linux_acl.__salt__, {'acl.modfacl': mock_modfacl}):
                with patch.dict(linux_acl.__opts__, {'test': False}):
                    comt = ('Applied new permissions for {0}'.format(acl_name))
                    ret = {'name': name,
                           'comment': comt,
                           'changes': {'new': {'acl_name': acl_name,
                                               'acl_type': acl_type,
                                               'perms': perms}},
                           'pchanges': {},
                           'result': True}
                    self.assertDictEqual(linux_acl.present(name, acl_type,
                                                           acl_name, perms),
                                         ret)
            # New - modfacl error
            with patch.dict(linux_acl.__salt__, {'acl.modfacl': MagicMock(
                    side_effect=CommandExecutionError('Custom err'))}):
                with patch.dict(linux_acl.__opts__, {'test': False}):
                    comt = ('Error updating permissions for {0}: Custom err'
                            ''.format(acl_name))
                    ret = {'name': name,
                           'comment': comt,
                           'changes': {},
                           'pchanges': {},
                           'result': False}
                    self.assertDictEqual(linux_acl.present(name, acl_type,
                                                           acl_name, perms),
                                         ret)
            # No acl type
            comt = ('ACL Type does not exist')
            ret = {'name': name, 'comment': comt, 'result': False,
                   'changes': {}, 'pchanges': {}}
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

        mock = MagicMock(side_effect=[{name: {acl_type: [{acl_name: {'octal': 'A'}}]}},
                                      {name: {acl_type: ''}}])
        with patch.dict(linux_acl.__salt__, {'acl.getfacl': mock}):
            with patch.dict(linux_acl.__opts__, {'test': True}):
                comt = ('Removing permissions')
                ret.update({'comment': comt})
                self.assertDictEqual(linux_acl.absent(name, acl_type, acl_name, perms), ret)

            comt = ('ACL Type does not exist')
            ret.update({'comment': comt, 'result': False})
            self.assertDictEqual(linux_acl.absent(name, acl_type, acl_name, perms), ret)
