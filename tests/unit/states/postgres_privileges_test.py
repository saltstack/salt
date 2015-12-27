# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Andrew Colin Kissa <andrew@topdog.za.net>`
'''
from __future__ import absolute_import

from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

from salt.states import postgres_privileges


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PostgresPrivilegesTestCase(TestCase):
    '''
    Test cases for salt.states.postgres_privileges
    '''

    def setUp(self):
        '''
        Setup data for the tests
        '''
        postgres_privileges.__opts__ = {}
        postgres_privileges.__salt__ = {}
        self.mock_true = MagicMock(return_value=True)
        self.mock_false = MagicMock(return_value=False)

    def test_present_existing(self):
        '''
        Test present, privilege(s) are already granted
        '''
        pass
