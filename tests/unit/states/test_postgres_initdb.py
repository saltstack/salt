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

import salt.states.postgres_initdb as postgres_initdb


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresInitdbTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.postgres_initdb
    '''

    def setup_loader_modules(self):
        return {postgres_initdb: {}}

    def setUp(self):
        '''
        Setup data for the tests
        '''
        self.name = '/var/lib/psql/data'
        self.ret = {
            'name': self.name,
            'changes': {},
            'result': False,
            'comment': ''}
        self.mock_true = MagicMock(return_value=True)
        self.mock_false = MagicMock(return_value=False)

    def tearDown(self):
        del self.ret
        del self.mock_true
        del self.mock_false

    def test_present_existing(self):
        '''
        Test existing data directory handled correctly
        '''
        with patch.dict(postgres_initdb.__salt__,
            {'postgres.datadir_exists': self.mock_true}):
            _comt = 'Postgres data directory {0} is already present'\
                .format(self.name)
            self.ret.update({'comment': _comt, 'result': True})
            self.assertDictEqual(postgres_initdb.present(self.name), self.ret)

    def test_present_non_existing_pass(self):
        '''
        Test non existing data directory ok
        '''
        with patch.dict(postgres_initdb.__salt__,
            {'postgres.datadir_exists': self.mock_false,
             'postgres.datadir_init': self.mock_true}):
            with patch.dict(postgres_initdb.__opts__, {'test': True}):
                _comt = 'Postgres data directory {0} is set to be initialized'\
                    .format(self.name)
                self.ret.update({'comment': _comt, 'result': None})
                self.assertDictEqual(
                    postgres_initdb.present(self.name), self.ret)

            with patch.dict(postgres_initdb.__opts__, {'test': False}):
                _comt = 'Postgres data directory {0} has been initialized'\
                    .format(self.name)
                _changes = {self.name: 'Present'}
                self.ret.update({
                        'comment': _comt,
                        'result': True,
                        'changes': _changes})
                self.assertDictEqual(
                    postgres_initdb.present(self.name), self.ret)

    def test_present_non_existing_fail(self):
        '''
        Test non existing data directory fail
        '''
        with patch.dict(postgres_initdb.__salt__,
            {'postgres.datadir_exists': self.mock_false,
             'postgres.datadir_init': self.mock_false}):
            with patch.dict(postgres_initdb.__opts__, {'test': False}):
                _comt = 'Postgres data directory {0} initialization failed'\
                    .format(self.name)
                self.ret.update({
                        'comment': _comt,
                        'result': False
                        })
                self.assertDictEqual(
                    postgres_initdb.present(self.name), self.ret)
