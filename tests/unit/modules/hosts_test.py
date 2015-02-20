# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import (
    MagicMock,
    mock_open,
    patch,
)
# Import Salt Libs
from salt.modules import hosts


class HostsTestCase(TestCase):
    '''
    TestCase for salt.modules.hosts
    '''
    hosts.__grains__ = {}
    hosts.__salt__ = {}
    hosts.__context__ = {}

    # 'list_hosts' function tests: 1

    @patch('salt.modules.hosts._list_hosts',
           MagicMock(return_value={'10.10.10.10': ['Salt1', 'Salt2']}))
    def test_list_hosts(self):
        '''
        Tests return the hosts found in the hosts file
        '''
        self.assertDictEqual({'10.10.10.10': ['Salt1', 'Salt2']},
                             hosts.list_hosts())

    # 'get_ip' function tests: 3

    @patch('salt.modules.hosts._list_hosts',
           MagicMock(return_value={'10.10.10.10': ['Salt1', 'Salt2']}))
    def test_get_ip(self):
        '''
        Tests return ip associated with the named host
        '''
        self.assertEqual('10.10.10.10', hosts.get_ip('Salt1'))

        self.assertEqual('', hosts.get_ip('Salt3'))

    @patch('salt.modules.hosts._list_hosts', MagicMock(return_value=''))
    def test_get_ip_none(self):
        '''
        Tests return ip associated with the named host
        '''
        self.assertEqual('', hosts.get_ip('Salt1'))

    # 'get_alias' function tests: 2

    @patch('salt.modules.hosts._list_hosts',
           MagicMock(return_value={'10.10.10.10': ['Salt1', 'Salt2']}))
    def test_get_alias(self):
        '''
        Tests return the list of aliases associated with an ip
        '''
        self.assertListEqual(['Salt1', 'Salt2'], hosts.get_alias('10.10.10.10'))

    @patch('salt.modules.hosts._list_hosts',
           MagicMock(return_value={'10.10.10.10': ['Salt1', 'Salt2']}))
    def test_get_alias_none(self):
        '''
        Tests return the list of aliases associated with an ip
        '''
        self.assertListEqual([], hosts.get_alias('10.10.10.11'))

    # 'has_pair' function tests: 1

    @patch('salt.modules.hosts._list_hosts',
           MagicMock(return_value={'10.10.10.10': ['Salt1', 'Salt2']}))
    def test_has_pair(self):
        '''
        Tests return True / False if the alias is set
        '''
        self.assertTrue(hosts.has_pair('10.10.10.10', 'Salt1'))

        self.assertFalse(hosts.has_pair('10.10.10.10', 'Salt3'))

    # 'set_host' function tests: 2

    @patch('salt.modules.hosts.__get_hosts_filename',
           MagicMock(return_value='/etc/hosts'))
    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_set_host(self):
        '''
        Tests true if the alias is set
        '''
        mock_opt = MagicMock(return_value=None)
        with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
            self.assertFalse(hosts.set_host('10.10.10.10', 'Salt1'))

    @patch('salt.modules.hosts.__get_hosts_filename',
           MagicMock(return_value='/etc/hosts'))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_set_host_true(self):
        '''
        Tests true if the alias is set
        '''
        with patch('salt.utils.fopen', mock_open()):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
                self.assertTrue(hosts.set_host('10.10.10.10', 'Salt1'))

    # 'rm_host' function tests: 2

    @patch('salt.modules.hosts.__get_hosts_filename',
           MagicMock(return_value='/etc/hosts'))
    @patch('salt.modules.hosts.has_pair', MagicMock(return_value=True))
    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_rm_host(self):
        '''
        Tests if specified host entry gets removed from the hosts file
        '''
        with patch('salt.utils.fopen', mock_open()):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
                self.assertTrue(hosts.rm_host('10.10.10.10', 'Salt1'))

    @patch('salt.modules.hosts.has_pair', MagicMock(return_value=False))
    def test_rm_host_false(self):
        '''
        Tests if specified host entry gets removed from the hosts file
        '''
        self.assertTrue(hosts.rm_host('10.10.10.10', 'Salt1'))

    # 'add_host' function tests: 3

    @patch('salt.modules.hosts.__get_hosts_filename',
           MagicMock(return_value='/etc/hosts'))
    def test_add_host(self):
        '''
        Tests if specified host entry gets added from the hosts file
        '''
        with patch('salt.utils.fopen', mock_open()):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
                self.assertTrue(hosts.add_host('10.10.10.10', 'Salt1'))

    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_add_host_no_file(self):
        '''
        Tests if specified host entry gets added from the hosts file
        '''
        with patch('salt.utils.fopen', mock_open()):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
                self.assertFalse(hosts.add_host('10.10.10.10', 'Salt1'))

    @patch('os.path.isfile', MagicMock(return_value=True))
    def test_add_host_create_entry(self):
        '''
        Tests if specified host entry gets added from the hosts file
        '''
        with patch('salt.utils.fopen', mock_open()):
            mock_opt = MagicMock(return_value=None)
            with patch.dict(hosts.__salt__, {'config.option': mock_opt}):
                self.assertTrue(hosts.add_host('10.10.10.10', 'Salt1'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(HostsTestCase, needs_daemon=False)
