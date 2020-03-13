# -*- coding: utf-8 -*-
'''
Test the hosts module
'''
# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import logging

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils

import pytest

log = logging.getLogger(__name__)


@pytest.mark.windows_whitelisted
class HostsModuleTest(ModuleCase):
    '''
    Test the hosts module
    '''

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.hosts_file = os.path.join(RUNTIME_VARS.TMP, 'hosts')

    def __clear_hosts(self):
        '''
        Delete the tmp hosts file
        '''
        if os.path.isfile(self.hosts_file):
            os.remove(self.hosts_file)

    def setUp(self):
        shutil.copyfile(os.path.join(RUNTIME_VARS.FILES, 'hosts'), self.hosts_file)
        self.addCleanup(self.__clear_hosts)

    def test_list_hosts(self):
        '''
        hosts.list_hosts
        '''
        hosts = self.run_function('hosts.list_hosts')
        assert len(hosts) == 10
        assert hosts['::1'] == ['ip6-localhost', 'ip6-loopback']
        assert hosts['127.0.0.1'] == ['localhost', 'myname']

    def test_list_hosts_nofile(self):
        '''
        hosts.list_hosts
        without a hosts file
        '''
        if os.path.isfile(self.hosts_file):
            os.remove(self.hosts_file)
        hosts = self.run_function('hosts.list_hosts')
        assert hosts == {}

    def test_get_ip(self):
        '''
        hosts.get_ip
        '''
        assert self.run_function('hosts.get_ip', ['myname']) == '127.0.0.1'
        assert self.run_function('hosts.get_ip', ['othername']) == ''
        self.__clear_hosts()
        assert self.run_function('hosts.get_ip', ['othername']) == ''

    def test_get_alias(self):
        '''
        hosts.get_alias
        '''
        assert self.run_function('hosts.get_alias', ['127.0.0.1']) == \
            ['localhost', 'myname']
        assert self.run_function('hosts.get_alias', ['127.0.0.2']) == \
            []
        self.__clear_hosts()
        assert self.run_function('hosts.get_alias', ['127.0.0.1']) == \
            []

    def test_has_pair(self):
        '''
        hosts.has_pair
        '''
        assert self.run_function('hosts.has_pair', ['127.0.0.1', 'myname'])
        assert not self.run_function('hosts.has_pair', ['127.0.0.1', 'othername'])

    def test_set_host(self):
        '''
        hosts.set_hosts
        '''
        assert self.run_function('hosts.set_host', ['192.168.1.123', 'newip'])
        assert self.run_function('hosts.has_pair', ['192.168.1.123', 'newip'])
        assert self.run_function('hosts.set_host', ['127.0.0.1', 'localhost'])
        assert len(self.run_function('hosts.list_hosts')) == 11
        assert not self.run_function('hosts.has_pair', ['127.0.0.1', 'myname']), \
            'should remove second entry'

    def test_add_host(self):
        '''
        hosts.add_host
        '''
        assert self.run_function('hosts.add_host', ['192.168.1.123', 'newip'])
        assert self.run_function('hosts.has_pair', ['192.168.1.123', 'newip'])
        assert len(self.run_function('hosts.list_hosts')) == 11
        assert self.run_function('hosts.add_host', ['127.0.0.1', 'othernameip'])
        assert len(self.run_function('hosts.list_hosts')) == 11

    def test_rm_host(self):
        assert self.run_function('hosts.has_pair', ['127.0.0.1', 'myname'])
        assert self.run_function('hosts.rm_host', ['127.0.0.1', 'myname'])
        assert not self.run_function('hosts.has_pair', ['127.0.0.1', 'myname'])
        assert self.run_function('hosts.rm_host', ['127.0.0.1', 'unknown'])

    def test_add_host_formatting(self):
        '''
        Ensure that hosts.add_host isn't adding duplicates and that
        it's formatting the output correctly
        '''
        # instead of using the 'clean' hosts file we're going to
        # use an empty one so we can prove the syntax of the entries
        # being added by the hosts module
        self.__clear_hosts()
        with salt.utils.files.fopen(self.hosts_file, 'w'):
            pass

        assert self.run_function(
                'hosts.add_host', ['192.168.1.3', 'host3.fqdn.com']
            )
        assert self.run_function(
                'hosts.add_host', ['192.168.1.1', 'host1.fqdn.com']
            )
        assert self.run_function('hosts.add_host', ['192.168.1.1', 'host1'])
        assert self.run_function(
                'hosts.add_host', ['192.168.1.2', 'host2.fqdn.com']
            )
        assert self.run_function('hosts.add_host', ['192.168.1.2', 'host2'])
        assert self.run_function('hosts.add_host', ['192.168.1.2', 'oldhost2'])
        assert self.run_function(
                'hosts.add_host', ['192.168.1.2', 'host2-reorder']
            )
        assert self.run_function(
                'hosts.add_host', ['192.168.1.1', 'host1-reorder']
            )

        # now read the lines and ensure they're formatted correctly
        with salt.utils.files.fopen(self.hosts_file, 'r') as fp_:
            lines = salt.utils.stringutils.to_unicode(fp_.read()).splitlines()
        assert lines == [
            '192.168.1.3\t\thost3.fqdn.com',
            '192.168.1.1\t\thost1.fqdn.com host1 host1-reorder',
            '192.168.1.2\t\thost2.fqdn.com host2 oldhost2 host2-reorder',
        ]
