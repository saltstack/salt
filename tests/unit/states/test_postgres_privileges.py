# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Andrew Colin Kissa <andrew@topdog.za.net>`
'''
from __future__ import absolute_import, unicode_literals, print_function

from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

import salt.states.postgres_privileges as postgres_privileges


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresPrivilegesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.postgres_privileges
    '''

    def setup_loader_modules(self):
        return {postgres_privileges: {}}

    def setUp(self):
        '''
        Setup data for the tests
        '''
        self.table_name = 'awl'
        self.group_name = 'admins'
        self.name = 'baruwa'
        self.ret = {'name': self.name,
                    'changes': {},
                    'result': False,
                    'comment': ''}
        self.mock_true = MagicMock(return_value=True)
        self.mock_false = MagicMock(return_value=False)

    def tearDown(self):
        del self.ret
        del self.mock_true
        del self.mock_false

    def test_present_table(self):
        '''
        Test present
        '''
        with patch.dict(postgres_privileges.__salt__,
                {'postgres.has_privileges': self.mock_true}):
            comt = 'The requested privilege(s) are already set'
            self.ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(
                postgres_privileges.present(
                    self.name,
                    self.table_name,
                    'table'),
                self.ret)

        with patch.dict(postgres_privileges.__salt__,
            {'postgres.has_privileges': self.mock_false,
                'postgres.privileges_grant': self.mock_true}):
            with patch.dict(postgres_privileges.__opts__, {'test': True}):
                comt = ('The privilege(s): {0} are'
                        ' set to be granted to {1}').format('ALL', self.name)
                self.ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(
                    postgres_privileges.present(self.name,
                        self.table_name, 'table', privileges=['ALL']), self.ret)

            with patch.dict(postgres_privileges.__opts__, {'test': False}):
                comt = ('The privilege(s): {0} have '
                        'been granted to {1}').format('ALL', self.name)
                self.ret.update({'comment': comt,
                            'result': True,
                            'changes': {'baruwa': 'Present'}})
                self.assertDictEqual(
                    postgres_privileges.present(self.name,
                        self.table_name, 'table', privileges=['ALL']), self.ret)

    def test_present_group(self):
        '''
        Test present group
        '''
        with patch.dict(postgres_privileges.__salt__,
            {'postgres.has_privileges': self.mock_false,
                'postgres.privileges_grant': self.mock_true}):
            with patch.dict(postgres_privileges.__opts__, {'test': True}):
                comt = ('The privilege(s): {0} are'
                        ' set to be granted to {1}').format(self.group_name,
                            self.name)
                self.ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(
                    postgres_privileges.present(self.name,
                        self.group_name, 'group'), self.ret)

            with patch.dict(postgres_privileges.__opts__, {'test': False}):
                comt = ('The privilege(s): {0} have '
                        'been granted to {1}').format(self.group_name,
                            self.name)
                self.ret.update({'comment': comt,
                            'result': True,
                            'changes': {'baruwa': 'Present'}})
                self.assertDictEqual(
                    postgres_privileges.present(self.name,
                        self.group_name, 'group'), self.ret)

    def test_absent_table(self):
        '''
        Test absent
        '''
        with patch.dict(postgres_privileges.__salt__,
                {'postgres.has_privileges': self.mock_false}):
            with patch.dict(postgres_privileges.__opts__, {'test': True}):
                comt = ('The requested privilege(s)'
                    ' are not set so cannot be revoked')
                self.ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(
                    postgres_privileges.absent(
                        self.name,
                        self.table_name,
                        'table'),
                    self.ret)

        with patch.dict(postgres_privileges.__salt__,
            {'postgres.has_privileges': self.mock_true,
                'postgres.privileges_revoke': self.mock_true}):
            with patch.dict(postgres_privileges.__opts__, {'test': True}):
                comt = ('The privilege(s): {0} are'
                        ' set to be revoked from {1}').format('ALL', self.name)
                self.ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(
                    postgres_privileges.absent(self.name,
                        self.table_name, 'table', privileges=['ALL']), self.ret)

            with patch.dict(postgres_privileges.__opts__, {'test': False}):
                comt = ('The privilege(s): {0} have '
                        'been revoked from {1}').format('ALL', self.name)
                self.ret.update({'comment': comt,
                            'result': True,
                            'changes': {'baruwa': 'Absent'}})
                self.assertDictEqual(
                    postgres_privileges.absent(self.name,
                        self.table_name, 'table', privileges=['ALL']), self.ret)

    def test_absent_group(self):
        '''
        Test absent group
        '''
        with patch.dict(postgres_privileges.__salt__,
            {'postgres.has_privileges': self.mock_true,
                'postgres.privileges_revoke': self.mock_true}):
            with patch.dict(postgres_privileges.__opts__, {'test': True}):
                comt = ('The privilege(s): {0} are'
                        ' set to be revoked from {1}').format(self.group_name,
                            self.name)
                self.ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(
                    postgres_privileges.absent(self.name,
                        self.group_name, 'group'), self.ret)

            with patch.dict(postgres_privileges.__opts__, {'test': False}):
                comt = ('The privilege(s): {0} have '
                        'been revoked from {1}').format(self.group_name,
                            self.name)
                self.ret.update({'comment': comt,
                            'result': True,
                            'changes': {'baruwa': 'Absent'}})
                self.assertDictEqual(
                    postgres_privileges.absent(self.name,
                        self.group_name, 'group'), self.ret)
