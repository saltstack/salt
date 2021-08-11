"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import types

import salt.modules.win_dns_client as win_dns_client
import salt.utils.stringutils
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock, patch
from tests.support.unit import TestCase, skipIf

try:
    import wmi

    HAS_WMI = True
except ImportError:
    HAS_WMI = False


class Mockwmi:
    """
    Mock wmi class
    """

    NetConnectionID = "Local Area Connection"
    Index = 0
    DNSServerSearchOrder = ["10.1.1.10"]
    Description = "Local Area Connection"
    DHCPEnabled = True

    def __init__(self):
        pass


class Mockwinapi:
    """
    Mock winapi class
    """

    def __init__(self):
        pass

    class winapi:
        """
        Mock winapi class
        """

        def __init__(self):
            pass

        @staticmethod
        def Com():
            """
            Mock Com method
            """
            return True


@skipIf(not HAS_WMI, "WMI only available on Windows")
class WinDnsClientTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_dns_client
    """

    def setup_loader_modules(self):
        # wmi and pythoncom modules are platform specific...
        mock_pythoncom = types.ModuleType(salt.utils.stringutils.to_str("pythoncom"))
        sys_modules_patcher = patch.dict("sys.modules", {"pythoncom": mock_pythoncom})
        sys_modules_patcher.start()
        self.addCleanup(sys_modules_patcher.stop)
        self.WMI = Mock()
        self.addCleanup(delattr, self, "WMI")
        return {win_dns_client: {"wmi": wmi}}

    # 'get_dns_servers' function tests: 1

    def test_get_dns_servers(self):
        """
        Test if it return a list of the configured DNS servers
        of the specified interface.
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_NetworkAdapter", return_value=[Mockwmi()]
        ), patch.object(
            self.WMI, "Win32_NetworkAdapterConfiguration", return_value=[Mockwmi()]
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            self.assertListEqual(
                win_dns_client.get_dns_servers("Local Area Connection"), ["10.1.1.10"]
            )

            self.assertFalse(win_dns_client.get_dns_servers("Ethernet"))

    # 'rm_dns' function tests: 1

    def test_rm_dns(self):
        """
        Test if it remove the DNS server from the network interface.
        """
        with patch.dict(
            win_dns_client.__salt__, {"cmd.retcode": MagicMock(return_value=0)}
        ):
            self.assertTrue(win_dns_client.rm_dns("10.1.1.10"))

    # 'add_dns' function tests: 1

    def test_add_dns(self):
        """
        Test if it add the DNS server to the network interface.
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_NetworkAdapter", return_value=[Mockwmi()]
        ), patch.object(
            self.WMI, "Win32_NetworkAdapterConfiguration", return_value=[Mockwmi()]
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            self.assertFalse(win_dns_client.add_dns("10.1.1.10", "Ethernet"))

            self.assertTrue(
                win_dns_client.add_dns("10.1.1.10", "Local Area Connection")
            )

        with patch.object(
            win_dns_client, "get_dns_servers", MagicMock(return_value=["10.1.1.10"])
        ), patch.dict(
            win_dns_client.__salt__, {"cmd.retcode": MagicMock(return_value=0)}
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            self.assertTrue(win_dns_client.add_dns("10.1.1.0", "Local Area Connection"))

    # 'dns_dhcp' function tests: 1

    def test_dns_dhcp(self):
        """
        Test if it configure the interface to get its
        DNS servers from the DHCP server
        """
        with patch.dict(
            win_dns_client.__salt__, {"cmd.retcode": MagicMock(return_value=0)}
        ):
            self.assertTrue(win_dns_client.dns_dhcp())

    # 'get_dns_config' function tests: 1

    def test_get_dns_config(self):
        """
        Test if it get the type of DNS configuration (dhcp / static)
        """
        with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
            self.WMI, "Win32_NetworkAdapter", return_value=[Mockwmi()]
        ), patch.object(
            self.WMI, "Win32_NetworkAdapterConfiguration", return_value=[Mockwmi()]
        ), patch.object(
            wmi, "WMI", Mock(return_value=self.WMI)
        ):
            self.assertTrue(win_dns_client.get_dns_config())

    @patch("salt.utils.platform.is_windows")
    def test___virtual__non_windows(self, mock):
        mock.return_value = False
        result = win_dns_client.__virtual__()
        expected = (
            False,
            "Module win_dns_client: module only works on Windows systems",
        )
        self.assertEqual(result, expected)

    @patch.object(win_dns_client, "HAS_LIBS", False)
    def test___virtual__missing_libs(self):
        result = win_dns_client.__virtual__()
        expected = (False, "Module win_dns_client: missing required libraries")
        self.assertEqual(result, expected)

    def test___virtual__(self):
        result = win_dns_client.__virtual__()
        expected = "win_dns_client"
        self.assertEqual(result, expected)
