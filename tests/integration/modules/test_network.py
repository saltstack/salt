# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import Salt Libs
import salt.utils.path
import salt.utils.platform

URL = 'google-public-dns-a.google.com'


class NetworkTest(ModuleCase):
    '''
    Validate network module
    '''
    def test_network_ping(self):
        '''
        network.ping
        '''
        ret = self.run_function('network.ping', [URL])
        exp_out = ['ping', URL, 'ms', 'time']
        for out in exp_out:
            self.assertIn(out, ret.lower())

    @skipIf(salt.utils.platform.is_darwin(), 'not supported on macosx')
    def test_network_netstat(self):
        '''
        network.netstat
        '''
        ret = self.run_function('network.netstat')
        exp_out = ['proto', 'local-address']
        for val in ret:
            for out in exp_out:
                self.assertIn(out, val)

    def test_network_traceroute(self):
        '''
        network.traceroute
        '''
        if not salt.utils.path.which('traceroute') and not salt.utils.platform.is_windows():
            self.skipTest('traceroute not installed')
        ret = self.run_function('network.traceroute', [URL])
        exp_out = ['hostname', 'ip']
        for out in exp_out:
            self.assertIn(out, exp_out)

    @skipIf(not salt.utils.platform.is_windows(), 'windows only test')
    def test_network_nslookup(self):
        '''
        network.nslookup
        '''
        ret = self.run_function('network.nslookup', [URL])
        exp_out = ['Server', 'Address']
        for out in exp_out:
            self.assertIn(out, exp_out)
