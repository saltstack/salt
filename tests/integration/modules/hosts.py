'''
Test the hosts module
'''
# Import python libs
import os
import shutil

# Import Salt libs
import integration

HFN = os.path.join(integration.TMP, 'hosts')

class HostsModuleTest(integration.ModuleCase):
    '''
    Test the hosts module
    '''
    def __clean_hosts(self):
        '''
        Clean out the hosts file
        '''
        shutil.copyfile(os.path.join(integration.FILES, 'hosts'), HFN)

    def __clear_hosts(self):
        '''
        Delete the tmp hosts file
        '''
        if os.path.isfile(HFN):
            os.remove(HFN)

    def tearDown(self):
        '''
        Make sure the tmp hosts file is gone
        '''
        self.__clear_hosts()

    def test_list_hosts(self):
        '''
        hosts.list_hosts
        '''
        self.__clean_hosts()
        hosts = self.run_function('hosts.list_hosts')
        self.assertEqual(len(hosts), 6)
        self.assertEqual(hosts['::1'], ['ip6-localhost', 'ip6-loopback'])
        self.assertEqual(hosts['127.0.0.1'], ['localhost', 'myname'])

    def test_list_hosts_nofile(self):
        '''
        hosts.list_hosts
        without a hosts file
        '''
        if os.path.isfile(HFN):
            os.remove(HFN)
        hosts = self.run_function('hosts.list_hosts')
        self.assertEqual(hosts, {})

    def test_get_ip(self):
        '''
        hosts.get_ip
        '''
        self.__clean_hosts()
        self.assertEqual(self.run_function('hosts.get_ip', ['myname']), '127.0.0.1')
        self.assertEqual(self.run_function('hosts.get_ip', ['othername']), '')
        self.__clear_hosts()
        self.assertEqual(self.run_function('hosts.get_ip', ['othername']), '')

    def test_get_alias(self):
        '''
        hosts.get_alias
        '''
        self.__clean_hosts()
        self.assertEqual(self.run_function('hosts.get_alias', ['127.0.0.1']), ['localhost', 'myname'])
        self.assertEqual(self.run_function('hosts.get_alias', ['127.0.0.2']), [])
        self.__clear_hosts()
        self.assertEqual(self.run_function('hosts.get_alias', ['127.0.0.1']), [])

    def test_has_pair(self):
        '''
        hosts.has_pair
        '''
        self.__clean_hosts()
        self.assertTrue(self.run_function('hosts.has_pair', ['127.0.0.1', 'myname']))
        self.assertFalse(self.run_function('hosts.has_pair', ['127.0.0.1', 'othername']))

    def test_set_host(self):
        '''
        hosts.set_hosts
        '''
        self.__clean_hosts()
        assert self.run_function('hosts.set_host', ['192.168.1.123', 'newip'])
        self.assertTrue(self.run_function('hosts.has_pair', ['192.168.1.123', 'newip']))
        self.assertEqual(len(self.run_function('hosts.list_hosts')), 7)
        assert self.run_function('hosts.set_host', ['127.0.0.1', 'localhost'])
        self.assertFalse(self.run_function('hosts.has_pair', ['127.0.0.1', 'myname']), 'should remove second entry')

    def test_add_host(self):
        '''
        hosts.add_host
        '''
        self.__clean_hosts()
        assert self.run_function('hosts.add_host', ['192.168.1.123', 'newip'])
        self.assertTrue(self.run_function('hosts.has_pair', ['192.168.1.123', 'newip']))
        self.assertEqual(len(self.run_function('hosts.list_hosts')), 7)
        assert self.run_function('hosts.add_host', ['127.0.0.1', 'othernameip'])
        self.assertEqual(len(self.run_function('hosts.list_hosts')), 7)

    def test_rm_host(self):
        self.__clean_hosts()
        assert self.run_function('hosts.has_pair', ['127.0.0.1', 'myname'])
        assert self.run_function('hosts.rm_host', ['127.0.0.1', 'myname'])
        assert not self.run_function('hosts.has_pair', ['127.0.0.1', 'myname'])
        assert self.run_function('hosts.rm_host', ['127.0.0.1', 'unknown'])
