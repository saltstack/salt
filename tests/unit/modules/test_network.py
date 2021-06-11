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
            "The network execution module cannot be loaded on Windows: use win_network instead.",
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
            return_value="8.8.8.8 via 10.10.10.1 dev eth0.1 src 10.10.10.10 uid 0\ncache"
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
            return_value="8.8.8.8 via 10.10.10.1 dev eth0:1 src 10.10.10.10 uid 0\ncache"
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
            return_value="8.8.8.8 via 10.10.10.1 dev lan-br0 src 10.10.10.10 uid 0\ncache"
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
