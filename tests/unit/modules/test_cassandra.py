# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.ext.six as six
from salt.modules import cassandra


cassandra.__grains__ = {}
cassandra.__salt__ = {}
cassandra.__context__ = {}
cassandra.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CassandraTestCase(TestCase):
    '''
    Test cases for salt.modules.cassandra
    '''
    def test_compactionstats(self):
        '''
        Test for Return compactionstats info
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.compactionstats(), 'A')

    def test_version(self):
        '''
        Test for Return the cassandra version
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.version(), 'A')

    def test_netstats(self):
        '''
        Test for Return netstats info
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.netstats(), 'A')

    def test_tpstats(self):
        '''
        Test for Return tpstats info
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.tpstats(), 'A')

    def test_info(self):
        '''
        Test for Return cassandra node info
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.info(), 'A')

    def test_ring(self):
        '''
        Test for Return ring info
        '''
        mock = MagicMock(return_value='A')
        with patch.object(cassandra, '_nodetool', mock):
            self.assertEqual(cassandra.ring(), 'A')

    def test_keyspaces(self):
        '''
        Test for Return existing keyspaces
        '''
        mock_keyspaces = ['A', 'B', 'C', 'D']

        class MockSystemManager(object):
            def list_keyspaces(self):
                return mock_keyspaces

        mock_sys_mgr = MagicMock(return_value=MockSystemManager())

        with patch.object(cassandra, '_sys_mgr', mock_sys_mgr):
            self.assertEqual(cassandra.keyspaces(), mock_keyspaces)

    def test_column_families(self):
        '''
        Test for Return existing column families for all keyspaces
        '''
        mock_keyspaces = ['A', 'B']

        class MockSystemManager(object):
            def list_keyspaces(self):
                return mock_keyspaces

            def get_keyspace_column_families(self, keyspace):
                if keyspace == 'A':
                    return {'a': 'saltines', 'b': 'biscuits'}
                if keyspace == 'B':
                    return {'c': 'cheese', 'd': 'crackers'}

        mock_sys_mgr = MagicMock(return_value=MockSystemManager())

        with patch.object(cassandra, '_sys_mgr', mock_sys_mgr):
            self.assertEqual(cassandra.column_families('Z'),
                             None)
            if six.PY3:
                self.assertCountEqual(cassandra.column_families('A'),
                                      ['a', 'b'])
                self.assertCountEqual(cassandra.column_families(),
                                      {'A': ['a', 'b'], 'B': ['c', 'd']})
            else:
                self.assertEqual(cassandra.column_families('A'),
                                 ['a', 'b'])
                self.assertEqual(cassandra.column_families(),
                                 {'A': ['a', 'b'], 'B': ['c', 'd']})

    def test_column_family_definition(self):
        '''
        Test for Return a dictionary of column family definitions for the given
        keyspace/column_family
        '''
        class MockSystemManager(object):
            def get_keyspace_column_families(self, keyspace):
                if keyspace == 'A':
                    return {'a': object, 'b': object}
                if keyspace == 'B':
                    raise Exception

        mock_sys_mgr = MagicMock(return_value=MockSystemManager())

        with patch.object(cassandra, '_sys_mgr', mock_sys_mgr):
            self.assertEqual(cassandra.column_family_definition('A', 'a'), vars(object))
            self.assertEqual(cassandra.column_family_definition('B', 'a'), None)
