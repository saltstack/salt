# -*- coding: utf-8 -*-

from __future__ import absolute_import

import pytest
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, slowTest
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
@pytest.mark.windows_whitelisted
class WinDNSTest(ModuleCase):
    """
    Test for salt.modules.win_dns_client
    """

    @destructiveTest
    @slowTest
    def test_add_remove_dns(self):
        """
        Test add and removing a dns server
        """
        # Get a list of interfaces on the system
        interfaces = self.run_function("network.interfaces_names")
        skipIf(interfaces.count == 0, "This test requires a network interface")

        interface = interfaces[0]
        dns = "8.8.8.8"
        # add dns server
        self.assertTrue(
            self.run_function("win_dns_client.add_dns", [dns, interface], index=42)
        )

        srvs = self.run_function("win_dns_client.get_dns_servers", interface=interface)
        self.assertIn(dns, srvs)

        # remove dns server
        self.assertTrue(
            self.run_function("win_dns_client.rm_dns", [dns], interface=interface)
        )

        srvs = self.run_function("win_dns_client.get_dns_servers", interface=interface)
        self.assertNotIn(dns, srvs)
