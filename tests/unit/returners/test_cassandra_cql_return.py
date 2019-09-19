# -*- coding: utf-8 -*-
'''
Cassandra cql returner test cases
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON
from tests.support.mixins import LoaderModuleMockMixin


# Import salt libs
import salt.returners.cassandra_cql_return as cassandra_cql


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CassandraCqlReturnerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test Cassandra Cql Returner
    '''
    def setup_loader_modules(self):
        return {cassandra_cql: {}}

    def test_get_keyspace(self):
        '''
        Test edge cases of _get_keyspace
        '''
        # Empty __opts__
        with patch.dict(cassandra_cql.__opts__, {}):
            self.assertEqual(cassandra_cql._get_keyspace(), 'salt')

        # Cassandra option without keyspace
        with patch.dict(cassandra_cql.__opts__, {'cassandra': None}):
            self.assertEqual(cassandra_cql._get_keyspace(), 'salt')
        with patch.dict(cassandra_cql.__opts__, {'cassandra': {}}):
            self.assertEqual(cassandra_cql._get_keyspace(), 'salt')

        # Cassandra option with keyspace
        with patch.dict(cassandra_cql.__opts__, {'cassandra': {'keyspace': 'abcd'}}):
            self.assertEqual(cassandra_cql._get_keyspace(), 'abcd')
