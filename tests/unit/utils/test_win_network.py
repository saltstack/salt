import pytest

import salt.utils.win_network as win_network
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PhysicalAddress:
    def __init__(self, address):
        self.address = address

    def ToString(self):
        return str(self.address)


class Interface:
    """
    Mocked interface object
    """

    def __init__(
        self,
        i_address="02D5F1DD31E0",
        i_description="Dell GigabitEthernet",
        i_id="{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
        i_name="Ethernet",
        i_receive_only=False,
        i_status=1,
        i_type=6,
    ):
        self.PhysicalAddress = PhysicalAddress(i_address)
        self.Description = i_description
        self.Id = i_id
        self.Name = i_name
        self.NetworkInterfaceType = i_type
        self.IsReceiveOnly = i_receive_only
        self.OperationalStatus = i_status

    def GetPhysicalAddress(self):
        return self.PhysicalAddress


@pytest.mark.skip_unless_on_windows
class WinNetworkTestCase(TestCase):
    def setUp(self):
        self.mock_ip_base = MagicMock(
            return_value={
                "dns_enabled": False,
                "dns_suffix": "",
                "dynamic_dns_enabled": False,
            }
        )
        self.mock_unicast = MagicMock(
            return_value={
                "ip_addresses": [
                    {
                        "address": "172.18.87.49",
                        "broadcast": "172.18.87.63",
                        "loopback": "127.0.0.1",
                        "netmask": "255.255.255.240",
                        "prefix_length": 28,
                        "prefix_origin": "Manual",
                        "suffix_origin": "Manual",
                    }
                ],
                "ipv6_addresses": [
                    {
                        "address": "fe80::e8a4:1224:5548:2b81",
                        "interface_index": 32,
                        "prefix_length": 64,
                        "prefix_origin": "WellKnown",
                        "suffix_origin": "Router",
                    }
                ],
            }
        )
        self.mock_gateway = MagicMock(
            return_value={
                "ip_gateways": ["192.168.0.1"],
                "ipv6_gateways": ["fe80::208:a2ff:fe0b:de70"],
            }
        )
        self.mock_dns = MagicMock(
            return_value={
                "ip_dns": ["10.4.0.1", "10.1.0.1", "8.8.8.8"],
                "ipv6_dns": ["2600:740a:1:304::1"],
            }
        )
        self.mock_multicast = MagicMock(
            return_value={
                "ip_multicast": [
                    "224.0.0.1",
                    "224.0.0.251",
                    "224.0.0.252",
                    "230.230.230.230",
                    "239.0.0.250",
                    "239.255.255.250",
                ],
                "ipv6_multicast": [
                    "ff01::1",
                    "ff02::1",
                    "ff02::c",
                    "ff02::fb",
                    "ff02::1:3",
                    "ff02::1:ff0f:4c48",
                    "ff02::1:ffa6:f6e6",
                ],
            }
        )
        self.mock_anycast = MagicMock(
            return_value={"ip_anycast": [], "ipv6_anycast": []}
        )
        self.mock_wins = MagicMock(return_value={"ip_wins": []})

    def test_get_interface_info_dot_net(self):
        expected = {
            "Ethernet": {
                "alias": "Ethernet",
                "description": "Dell GigabitEthernet",
                "dns_enabled": False,
                "dns_suffix": "",
                "dynamic_dns_enabled": False,
                "id": "{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
                "ip_addresses": [
                    {
                        "address": "172.18.87.49",
                        "broadcast": "172.18.87.63",
                        "loopback": "127.0.0.1",
                        "netmask": "255.255.255.240",
                        "prefix_length": 28,
                        "prefix_origin": "Manual",
                        "suffix_origin": "Manual",
                    }
                ],
                "ip_anycast": [],
                "ip_dns": ["10.4.0.1", "10.1.0.1", "8.8.8.8"],
                "ip_gateways": ["192.168.0.1"],
                "ip_multicast": [
                    "224.0.0.1",
                    "224.0.0.251",
                    "224.0.0.252",
                    "230.230.230.230",
                    "239.0.0.250",
                    "239.255.255.250",
                ],
                "ip_wins": [],
                "ipv6_addresses": [
                    {
                        "address": "fe80::e8a4:1224:5548:2b81",
                        "interface_index": 32,
                        "prefix_length": 64,
                        "prefix_origin": "WellKnown",
                        "suffix_origin": "Router",
                    }
                ],
                "ipv6_anycast": [],
                "ipv6_dns": ["2600:740a:1:304::1"],
                "ipv6_gateways": ["fe80::208:a2ff:fe0b:de70"],
                "ipv6_multicast": [
                    "ff01::1",
                    "ff02::1",
                    "ff02::c",
                    "ff02::fb",
                    "ff02::1:3",
                    "ff02::1:ff0f:4c48",
                    "ff02::1:ffa6:f6e6",
                ],
                "physical_address": "02:D5:F1:DD:31:E0",
                "receive_only": False,
                "status": "Up",
                "type": "Ethernet",
            }
        }

        mock_int = MagicMock(return_value=[Interface()])
        with patch.object(
            win_network, "_get_network_interfaces", mock_int
        ), patch.object(
            win_network, "_get_ip_base_properties", self.mock_ip_base
        ), patch.object(
            win_network, "_get_ip_unicast_info", self.mock_unicast
        ), patch.object(
            win_network, "_get_ip_gateway_info", self.mock_gateway
        ), patch.object(
            win_network, "_get_ip_dns_info", self.mock_dns
        ), patch.object(
            win_network, "_get_ip_multicast_info", self.mock_multicast
        ), patch.object(
            win_network, "_get_ip_anycast_info", self.mock_anycast
        ), patch.object(
            win_network, "_get_ip_wins_info", self.mock_wins
        ):

            # ret = win_network._get_base_properties()
            results = win_network.get_interface_info_dot_net()

        self.assertDictEqual(expected, results)

    def test_get_network_info(self):
        expected = {
            "Dell GigabitEthernet": {
                "hwaddr": "02:D5:F1:DD:31:E0",
                "inet": [
                    {
                        "address": "172.18.87.49",
                        "broadcast": "172.18.87.63",
                        "gateway": "192.168.0.1",
                        "label": "Dell GigabitEthernet",
                        "netmask": "255.255.255.240",
                    }
                ],
                "inet6": [
                    {
                        "address": "fe80::e8a4:1224:5548:2b81",
                        "gateway": "fe80::208:a2ff:fe0b:de70",
                        "prefixlen": 64,
                    }
                ],
                "up": True,
            }
        }
        mock_int = MagicMock(return_value=[Interface()])
        with patch.object(
            win_network, "_get_network_interfaces", mock_int
        ), patch.object(
            win_network, "_get_ip_base_properties", self.mock_ip_base
        ), patch.object(
            win_network, "_get_ip_unicast_info", self.mock_unicast
        ), patch.object(
            win_network, "_get_ip_gateway_info", self.mock_gateway
        ), patch.object(
            win_network, "_get_ip_dns_info", self.mock_dns
        ), patch.object(
            win_network, "_get_ip_multicast_info", self.mock_multicast
        ), patch.object(
            win_network, "_get_ip_anycast_info", self.mock_anycast
        ), patch.object(
            win_network, "_get_ip_wins_info", self.mock_wins
        ):

            # ret = win_network._get_base_properties()
            results = win_network.get_interface_info()

        self.assertDictEqual(expected, results)

    def test__get_base_properties_tap_adapter(self):
        """
        Adapter Type 53 is apparently an undocumented type corresponding to
        OpenVPN TAP Adapters and possibly other TAP Adapters. This test makes
        sure the win_network util will catch that.
        https://github.com/saltstack/salt/issues/56196
        https://github.com/saltstack/salt/issues/56275
        """
        i_face = Interface(
            i_address="03DE4D0713FA",
            i_description="Windows TAP Adapter",
            i_id="{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
            i_name="Windows TAP Adapter",
            i_receive_only=False,
            i_status=1,
            i_type=53,
        )
        expected = {
            "alias": "Windows TAP Adapter",
            "description": "Windows TAP Adapter",
            "id": "{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
            "receive_only": False,
            "physical_address": "03:DE:4D:07:13:FA",
            "status": "Up",
            "type": "TAPAdapter",
        }
        results = win_network._get_base_properties(i_face=i_face)
        self.assertDictEqual(expected, results)

    def test__get_base_properties_undefined_adapter(self):
        """
        The Adapter Type 53 may be an arbitrary number assigned by OpenVPN.
        This will test the ability to avoid stack tracing on an undefined
        adapter type. If one is encountered, just use the description.
        """
        i_face = Interface(
            i_address="03DE4D0713FA",
            i_description="Undefined Adapter",
            i_id="{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
            i_name="Undefined",
            i_receive_only=False,
            i_status=1,
            i_type=50,
        )
        expected = {
            "alias": "Undefined",
            "description": "Undefined Adapter",
            "id": "{C5F468C0-DD5F-4C2B-939F-A411DCB5DE16}",
            "receive_only": False,
            "physical_address": "03:DE:4D:07:13:FA",
            "status": "Up",
            "type": "Undefined Adapter",
        }
        results = win_network._get_base_properties(i_face=i_face)
        self.assertDictEqual(expected, results)
