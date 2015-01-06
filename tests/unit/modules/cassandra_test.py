# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import cassandra
HAS_PYCASSA = False
try:
    from pycassa.system_manager import SystemManager
    HAS_PYCASSA = True
except ImportError:
    pass

# Globals
# from pycassa.system_manager.SystemManager import list_keyspaces
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
        mock = MagicMock(side_effect=['thrift_port', 'host'])
        with patch.dict(cassandra.__salt__, {'config.option': mock}):
            mock = MagicMock()
            with patch.object(cassandra, 'SystemManager', mock):
                mock = MagicMock(return_value=['A'])
                with patch.object(cassandra, 'list_keyspaces', mock):
                    self.assertEqual(cassandra.keyspaces(), '')

    def test_column_families(self):
        '''
        Test for Return existing column families for all keyspaces
        '''
        pass

    def test_column_family_definition(self):
        '''
        Test for Return a dictionary of column family definitions for the given
        keyspace/column_family
        '''
        pass


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CassandraTestCase, needs_daemon=False)
