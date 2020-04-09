# -*- coding: utf-8 -*-
"""
integration tests for nilirt_ip
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import time

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, skip_if_not_root
from tests.support.unit import skipIf


@skip_if_not_root
@skipIf(not salt.utils.platform.is_linux(), "These tests can only be run on linux")
class Nilrt_ipModuleTest(ModuleCase):
    """
    Validate the nilrt_ip module
    """

    @classmethod
    def setUpClass(cls):
        cls.initialState = {}

    def setUp(self):
        """
        Get current settings
        """
        # save files from var/lib/connman*
        os_grain = self.run_function("grains.item", ["os_family"])
        if os_grain["os_family"] != "NILinuxRT":
            self.skipTest("Tests applicable only to NILinuxRT")
        super(Nilrt_ipModuleTest, self).setUp()
        self.run_function(
            "file.copy",
            [
                "/var/lib/connman",
                "/tmp/connman",
                "recurse=True",
                "remove_existing=True",
            ],
        )

    def tearDown(self):
        """
        Reset to original settings
        """
        # restore files
        self.run_function(
            "file.copy",
            [
                "/tmp/connman",
                "/var/lib/connman",
                "recurse=True",
                "remove_existing=True",
            ],
        )
        # restart connman
        self.run_function("service.restart", ["connman"])
        time.sleep(10)  # wait 10 seconds for connman to be fully loaded
        interfaces = self.__interfaces()
        for interface in interfaces:
            self.run_function("ip.up", [interface])

    def __connected(self, interface):
        return interface["up"]

    def __interfaces(self):
        interfaceList = []
        for iface in self.run_function("ip.get_interfaces_details")["interfaces"]:
            interfaceList.append(iface["connectionid"])
        return interfaceList

    @destructiveTest
    def test_down(self):
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.down", [interface])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details")
        for interface in info["interfaces"]:
            self.assertFalse(self.__connected(interface))

    @destructiveTest
    def test_up(self):
        interfaces = self.__interfaces()
        # first down all interfaces
        for interface in interfaces:
            self.run_function("ip.down", [interface])
        # up interfaces
        for interface in interfaces:
            result = self.run_function("ip.up", [interface])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details")
        for interface in info["interfaces"]:
            self.assertTrue(self.__connected(interface))

    @destructiveTest
    def test_set_dhcp_linklocal_all(self):
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.set_dhcp_linklocal_all", [interface])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details")
        for interface in info["interfaces"]:
            self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")

    @destructiveTest
    def test_static_all(self):
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function(
                "ip.set_static_all",
                [
                    interface,
                    "192.168.10.4",
                    "255.255.255.0",
                    "192.168.10.1",
                    "8.8.4.4 8.8.8.8",
                ],
            )
            self.assertTrue(result)

        info = self.run_function("ip.get_interfaces_details")
        for interface in info["interfaces"]:
            self.assertIn("8.8.4.4", interface["ipv4"]["dns"])
            self.assertIn("8.8.8.8", interface["ipv4"]["dns"])
            self.assertEqual(interface["ipv4"]["requestmode"], "static")
            self.assertEqual(interface["ipv4"]["address"], "192.168.10.4")
            self.assertEqual(interface["ipv4"]["netmask"], "255.255.255.0")
            self.assertEqual(interface["ipv4"]["gateway"], "192.168.10.1")
