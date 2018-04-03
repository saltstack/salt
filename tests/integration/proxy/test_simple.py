# -*- coding: utf-8 -*-
'''
Simple Smoke Tests for Connected Proxy Minion
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase


class ProxyMinionSimpleTestCase(ModuleCase):
    '''
    Test minion blackout functionality
    '''
    def test_can_it_ping(self):
        '''
        Ensure the proxy can ping
        '''
        ret = self.run_function('test.ping', minion_tgt='proxytest')
        self.assertEqual(ret, True)

    def test_list_pkgs(self):
        '''
        Package test 1, really just tests that the virtual function capability
        is working OK.
        '''
        ret = self.run_function('pkg.list_pkgs', minion_tgt='proxytest')
        self.assertIn('coreutils', ret)
        self.assertIn('apache', ret)
        self.assertIn('redbull', ret)

    def test_install_pkgs(self):
        '''
        Package test 2, really just tests that the virtual function capability
        is working OK.
        '''
        ret = self.run_function('pkg.install', ['thispkg'], minion_tgt='proxytest')
        self.assertEqual(ret['thispkg'], '1.0')

        ret = self.run_function('pkg.list_pkgs', minion_tgt='proxytest')

        self.assertEqual(ret['apache'], '2.4')
        self.assertEqual(ret['redbull'], '999.99')
        self.assertEqual(ret['thispkg'], '1.0')

    def test_remove_pkgs(self):
        ret = self.run_function('pkg.remove', ['apache'], minion_tgt='proxytest')
        self.assertNotIn('apache', ret)

    def test_upgrade(self):
        ret = self.run_function('pkg.upgrade', minion_tgt='proxytest')
        self.assertEqual(ret['coreutils']['new'], '2.0')
        self.assertEqual(ret['redbull']['new'], '1000.99')

    def test_service_list(self):
        ret = self.run_function('service.list', minion_tgt='proxytest')
        self.assertIn('ntp', ret)

    def test_service_stop(self):
        ret = self.run_function('service.stop', ['ntp'], minion_tgt='proxytest')
        ret = self.run_function('service.status', ['ntp'], minion_tgt='proxytest')
        self.assertFalse(ret)

    def test_service_start(self):
        ret = self.run_function('service.start', ['samba'], minion_tgt='proxytest')
        ret = self.run_function('service.status', ['samba'], minion_tgt='proxytest')
        self.assertTrue(ret)

    def test_service_get_all(self):
        ret = self.run_function('service.get_all', minion_tgt='proxytest')
        self.assertTrue(ret)
        self.assertIn('samba', ' '.join(ret))

    def test_grains_items(self):
        ret = self.run_function('grains.items', minion_tgt='proxytest')
        self.assertEqual(ret['kernel'], 'proxy')
        self.assertEqual(ret['kernelrelease'], 'proxy')

    def test_state_apply(self):
        ret = self.run_function('state.apply', ['core'], minion_tgt='proxytest')
        for key, value in ret.items():
            self.assertTrue(value['result'])

    def test_state_highstate(self):
        ret = self.run_function('state.highstate', minion_tgt='proxytest')
        for key, value in ret.items():
            self.assertTrue(value['result'])
