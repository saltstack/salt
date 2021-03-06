"""
integration tests for nilirt_ip
"""

import configparser
import re
import shutil
import time

import pytest
import salt.modules.nilrt_ip as ip
import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import requires_system_grains, runs_on
from tests.support.unit import skipIf

try:
    import pyiface
    from pyiface.ifreqioctls import IFF_LOOPBACK, IFF_RUNNING
except ImportError:
    pyiface = None

try:
    from requests.structures import CaseInsensitiveDict
except ImportError:
    CaseInsensitiveDict = None

INTERFACE_FOR_TEST = "eth1"


@pytest.mark.skip_if_not_root
@skipIf(not pyiface, "The python pyiface package is not installed")
@skipIf(not CaseInsensitiveDict, "The python package requests is not installed")
@runs_on(os_family="NILinuxRT", reason="Tests applicable only to NILinuxRT")
@pytest.mark.destructive_test
class NilrtIpModuleTest(ModuleCase):
    """
    Validate the nilrt_ip module
    """

    @requires_system_grains
    @classmethod
    def setUpClass(cls, grains):  # pylint: disable=arguments-differ
        cls.initialState = {}
        cls.grains = grains

    @classmethod
    def tearDownClass(cls):
        cls.initialState = cls.grains = None

    @staticmethod
    def setup_loader_modules():
        """
        Setup loader modules
        """
        return {ip: {}}

    def setUp(self):
        """
        Get current settings
        """
        # save files from var/lib/connman*
        super().setUp()
        if self.grains["lsb_distrib_id"] == "nilrt":
            shutil.move("/etc/natinst/share/ni-rt.ini", "/tmp/ni-rt.ini")
        else:
            shutil.move("/var/lib/connman", "/tmp/connman")

    def tearDown(self):
        """
        Reset to original settings
        """
        # restore files
        if self.grains["lsb_distrib_id"] == "nilrt":
            shutil.move("/tmp/ni-rt.ini", "/etc/natinst/share/ni-rt.ini")
            self.run_function("cmd.run", ["/etc/init.d/networking restart"])
        else:
            shutil.move("/tmp/connman", "/var/lib/connman")
            self.run_function("service.restart", ["connman"])
        time.sleep(10)  # wait 10 seconds for connman to be fully loaded
        interfaces = self.__interfaces()
        for interface in interfaces:
            self.run_function("ip.up", [interface.name])

    @staticmethod
    def __connected(interface):
        """
        Check if an interface is up or down
        :param interface: pyiface.Interface object
        :return: True, if interface is up, otherwise False.
        """
        return interface.flags & IFF_RUNNING != 0

    @staticmethod
    def __interfaces():
        """
        Return the list of all interfaces without loopback
        """
        return [
            interface
            for interface in pyiface.getIfaces()
            if interface.flags & IFF_LOOPBACK == 0
        ]

    def __check_ethercat(self):
        """
        Check if ethercat is installed.

        :return: True if ethercat is installed, otherwise False.
        """
        if self.grains["lsb_distrib_id"] != "nilrt":
            return False
        with salt.utils.files.fopen("/etc/natinst/share/ni-rt.ini", "r") as config_file:
            config_parser = configparser.RawConfigParser(dict_type=CaseInsensitiveDict)
            config_parser.readfp(config_file)
            return (
                "ethercat"
                in config_parser.get(
                    "lvrt", "AdditionalNetworkProtocols", fallback=""
                ).lower()
            )

    def test_down(self):
        """
        Test ip.down function
        """
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.down", [interface.name])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if self.grains["lsb_distrib_id"] == "nilrt":
                self.assertEqual(interface["adapter_mode"], "disabled")
            self.assertFalse(
                self.__connected(pyiface.Interface(name=interface["connectionid"]))
            )

    def test_up(self):
        """
        Test ip.up function
        """
        interfaces = self.__interfaces()
        # first down all interfaces
        for interface in interfaces:
            self.run_function("ip.down", [interface.name])
            self.assertFalse(self.__connected(interface))
        # up interfaces
        for interface in interfaces:
            result = self.run_function("ip.up", [interface.name])
            self.assertTrue(result)
        if self.grains["lsb_distrib_id"] == "nilrt":
            info = self.run_function("ip.get_interfaces_details", timeout=300)
            for interface in info["interfaces"]:
                self.assertEqual(interface["adapter_mode"], "tcpip")

    def test_set_dhcp_linklocal_all(self):
        """
        Test ip.set_dhcp_linklocal_all function
        """
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.set_dhcp_linklocal_all", [interface.name])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
            if self.grains["lsb_distrib_id"] == "nilrt":
                self.assertEqual(interface["adapter_mode"], "tcpip")

    def test_set_dhcp_only_all(self):
        """
        Test ip.set_dhcp_only_all function
        """
        if self.grains["lsb_distrib_id"] != "nilrt":
            self.skipTest("Test not applicable to newer nilrt")
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.set_dhcp_only_all", [interface.name])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_only")
            self.assertEqual(interface["adapter_mode"], "tcpip")

    def test_set_linklocal_only_all(self):
        """
        Test ip.set_linklocal_only_all function
        """
        if self.grains["lsb_distrib_id"] != "nilrt":
            self.skipTest("Test not applicable to newer nilrt")
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function("ip.set_linklocal_only_all", [interface.name])
            self.assertTrue(result)
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            self.assertEqual(interface["ipv4"]["requestmode"], "linklocal_only")
            self.assertEqual(interface["adapter_mode"], "tcpip")

    def test_static_all(self):
        """
        Test ip.set_static_all function
        """
        interfaces = self.__interfaces()
        for interface in interfaces:
            result = self.run_function(
                "ip.set_static_all",
                [
                    interface.name,
                    "192.168.10.4",
                    "255.255.255.0",
                    "192.168.10.1",
                    "8.8.4.4 8.8.8.8",
                ],
            )
            self.assertTrue(result)

        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if self.grains["lsb_distrib_id"] != "nilrt":
                self.assertIn("8.8.4.4", interface["ipv4"]["dns"])
                self.assertIn("8.8.8.8", interface["ipv4"]["dns"])
            else:
                self.assertEqual(interface["ipv4"]["dns"], ["8.8.4.4"])
                self.assertEqual(interface["adapter_mode"], "tcpip")
            self.assertEqual(interface["ipv4"]["requestmode"], "static")
            self.assertEqual(interface["ipv4"]["address"], "192.168.10.4")
            self.assertEqual(interface["ipv4"]["netmask"], "255.255.255.0")
            self.assertEqual(interface["ipv4"]["gateway"], "192.168.10.1")

    def test_supported_adapter_modes(self):
        """
        Test supported adapter modes for each interface
        """
        if self.grains["lsb_distrib_id"] != "nilrt":
            self.skipTest("Test is just for older nilrt distros")
        interface_pattern = re.compile("^eth[0-9]+$")
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == "eth0":
                self.assertEqual(interface["supported_adapter_modes"], ["tcpip"])
            else:
                self.assertIn("tcpip", interface["supported_adapter_modes"])
                if not interface_pattern.match(interface["connectionid"]):
                    self.assertNotIn("ethercat", interface["supported_adapter_modes"])
                elif self.__check_ethercat():
                    self.assertIn("ethercat", interface["supported_adapter_modes"])

    def test_ethercat(self):
        """
        Test ip.set_ethercat function
        """
        if not self.__check_ethercat():
            self.skipTest("Test is just for systems with Ethercat")
        self.assertTrue(self.run_function("ip.set_ethercat", [INTERFACE_FOR_TEST, 19]))
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["adapter_mode"], "ethercat")
                self.assertEqual(int(interface["ethercat"]["masterid"]), 19)
                break
        self.assertTrue(
            self.run_function("ip.set_dhcp_linklocal_all", [INTERFACE_FOR_TEST])
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["adapter_mode"], "tcpip")
                self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
                break

    @pytest.mark.destructive_test
    def test_dhcp_disable(self):
        """
        Test cases:
            - dhcp -> disable
            - disable -> dhcp
        """
        if self.grains["lsb_distrib_id"] == "nilrt":
            self.skipTest("Test is just for newer nilrt distros")

        self.assertTrue(
            self.run_function("ip.set_dhcp_linklocal_all", [INTERFACE_FOR_TEST])
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
                break

        self.assertTrue(self.run_function("ip.disable", [INTERFACE_FOR_TEST]))
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "disabled")
                break

        self.assertTrue(
            self.run_function("ip.set_dhcp_linklocal_all", [INTERFACE_FOR_TEST])
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
                break

    @pytest.mark.destructive_test
    def test_dhcp_static(self):
        """
        Test cases:
            - dhcp -> static
            - static -> dhcp
        """
        if self.grains["lsb_distrib_id"] == "nilrt":
            self.skipTest("Test is just for newer nilrt distros")

        self.assertTrue(
            self.run_function("ip.set_dhcp_linklocal_all", [INTERFACE_FOR_TEST])
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
                break

        self.assertTrue(
            self.run_function(
                "ip.set_static_all",
                [
                    INTERFACE_FOR_TEST,
                    "192.168.1.125",
                    "255.255.255.0",
                    "192.168.1.1",
                    "8.8.8.8 8.8.8.4",
                ],
            )
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "static")
                self.assertEqual(interface["ipv4"]["address"], "192.168.1.125")
                self.assertEqual(interface["ipv4"]["netmask"], "255.255.255.0")
                self.assertIn("8.8.8.4", interface["ipv4"]["dns"])
                self.assertIn("8.8.8.8", interface["ipv4"]["dns"])
                break

        self.assertTrue(
            self.run_function("ip.set_dhcp_linklocal_all", [INTERFACE_FOR_TEST])
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "dhcp_linklocal")
                break

    @pytest.mark.destructive_test
    def test_static_disable(self):
        """
        Test cases:
            - static -> disable
            - disable -> static
        """
        if self.grains["lsb_distrib_id"] == "nilrt":
            self.skipTest("Test is just for newer nilrt distros")

        self.assertTrue(
            self.run_function(
                "ip.set_static_all",
                [
                    INTERFACE_FOR_TEST,
                    "192.168.1.125",
                    "255.255.255.0",
                    "192.168.1.1",
                    "8.8.8.8",
                ],
            )
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "static")
                self.assertEqual(interface["ipv4"]["address"], "192.168.1.125")
                self.assertEqual(interface["ipv4"]["netmask"], "255.255.255.0")
                self.assertEqual(interface["ipv4"]["dns"], ["8.8.8.8"])
                break

        self.assertTrue(self.run_function("ip.disable", [INTERFACE_FOR_TEST]))
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "disabled")
                break

        self.assertTrue(
            self.run_function(
                "ip.set_static_all",
                [INTERFACE_FOR_TEST, "192.168.1.125", "255.255.255.0", "192.168.1.1"],
            )
        )
        info = self.run_function("ip.get_interfaces_details", timeout=300)
        for interface in info["interfaces"]:
            if interface["connectionid"] == INTERFACE_FOR_TEST:
                self.assertEqual(interface["ipv4"]["requestmode"], "static")
                self.assertEqual(interface["ipv4"]["address"], "192.168.1.125")
                self.assertEqual(interface["ipv4"]["netmask"], "255.255.255.0")
                self.assertEqual(interface["ipv4"]["dns"], [])
                break
