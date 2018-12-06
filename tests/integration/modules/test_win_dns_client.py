# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils.platform


@skipIf(not salt.utils.platform.is_windows(), 'windows test only')
class WinDNSTest(ModuleCase):
    '''
    Test for salt.modules.win_dns_client
    '''
    @destructiveTest
    def test_add_remove_dns(self):
        '''
        Test add and removing a dns server
        '''
        dns = '8.8.8.8'
        interface = 'Ethernet'
        # add dns server
        self.assertTrue(self.run_function('win_dns_client.add_dns', [dns, interface], index=42))

        srvs = self.run_function('win_dns_client.get_dns_servers', interface=interface)
        self.assertIn(dns, srvs)

        # remove dns server
        self.assertTrue(self.run_function('win_dns_client.rm_dns', [dns], interface=interface))

        srvs = self.run_function('win_dns_client.get_dns_servers', interface=interface)
        self.assertNotIn(dns, srvs)
