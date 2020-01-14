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
    Test proxy minion functionality
    '''
    def test_can_it_ping(self):
        '''
        Ensure the proxy can ping
        '''
        ret = self.run_function('test.ping', minion_tgt='proxytest')
        assert ret is True

    def test_list_pkgs(self):
        '''
        Package test 1, really just tests that the virtual function capability
        is working OK.
        '''
        ret = self.run_function('pkg.list_pkgs', minion_tgt='proxytest')
        assert 'coreutils' in ret
        assert 'apache' in ret
        assert 'redbull' in ret

    def test_install_pkgs(self):
        '''
        Package test 2, really just tests that the virtual function capability
        is working OK.
        '''
        ret = self.run_function('pkg.install', ['thispkg'], minion_tgt='proxytest')
        assert ret['thispkg'] == '1.0'

        ret = self.run_function('pkg.list_pkgs', minion_tgt='proxytest')

        assert ret['apache'] == '2.4'
        assert ret['redbull'] == '999.99'
        assert ret['thispkg'] == '1.0'

    def test_remove_pkgs(self):
        ret = self.run_function('pkg.remove', ['apache'], minion_tgt='proxytest')
        assert 'apache' not in ret

    def test_upgrade(self):
        ret = self.run_function('pkg.upgrade', minion_tgt='proxytest')
        assert ret['coreutils']['new'] == '2.0'
        assert ret['redbull']['new'] == '1000.99'

    def test_service_list(self):
        ret = self.run_function('service.list', minion_tgt='proxytest')
        assert 'ntp' in ret

    def test_service_stop(self):
        ret = self.run_function('service.stop', ['ntp'], minion_tgt='proxytest')
        ret = self.run_function('service.status', ['ntp'], minion_tgt='proxytest')
        assert not ret

    def test_service_start(self):
        ret = self.run_function('service.start', ['samba'], minion_tgt='proxytest')
        ret = self.run_function('service.status', ['samba'], minion_tgt='proxytest')
        assert ret

    def test_service_get_all(self):
        ret = self.run_function('service.get_all', minion_tgt='proxytest')
        assert ret
        assert 'samba' in ' '.join(ret)

    def test_grains_items(self):
        ret = self.run_function('grains.items', minion_tgt='proxytest')
        assert ret['kernel'] == 'proxy'
        assert ret['kernelrelease'] == 'proxy'

    def test_state_apply(self):
        ret = self.run_function('state.apply', ['core'], minion_tgt='proxytest')
        for key, value in ret.items():
            assert value['result']

    def test_state_highstate(self):
        ret = self.run_function('state.highstate', minion_tgt='proxytest')
        for key, value in ret.items():
            assert value['result']
