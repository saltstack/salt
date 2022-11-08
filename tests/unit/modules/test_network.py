import logging
import os.path
import shutil
import socket

import salt.config
import salt.modules.network as network
import salt.utils.path
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


class NetworkTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.network
    """

    def setup_loader_modules(self):
        opts = salt.config.DEFAULT_MINION_OPTS.copy()
        utils = salt.loader.utils(
            opts, whitelist=["network", "path", "platform", "stringutils"]
        )
        return {
            network: {"__utils__": utils},
        }

    @patch("salt.utils.platform.is_windows")
    def test___virtual__is_windows_true(self, mock_is_windows):
        mock_is_windows.return_value = True
        result = network.__virtual__()
        expected = (
            False,
            "The network execution module cannot be loaded on Windows: use win_network"
            " instead.",
        )
        self.assertEqual(result, expected)

    @patch("salt.utils.platform.is_windows")
    def test___virtual__is_windows_false(self, mock_is_windows):
        mock_is_windows.return_value = False
        result = network.__virtual__()
        self.assertEqual(result, True)

    def test_wol_bad_mac(self):
        """
        tests network.wol with bad mac
        """
        bad_mac = "31337"
        self.assertRaises(ValueError, network.wol, bad_mac)

    def test_wol_success(self):
        """
        tests network.wol success
        """
        mac = "080027136977"
        bcast = "255.255.255.255 7"

        class MockSocket:
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, *args, **kwargs):
                pass

            def setsockopt(self, *args, **kwargs):
                pass

            def sendto(self, *args, **kwargs):
                pass

        with patch("socket.socket", MockSocket):
            self.assertTrue(network.wol(mac, bcast))

    def test_ping(self):
        """
        Test for Performs a ping to a host
        """
        with patch.dict(
            network.__utils__, {"network.sanitize_host": MagicMock(return_value="A")}
        ):
            mock_all = MagicMock(side_effect=[{"retcode": 1}, {"retcode": 0}])
            with patch.dict(network.__salt__, {"cmd.run_all": mock_all}):
                self.assertFalse(network.ping("host", return_boolean=True))

                self.assertTrue(network.ping("host", return_boolean=True))

            with patch.dict(network.__salt__, {"cmd.run": MagicMock(return_value="A")}):
                self.assertEqual(network.ping("host"), "A")

    def test_netstat(self):
        """
        Test for return information on open ports and states
        """
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.object(network, "_netstat_linux", return_value="A"):
                with patch.object(network, "_ss_linux", return_value="A"):
                    self.assertEqual(network.netstat(), "A")

        with patch.dict(network.__grains__, {"kernel": "OpenBSD"}):
            with patch.object(network, "_netstat_bsd", return_value="A"):
                self.assertEqual(network.netstat(), "A")

        with patch.dict(network.__grains__, {"kernel": "A"}):
            self.assertRaises(CommandExecutionError, network.netstat)

    def test_active_tcp(self):
        """
        Test for return a dict containing information on all
         of the running TCP connections
        """
        with patch.dict(
            network.__utils__, {"network.active_tcp": MagicMock(return_value="A")}
        ):
            with patch.dict(network.__grains__, {"kernel": "Linux"}):
                self.assertEqual(network.active_tcp(), "A")

    def test_traceroute(self):
        """
        Test for Performs a traceroute to a 3rd party host
        """

        def patched_which(binary):
            binary_path = shutil.which(binary)
            if binary_path:
                # The path exists, just return it
                return binary_path
            if binary == "traceroute":
                # The path doesn't exist but we mock it on the test.
                # Return the binary name
                return binary
            # The binary does not exist
            return binary_path

        with patch("salt.utils.path.which", patched_which):
            with patch.dict(network.__salt__, {"cmd.run": MagicMock(return_value="")}):
                self.assertListEqual(network.traceroute("gentoo.org"), [])

            with patch.dict(
                network.__utils__,
                {"network.sanitize_host": MagicMock(return_value="gentoo.org")},
            ):
                with patch.dict(
                    network.__salt__, {"cmd.run": MagicMock(return_value="")}
                ):
                    self.assertListEqual(network.traceroute("gentoo.org"), [])

    def test_dig(self):
        """
        Test for Performs a DNS lookup with dig
        """
        with patch("salt.utils.path.which", MagicMock(return_value="dig")), patch.dict(
            network.__utils__, {"network.sanitize_host": MagicMock(return_value="A")}
        ), patch.dict(network.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            self.assertEqual(network.dig("host"), "A")

    def test_arp(self):
        """
        Test for return the arp table from the minion
        """
        with patch.dict(
            network.__salt__, {"cmd.run": MagicMock(return_value="A,B,C,D\nE,F,G,H\n")}
        ), patch("salt.utils.path.which", MagicMock(return_value="")):
            self.assertDictEqual(network.arp(), {})

    def test_interfaces(self):
        """
        Test for return a dictionary of information about
         all the interfaces on the minion
        """
        with patch.dict(
            network.__utils__, {"network.interfaces": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.interfaces(), {})

    def test_hw_addr(self):
        """
        Test for return the hardware address (a.k.a. MAC address)
         for a given interface
        """
        with patch.dict(
            network.__utils__, {"network.hw_addr": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.hw_addr("iface"), {})

    def test_interface(self):
        """
        Test for return the inet address for a given interface
        """
        with patch.dict(
            network.__utils__, {"network.interface": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.interface("iface"), {})

    def test_interface_ip(self):
        """
        Test for return the inet address for a given interface
        """
        with patch.dict(
            network.__utils__, {"network.interface_ip": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.interface_ip("iface"), {})

    def test_subnets(self):
        """
        Test for returns a list of subnets to which the host belongs
        """
        with patch.dict(
            network.__utils__, {"network.subnets": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.subnets(), {})

    def test_in_subnet(self):
        """
        Test for returns True if host is within specified
         subnet, otherwise False.
        """
        with patch.dict(
            network.__utils__, {"network.in_subnet": MagicMock(return_value={})}
        ):
            self.assertDictEqual(network.in_subnet("iface"), {})

    def test_ip_addrs(self):
        """
        Test for returns a list of IPv4 addresses assigned to the host.
        """
        with patch.dict(
            network.__utils__,
            {
                "network.ip_addrs": MagicMock(return_value=["0.0.0.0"]),
                "network.in_subnet": MagicMock(return_value=True),
            },
        ):
            self.assertListEqual(
                network.ip_addrs("interface", "include_loopback", "cidr"), ["0.0.0.0"]
            )
            self.assertListEqual(
                network.ip_addrs("interface", "include_loopback"), ["0.0.0.0"]
            )

    def test_ip_addrs6(self):
        """
        Test for returns a list of IPv6 addresses assigned to the host.
        """
        with patch.dict(
            network.__utils__, {"network.ip_addrs6": MagicMock(return_value=["A"])}
        ):
            self.assertListEqual(network.ip_addrs6("int", "include"), ["A"])

    def test_get_hostname(self):
        """
        Test for Get hostname
        """
        with patch.object(socket, "gethostname", return_value="A"):
            self.assertEqual(network.get_hostname(), "A")

    def test_mod_hostname(self):
        """
        Test for Modify hostname
        """
        self.assertFalse(network.mod_hostname(None))
        file_d = "\n".join(["#", "A B C D,E,F G H"])

        with patch.dict(
            network.__utils__,
            {
                "path.which": MagicMock(return_value="hostname"),
                "files.fopen": mock_open(read_data=file_d),
            },
        ), patch.dict(
            network.__salt__, {"cmd.run": MagicMock(return_value=None)}
        ), patch.dict(
            network.__grains__, {"os_family": "A"}
        ):
            self.assertTrue(network.mod_hostname("hostname"))

    def test_mod_hostname_quoted(self):
        """
        Test for correctly quoted hostname on rh-style distro
        """

        fopen_mock = mock_open(
            read_data={
                "/etc/hosts": "\n".join(
                    ["127.0.0.1 localhost.localdomain", "127.0.0.2 undef"]
                ),
                "/etc/sysconfig/network": "\n".join(
                    ["NETWORKING=yes", 'HOSTNAME="undef"']
                ),
            }
        )

        with patch.dict(network.__grains__, {"os_family": "RedHat"}), patch.dict(
            network.__salt__, {"cmd.run": MagicMock(return_value=None)}
        ), patch("socket.getfqdn", MagicMock(return_value="undef")), patch.dict(
            network.__utils__,
            {
                "path.which": MagicMock(return_value="hostname"),
                "files.fopen": fopen_mock,
            },
        ):
            self.assertTrue(network.mod_hostname("hostname"))
            assert (
                fopen_mock.filehandles["/etc/sysconfig/network"][1].write_calls[1]
                == 'HOSTNAME="hostname"\n'
            )

    def test_mod_hostname_unquoted(self):
        """
        Test for correctly unquoted hostname on rh-style distro
        """

        fopen_mock = mock_open(
            read_data={
                "/etc/hosts": "\n".join(
                    ["127.0.0.1 localhost.localdomain", "127.0.0.2 undef"]
                ),
                "/etc/sysconfig/network": "\n".join(
                    ["NETWORKING=yes", "HOSTNAME=undef"]
                ),
            }
        )

        with patch.dict(network.__grains__, {"os_family": "RedHat"}), patch.dict(
            network.__salt__, {"cmd.run": MagicMock(return_value=None)}
        ), patch("socket.getfqdn", MagicMock(return_value="undef")), patch.dict(
            network.__utils__,
            {
                "path.which": MagicMock(return_value="hostname"),
                "files.fopen": fopen_mock,
            },
        ):
            self.assertTrue(network.mod_hostname("hostname"))
            assert (
                fopen_mock.filehandles["/etc/sysconfig/network"][1].write_calls[1]
                == "HOSTNAME=hostname\n"
            )

    def test_connect(self):
        """
        Test for Test connectivity to a host using a particular
        port from the minion.
        """
        with patch("socket.socket") as mock_socket:
            self.assertDictEqual(
                network.connect(False, "port"),
                {"comment": "Required argument, host, is missing.", "result": False},
            )

            self.assertDictEqual(
                network.connect("host", False),
                {"comment": "Required argument, port, is missing.", "result": False},
            )

            ret = "Unable to connect to host (0) on tcp port port"
            mock_socket.side_effect = Exception("foo")
            with patch.dict(
                network.__utils__,
                {"network.sanitize_host": MagicMock(return_value="A")},
            ):
                with patch.object(
                    socket,
                    "getaddrinfo",
                    return_value=[["ipv4", "A", 6, "B", "0.0.0.0"]],
                ):
                    self.assertDictEqual(
                        network.connect("host", "port"),
                        {"comment": ret, "result": False},
                    )

            ret = "Successfully connected to host (0) on tcp port port"
            mock_socket.side_effect = MagicMock()
            mock_socket.settimeout().return_value = None
            mock_socket.connect().return_value = None
            mock_socket.shutdown().return_value = None
            with patch.dict(
                network.__utils__,
                {"network.sanitize_host": MagicMock(return_value="A")},
            ):
                with patch.object(
                    socket,
                    "getaddrinfo",
                    return_value=[["ipv4", "A", 6, "B", "0.0.0.0"]],
                ):
                    self.assertDictEqual(
                        network.connect("host", "port"),
                        {"comment": ret, "result": True},
                    )

    @skipIf(not bool(ipaddress), "unable to import 'ipaddress'")
    def test_is_private(self):
        """
        Test for Check if the given IP address is a private address
        """
        with patch.object(ipaddress.IPv4Address, "is_private", return_value=True):
            self.assertTrue(network.is_private("0.0.0.0"))
        with patch.object(ipaddress.IPv6Address, "is_private", return_value=True):
            self.assertTrue(network.is_private("::1"))

    @skipIf(not bool(ipaddress), "unable to import 'ipaddress'")
    def test_is_loopback(self):
        """
        Test for Check if the given IP address is a loopback address
        """
        with patch.object(ipaddress.IPv4Address, "is_loopback", return_value=True):
            self.assertTrue(network.is_loopback("127.0.0.1"))
        with patch.object(ipaddress.IPv6Address, "is_loopback", return_value=True):
            self.assertTrue(network.is_loopback("::1"))

    def test_get_bufsize(self):
        """
        Test for return network buffer sizes as a dict
        """
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.object(os.path, "exists", return_value=True):
                with patch.object(
                    network, "_get_bufsize_linux", return_value={"size": 1}
                ):
                    self.assertDictEqual(network.get_bufsize("iface"), {"size": 1})

        with patch.dict(network.__grains__, {"kernel": "A"}):
            self.assertDictEqual(network.get_bufsize("iface"), {})

    def test_mod_bufsize(self):
        """
        Test for Modify network interface buffers (currently linux only)
        """
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.object(os.path, "exists", return_value=True):
                with patch.object(
                    network, "_mod_bufsize_linux", return_value={"size": 1}
                ):
                    self.assertDictEqual(network.mod_bufsize("iface"), {"size": 1})

        with patch.dict(network.__grains__, {"kernel": "A"}):
            self.assertFalse(network.mod_bufsize("iface"))

    def test_routes(self):
        """
        Test for return currently configured routes from routing table
        """
        self.assertRaises(CommandExecutionError, network.routes, "family")

        with patch.dict(network.__grains__, {"kernel": "A", "os": "B"}):
            self.assertRaises(CommandExecutionError, network.routes, "inet")

        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.object(
                network,
                "_netstat_route_linux",
                side_effect=["A", [{"addr_family": "inet"}]],
            ):
                with patch.object(
                    network,
                    "_ip_route_linux",
                    side_effect=["A", [{"addr_family": "inet"}]],
                ):
                    self.assertEqual(network.routes(None), "A")

                    self.assertListEqual(
                        network.routes("inet"), [{"addr_family": "inet"}]
                    )

    def test_default_route(self):
        """
        Test for return default route(s) from routing table
        """
        self.assertRaises(CommandExecutionError, network.default_route, "family")

        with patch.object(
            network,
            "routes",
            side_effect=[[{"addr_family": "inet"}, {"destination": "A"}], []],
        ):
            with patch.dict(network.__grains__, {"kernel": "A", "os": "B"}):
                self.assertRaises(CommandExecutionError, network.default_route, "inet")

            with patch.dict(network.__grains__, {"kernel": "Linux"}):
                self.assertListEqual(network.default_route("inet"), [])

    def test_default_route_ipv6(self):
        """
        Test for return default route(s) from routing table for IPv6
        Additionally tests that multicast, anycast, etc. do not throw errors
        """
        mock_iproute_ipv4 = """default via 192.168.0.1 dev enx3c18a040229d proto dhcp metric 100
default via 192.168.0.1 dev wlp59s0 proto dhcp metric 600
3.15.90.221 via 10.16.119.224 dev gpd0
3.18.18.213 via 10.16.119.224 dev gpd0
10.0.0.0/8 via 10.16.119.224 dev gpd0
10.1.0.0/16 via 10.12.240.1 dev tun0
10.2.0.0/16 via 10.12.240.1 dev tun0
10.12.0.0/16 via 10.12.240.1 dev tun0
10.12.240.0/20 dev tun0 proto kernel scope link src 10.12.240.2
10.14.0.0/16 via 10.12.240.1 dev tun0
10.16.0.0/16 via 10.12.240.1 dev tun0
10.16.188.201 via 10.16.119.224 dev gpd0
10.16.188.202 via 10.16.119.224 dev gpd0
10.27.0.0/16 via 10.12.240.1 dev tun0
52.14.149.204 via 10.16.119.224 dev gpd0
52.14.159.171 via 10.16.119.224 dev gpd0
52.14.249.61 via 10.16.119.224 dev gpd0
52.15.65.251 via 10.16.119.224 dev gpd0
54.70.229.135 via 10.16.119.224 dev gpd0
54.71.37.253 via 10.12.240.1 dev tun0
54.189.240.227 via 10.16.119.224 dev gpd0
66.170.96.2 via 192.168.0.1 dev enx3c18a040229d
80.169.184.191 via 10.16.119.224 dev gpd0
107.154.251.105 via 10.16.119.224 dev gpd0
168.61.48.213 via 10.16.119.224 dev gpd0
169.254.0.0/16 dev enx3c18a040229d scope link metric 1000
172.17.0.0/16 dev docker0 proto kernel scope link src 172.17.0.1 linkdown
172.30.0.0/16 via 10.12.240.1 dev tun0
184.169.136.236 via 10.16.119.224 dev gpd0
191.237.22.167 via 10.16.119.224 dev gpd0
192.30.68.16 via 10.16.119.224 dev gpd0
192.30.71.16 via 10.16.119.224 dev gpd0
192.30.71.71 via 10.16.119.224 dev gpd0
192.168.0.0/24 dev enx3c18a040229d proto kernel scope link src 192.168.0.99 metric 100
192.168.0.0/24 dev wlp59s0 proto kernel scope link src 192.168.0.99 metric 600
192.240.157.233 via 10.16.119.224 dev gpd0
206.80.50.33 via 10.16.119.224 dev gpd0
209.34.94.97 via 10.16.119.224 dev gpd0
unreachable should ignore this 
"""
        mock_iproute_ipv6 = """::1 dev lo proto kernel metric 256 pref medium
2060:123:4069::10 dev enp5s0 proto kernel metric 100 pref medium
2060:123:4069::68 dev wlp3s0 proto kernel metric 600 pref medium
2060:123:4069::15:0/112 dev virbr0 proto kernel metric 256 pref medium
2060:123:4069::/64 dev enp5s0 proto ra metric 100 pref medium
2060:123:4069::/64 dev wlp3s0 proto ra metric 600 pref medium
2602:ae13:dc4:1b00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:66:8300::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:a0:4d00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:508:3900::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:513:a200::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:769:2b00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:924:9700::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:9e1:6000::10:1 via fe80::222:15ff:fe3f:23fe dev enp5s0 proto static metric 100 pref medium
2602:ae14:9e1:6080::10:1 dev tun0 proto kernel metric 50 pref medium
2602:ae14:9e1:6080::10:1 dev tun0 proto kernel metric 256 pref medium
2602:ae14:9e1:6080::10:1001 dev tun0 proto kernel metric 50 pref medium
2602:ae14:9e1:6000::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:cc1:fa00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:cd0:5b00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2602:ae14:d5f:b400::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2a34:d014:1d3:5d00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
2a34:d014:919:bb00::/56 via 2602:ae14:9e1:6080::10:1 dev tun0 proto static metric 50 pref medium
fd0d:3ed3:cb42:1::/64 dev enp5s0 proto ra metric 100 pref medium
fd0d:3ed3:cb42:1::/64 dev wlp3s0 proto ra metric 600 pref medium
fe80::222:15ff:fe3f:23fe dev enp5s0 proto static metric 100 pref medium
fe80::/64 dev enp5s0 proto kernel metric 100 pref medium
fe80::/64 dev virbr0 proto kernel metric 256 pref medium
fe80::/64 dev vnet2 proto kernel metric 256 pref medium
fe80::/64 dev docker0 proto kernel metric 256 linkdown pref medium
fe80::/64 dev vpn0 proto kernel metric 256 pref medium
fe80::/64 dev wlp3s0 proto kernel metric 600 pref medium
default via fe80::222:15ff:fe3f:23fe dev enp5s0 proto ra metric 100 pref medium
default via fe80::222:15ff:fe3f:23fe dev wlp3s0 proto ra metric 600 pref medium
local ::1 dev lo table local proto kernel metric 0 pref medium
anycast 2060:123:4069:: dev wlp3s0 table local proto kernel metric 0 pref medium
local 2060:123:4069::10 dev enp5s0 table local proto kernel metric 0 pref medium
local 2060:123:4069::68 dev wlp3s0 table local proto kernel metric 0 pref medium
anycast 2060:123:4069::15:0 dev virbr0 table local proto kernel metric 0 pref medium
local 2060:123:4069::15:1 dev virbr0 table local proto kernel metric 0 pref medium
local 2060:123:4069:0:f4d:7d09:358c:ce5 dev wlp3s0 table local proto kernel metric 0 pref medium
local 2060:123:4069:0:a089:c284:32a8:9536 dev enp5s0 table local proto kernel metric 0 pref medium
anycast 2602:ae14:9e1:6080::10:0 dev tun0 table local proto kernel metric 0 pref medium
local 2602:ae14:9e1:6080::10:1001 dev tun0 table local proto kernel metric 0 pref medium
anycast fd0d:3ed3:cb42:1:: dev wlp3s0 table local proto kernel metric 0 pref medium
local fd0d:3ed3:cb42:1:cffd:9b03:c50:6d2a dev wlp3s0 table local proto kernel metric 0 pref medium
local fd0d:3ed3:cb42:1:f00b:50ef:2143:36cf dev enp5s0 table local proto kernel metric 0 pref medium
anycast fe80:: dev virbr0 table local proto kernel metric 0 pref medium
anycast fe80:: dev vnet2 table local proto kernel metric 0 pref medium
anycast fe80:: dev docker0 table local proto kernel metric 0 pref medium
anycast fe80:: dev wlp3s0 table local proto kernel metric 0 pref medium
anycast fe80:: dev vpn0 table local proto kernel metric 0 pref medium
local fe80::42:bfff:fec9:f590 dev docker0 table local proto kernel metric 0 pref medium
local fe80::18b1:cf8e:49cc:a783 dev wlp3s0 table local proto kernel metric 0 pref medium
local fe80::5054:ff:fe55:9457 dev virbr0 table local proto kernel metric 0 pref medium
local fe80::d251:c2a7:f5c8:2778 dev enp5s0 table local proto kernel metric 0 pref medium
local fe80::df35:e22c:f7db:a892 dev vpn0 table local proto kernel metric 0 pref medium
local fe80::fc54:ff:fee6:9fef dev vnet2 table local proto kernel metric 0 pref medium
multicast ff00::/8 dev enp5s0 table local proto kernel metric 256 pref medium
multicast ff00::/8 dev virbr0 table local proto kernel metric 256 pref medium
multicast ff00::/8 dev vnet2 table local proto kernel metric 256 pref medium
multicast ff00::/8 dev docker0 table local proto kernel metric 256 linkdown pref medium
multicast ff00::/8 dev wlp3s0 table local proto kernel metric 256 pref medium
multicast ff00::/8 dev vpn0 table local proto kernel metric 256 pref medium
multicast ff00::/8 dev tun0 table local proto kernel metric 256 pref medium
unicast should ignore this 
broadcast cast should ignore this 
throw should ignore this 
unreachable should ignore this 
prohibit should ignore this 
blackhole should ignore this 
nat should ignore this 
"""

        self.assertRaises(CommandExecutionError, network.default_route, "family")

        with patch.object(
            network,
            "routes",
            side_effect=[[{"family": "inet6"}, {"destination": "A"}], []],
        ):
            with patch.dict(network.__grains__, {"kernel": "A", "os": "B"}):
                self.assertRaises(CommandExecutionError, network.default_route, "inet6")

        cmd_mock = MagicMock(side_effect=[mock_iproute_ipv4, mock_iproute_ipv6])
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.dict(
                network.__utils__, {"path.which": MagicMock(return_value=False)}
            ):
                with patch.dict(network.__salt__, {"cmd.run": cmd_mock}):
                    self.assertListEqual(
                        network.default_route("inet6"),
                        [
                            {
                                "addr_family": "inet6",
                                "destination": "::/0",
                                "gateway": "fe80::222:15ff:fe3f:23fe",
                                "netmask": "",
                                "flags": "UG",
                                "interface": "enp5s0",
                            },
                            {
                                "addr_family": "inet6",
                                "destination": "::/0",
                                "gateway": "fe80::222:15ff:fe3f:23fe",
                                "netmask": "",
                                "flags": "UG",
                                "interface": "wlp3s0",
                            },
                        ],
                    )

    def test_get_route(self):
        """
        Test for return output from get_route
        """
        mock_iproute = MagicMock(
            return_value="8.8.8.8 via 10.10.10.1 dev eth0 src 10.10.10.10 uid 0\ncache"
        )
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.dict(network.__salt__, {"cmd.run": mock_iproute}):
                expected = {
                    "interface": "eth0",
                    "source": "10.10.10.10",
                    "destination": "8.8.8.8",
                    "gateway": "10.10.10.1",
                }
                ret = network.get_route("8.8.8.8")
                self.assertEqual(ret, expected)

        mock_iproute = MagicMock(
            return_value=(
                "8.8.8.8 via 10.10.10.1 dev eth0.1 src 10.10.10.10 uid 0\ncache"
            )
        )
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.dict(network.__salt__, {"cmd.run": mock_iproute}):
                expected = {
                    "interface": "eth0.1",
                    "source": "10.10.10.10",
                    "destination": "8.8.8.8",
                    "gateway": "10.10.10.1",
                }
                ret = network.get_route("8.8.8.8")
                self.assertEqual(ret, expected)

        mock_iproute = MagicMock(
            return_value=(
                "8.8.8.8 via 10.10.10.1 dev eth0:1 src 10.10.10.10 uid 0\ncache"
            )
        )
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.dict(network.__salt__, {"cmd.run": mock_iproute}):
                expected = {
                    "interface": "eth0:1",
                    "source": "10.10.10.10",
                    "destination": "8.8.8.8",
                    "gateway": "10.10.10.1",
                }
                ret = network.get_route("8.8.8.8")
                self.assertEqual(ret, expected)

        mock_iproute = MagicMock(
            return_value=(
                "8.8.8.8 via 10.10.10.1 dev lan-br0 src 10.10.10.10 uid 0\ncache"
            )
        )
        with patch.dict(network.__grains__, {"kernel": "Linux"}):
            with patch.dict(network.__salt__, {"cmd.run": mock_iproute}):
                expected = {
                    "interface": "lan-br0",
                    "source": "10.10.10.10",
                    "destination": "8.8.8.8",
                    "gateway": "10.10.10.1",
                }
                ret = network.get_route("8.8.8.8")
                self.assertEqual(ret, expected)
