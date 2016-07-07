# -*- encoding: utf-8 -*-
'''
    :codeauthor: :email: `Justin Anderson <janderson@saltstack.com>`

    tests.integration.states.network
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Python libs
from __future__ import absolute_import

# Salt libs
import integration

# Salttesting libs
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')


@destructiveTest
class NetworkTest(integration.ModuleCase, integration.SaltReturnAssertsMixIn):
    '''
    Validate network state module
    '''
    def setUp(self):
        os_family = self.run_function('grains.get', ['os_family'])
        if os_family not in ('RedHat', 'Debian'):
            self.skipTest('Network state only supported on RedHat and Debian based systems')

    def test_managed(self):
        '''
        network.managed
        '''
        state_key = 
        ret = self.run_function('state.sls', mods='network.managed', test=True)
                   
        out = ret['network_|-dummy0_|-dummy0_|-managed']['comment'].split('\n')
                   
        self.assertIn('Interface dummy0 is set to be updated:', out)
        self.assertIn(' DEVICE="dummy0"', out)
        self.assertIn(' USERCTL="no"', out)
        self.assertIn(' ONBOOT="yes"', out)
        self.assertIn(' IPADDR="10.1.0.1"', out)
                   
    def test_routes(self):
        '''        
        network.routes
        '''        
        state_key = 'network_|-routes_|-dummy0_|-routes'
        expected_changes = 'Interface dummy0 routes are set to be added.'
                   
        ret = self.run_function('state.sls', mods='network.routes', test=True)
        print(ret) 
                   
        self.assertEqual(ret[state_key]['comment'], expected_changes)
                   
    def test_system(self):
        '''        
        network.system
        '''        
        state_key = 'network_|-system_|-system_|-system'
        comment_out = 'Global network settings are set to be updated:\n--- \n+++ \n@@ -1 +1,4 @@\n-# Created by anaconda\n+NETWORKING=yes\n+HOSTNAME=server1.example.com\n+GATEWAY=10.1.0.1\n+GATEWAYDEV=dummy0'
                   
        ret = self.run_function('state.sls', mods='network.system', test=True)
        self.assertEqual(ret[state_key]['comment'], comment_out)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetworkTest)
