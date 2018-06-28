# -*- coding: utf-8 -*-
'''
    :codeauthor: Thayne Harbaugh (tharbaug@adobe.com)

    tests.integration.shell.proxy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.json as json

# Import salt tests libs
from tests.support.case import ShellCase


class ProxyCallerSimpleTestCase(ShellCase):
    '''
    Test salt-call --proxyid <proxyid> commands
    '''
    @staticmethod
    def _load_return(ret):
        return json.loads('\n'.join(ret))

    def test_can_it_ping(self):
        '''
        Ensure the proxy can ping
        '''
        ret = self._load_return(self.run_call('--proxyid proxytest --out=json test.ping'))
        self.assertEqual(ret['local'], True)

    def test_list_pkgs(self):
        '''
        Package test 1, really just tests that the virtual function capability
        is working OK.
        '''
        ret = self._load_return(self.run_call('--proxyid proxytest --out=json pkg.list_pkgs'))
        self.assertIn('coreutils', ret['local'])
        self.assertIn('apache', ret['local'])
        self.assertIn('redbull', ret['local'])

    def test_service_list(self):
        ret = self._load_return(self.run_call('--proxyid proxytest --out=json service.list'))
        self.assertIn('ntp', ret['local'])

    def test_grains_items(self):
        ret = self._load_return(self.run_call('--proxyid proxytest --out=json grains.items'))
        self.assertEqual(ret['local']['kernel'], 'proxy')
        self.assertEqual(ret['local']['kernelrelease'], 'proxy')
