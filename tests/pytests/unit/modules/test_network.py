import logging
import os.path
import shutil
import socket
import threading

import pytest

import salt.config
import salt.modules.network as networkmod
import salt.utils.path
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules(minion_opts):
    ## return {networkmod: {}}
    utils = salt.loader.utils(
        minion_opts, whitelist=["network", "path", "platform", "stringutils"]
    )
    return {
        networkmod: {"__utils__": utils},
    }


@pytest.fixture
def socket_errors():
    # Not sure what kind of errors could be returned by getfqdn or
    # gethostbyaddr, but we have reports that thread leaks are happening
    with patch("socket.getfqdn", autospec=True, side_effect=Exception), patch(
        "socket.gethostbyaddr", autospec=True, side_effect=Exception
    ):
        yield


@pytest.fixture
def fake_fqdn():
    fqdn = "some.sample.fqdn.example.com"
    # Since we're mocking getfqdn it doesn't matter what gethostbyaddr returns.
    # At least as long as it's the right shape (i.e. has a [0] element)
    with patch("socket.getfqdn", autospec=True, return_value=fqdn), patch(
        "socket.gethostbyaddr",
        autospec=True,
        return_value=("fnord", "fnord fnord"),
    ):
        yield fqdn


@pytest.fixture
def fake_ips():
    with patch(
        "salt.utils.network.ip_addrs",
        autospec=True,
        return_value=[
            "203.0.113.1",
            "203.0.113.3",
            "203.0.113.6",
            "203.0.113.25",
            "203.0.113.82",
        ],
    ), patch("salt.utils.network.ip_addrs6", autospec=True, return_value=[]):
        yield


def test_when_errors_happen_looking_up_fqdns_threads_should_not_leak(socket_errors):
    before_threads = threading.active_count()
    networkmod.fqdns()
    after_threads = threading.active_count()
    assert (
        before_threads == after_threads
    ), "Difference in thread count means the thread pool is not correctly cleaning up."


def test_when_no_errors_happen_looking_up_fqdns_threads_should_not_leak(
    fake_fqdn, fake_ips
):
    before_threads = threading.active_count()
    networkmod.fqdns()
    after_threads = threading.active_count()
    assert (
        before_threads == after_threads
    ), "Difference in thread count means the thread pool is not correctly cleaning up."


def test_when_no_errors_happen_looking_up_fqdns_results_from_fqdns_lookup_should_be_returned(
    fake_fqdn, fake_ips
):
    actual_fqdn = networkmod.fqdns()
    # Even though we have two fake IPs they magically resolve to the same fqdn
    assert actual_fqdn == {"fqdns": [fake_fqdn]}


def test_fqdns_should_return_sorted_unique_domains(fake_ips):
    # These need to match the number of ips in fake_ips
    fake_domains = [
        "z.example.com",
        "z.example.com",
        "c.example.com",
        "a.example.com",
    ]
    with patch("socket.getfqdn", autospec=True, side_effect=fake_domains), patch(
        "socket.gethostbyaddr",
        autospec=True,
        return_value=("fnord", "fnord fnord"),
    ):
        actual_fqdns = networkmod.fqdns()
        assert actual_fqdns == {
            "fqdns": ["a.example.com", "c.example.com", "z.example.com"]
        }


def test___virtual__is_windows_true():
    with patch("salt.utils.platform.is_windows", return_value=True):
        result = networkmod.__virtual__()
        expected = (
            False,
            "The network execution module cannot be loaded on Windows: use win_network"
            " instead.",
        )
        assert result == expected


def test___virtual__is_windows_false():
    with patch("salt.utils.platform.is_windows", return_value=False):
        result = networkmod.__virtual__()
        assert result


def test_wol_bad_mac():
    """
    tests network.wol with bad mac
    """
    bad_mac = "31337"
    pytest.raises(ValueError, networkmod.wol, bad_mac)


def test_wol_success():
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
        assert networkmod.wol(mac, bcast)


def test_ping():
    """
    Test for Performs a ping to a host
    """
    with patch.dict(
        networkmod.__utils__, {"network.sanitize_host": MagicMock(return_value="A")}
    ):
        mock_all = MagicMock(side_effect=[{"retcode": 1}, {"retcode": 0}])
        with patch.dict(networkmod.__salt__, {"cmd.run_all": mock_all}):
            assert not networkmod.ping("host", return_boolean=True)
            assert networkmod.ping("host", return_boolean=True)

        with patch.dict(networkmod.__salt__, {"cmd.run": MagicMock(return_value="A")}):
            assert networkmod.ping("host") == "A"


def test_netstat():
    """
    Test for return information on open ports and states
    """
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.object(networkmod, "_netstat_linux", return_value="A"):
            with patch.object(networkmod, "_ss_linux", return_value="A"):
                assert networkmod.netstat() == "A"

    with patch.dict(networkmod.__grains__, {"kernel": "OpenBSD"}):
        with patch.object(networkmod, "_netstat_bsd", return_value="A"):
            assert networkmod.netstat() == "A"

    with patch.dict(networkmod.__grains__, {"kernel": "A"}):
        pytest.raises(CommandExecutionError, networkmod.netstat)


def test_active_tcp():
    """
    Test for return a dict containing information on all
     of the running TCP connections
    """
    with patch.dict(
        networkmod.__utils__, {"network.active_tcp": MagicMock(return_value="A")}
    ):
        with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
            assert networkmod.active_tcp() == "A"


def test_traceroute():
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
        with patch.dict(networkmod.__salt__, {"cmd.run": MagicMock(return_value="")}):
            assert networkmod.traceroute("gentoo.org") == []

        with patch.dict(
            networkmod.__utils__,
            {"network.sanitize_host": MagicMock(return_value="gentoo.org")},
        ):
            with patch.dict(
                networkmod.__salt__, {"cmd.run": MagicMock(return_value="")}
            ):
                assert networkmod.traceroute("gentoo.org") == []


def test_dig():
    """
    Test for Performs a DNS lookup with dig
    """
    with patch("salt.utils.path.which", MagicMock(return_value="dig")), patch.dict(
        networkmod.__utils__, {"network.sanitize_host": MagicMock(return_value="A")}
    ), patch.dict(networkmod.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert networkmod.dig("host") == "A"


def test_arp():
    """
    Test for return the arp table from the minion
    """
    with patch.dict(
        networkmod.__salt__,
        {"cmd.run": MagicMock(return_value="A,B,C,D\nE,F,G,H\n")},
    ), patch("salt.utils.path.which", MagicMock(return_value="")):
        assert networkmod.arp() == {}


def test_interfaces():
    """
    Test for return a dictionary of information about
     all the interfaces on the minion
    """
    with patch.dict(
        networkmod.__utils__, {"network.interfaces": MagicMock(return_value={})}
    ):
        assert networkmod.interfaces() == {}


def test_hw_addr():
    """
    Test for return the hardware address (a.k.a. MAC address)
     for a given interface
    """
    with patch.dict(
        networkmod.__utils__, {"network.hw_addr": MagicMock(return_value={})}
    ):
        assert networkmod.hw_addr("iface") == {}


def test_interface():
    """
    Test for return the inet address for a given interface
    """
    with patch.dict(
        networkmod.__utils__, {"network.interface": MagicMock(return_value={})}
    ):
        assert networkmod.interface("iface") == {}


def test_interface_ip():
    """
    Test for return the inet address for a given interface
    """
    with patch.dict(
        networkmod.__utils__, {"network.interface_ip": MagicMock(return_value={})}
    ):
        assert networkmod.interface_ip("iface") == {}


def test_subnets():
    """
    Test for returns a list of subnets to which the host belongs
    """
    with patch.dict(
        networkmod.__utils__, {"network.subnets": MagicMock(return_value={})}
    ):
        assert networkmod.subnets() == {}


def test_in_subnet():
    """
    Test for returns True if host is within specified
     subnet, otherwise False.
    """
    with patch.dict(
        networkmod.__utils__, {"network.in_subnet": MagicMock(return_value={})}
    ):
        assert networkmod.in_subnet("iface") == {}


def test_ip_addrs():
    """
    Test for returns a list of IPv4 addresses assigned to the host.
    """
    with patch.dict(
        networkmod.__utils__,
        {
            "network.ip_addrs": MagicMock(return_value=["0.0.0.0"]),
            "network.in_subnet": MagicMock(return_value=True),
        },
    ):
        assert networkmod.ip_addrs("interface", "include_loopback", "cidr") == [
            "0.0.0.0"
        ]
        assert networkmod.ip_addrs("interface", "include_loopback") == ["0.0.0.0"]


def test_ip_addrs6():
    """
    Test for returns a list of IPv6 addresses assigned to the host.
    """
    with patch.dict(
        networkmod.__utils__, {"network.ip_addrs6": MagicMock(return_value=["A"])}
    ):
        assert networkmod.ip_addrs6("int", "include") == ["A"]


def test_get_hostname():
    """
    Test for Get hostname
    """
    with patch.object(socket, "gethostname", return_value="A"):
        assert networkmod.get_hostname() == "A"


def test_mod_hostname():
    """
    Test for Modify hostname
    """
    assert not networkmod.mod_hostname(None)
    file_d = "\n".join(["#", "A B C D,E,F G H"])

    with patch.dict(
        networkmod.__utils__,
        {
            "path.which": MagicMock(return_value="hostname"),
            "files.fopen": mock_open(read_data=file_d),
        },
    ), patch.dict(
        networkmod.__salt__, {"cmd.run": MagicMock(return_value=None)}
    ), patch.dict(
        networkmod.__grains__, {"os_family": "A"}
    ):
        assert networkmod.mod_hostname("hostname")


def test_mod_hostname_quoted():
    """
    Test for correctly quoted hostname on rh-style distro
    """

    fopen_mock = mock_open(
        read_data={
            "/etc/hosts": "\n".join(
                ["127.0.0.1 localhost.localdomain", "127.0.0.2 undef"]
            ),
            "/etc/sysconfig/network": "\n".join(["NETWORKING=yes", 'HOSTNAME="undef"']),
        }
    )

    with patch.dict(networkmod.__grains__, {"os_family": "RedHat"}), patch.dict(
        networkmod.__salt__, {"cmd.run": MagicMock(return_value=None)}
    ), patch("socket.getfqdn", MagicMock(return_value="undef")), patch.dict(
        networkmod.__utils__,
        {
            "path.which": MagicMock(return_value="hostname"),
            "files.fopen": fopen_mock,
        },
    ):
        assert networkmod.mod_hostname("hostname")
        assert (
            fopen_mock.filehandles["/etc/sysconfig/network"][1].write_calls[1]
            == 'HOSTNAME="hostname"\n'
        )


def test_mod_hostname_unquoted():
    """
    Test for correctly unquoted hostname on rh-style distro
    """

    fopen_mock = mock_open(
        read_data={
            "/etc/hosts": "\n".join(
                ["127.0.0.1 localhost.localdomain", "127.0.0.2 undef"]
            ),
            "/etc/sysconfig/network": "\n".join(["NETWORKING=yes", "HOSTNAME=undef"]),
        }
    )

    with patch.dict(networkmod.__grains__, {"os_family": "RedHat"}), patch.dict(
        networkmod.__salt__, {"cmd.run": MagicMock(return_value=None)}
    ), patch("socket.getfqdn", MagicMock(return_value="undef")), patch.dict(
        networkmod.__utils__,
        {
            "path.which": MagicMock(return_value="hostname"),
            "files.fopen": fopen_mock,
        },
    ):
        assert networkmod.mod_hostname("hostname")
        assert (
            fopen_mock.filehandles["/etc/sysconfig/network"][1].write_calls[1]
            == "HOSTNAME=hostname\n"
        )


def test_connect():
    """
    Test for Test connectivity to a host using a particular
    port from the minion.
    """
    with patch("socket.socket") as mock_socket:
        assert networkmod.connect(False, "port") == {
            "comment": "Required argument, host, is missing.",
            "result": False,
        }
        assert networkmod.connect("host", False) == {
            "comment": "Required argument, port, is missing.",
            "result": False,
        }

        ret = "Unable to connect to host (0) on tcp port port"
        mock_socket.side_effect = Exception("foo")
        with patch.dict(
            networkmod.__utils__,
            {"network.sanitize_host": MagicMock(return_value="A")},
        ):
            with patch.object(
                socket,
                "getaddrinfo",
                return_value=[["ipv4", "A", 6, "B", "0.0.0.0"]],
            ):
                assert networkmod.connect("host", "port") == {
                    "comment": ret,
                    "result": False,
                }

        ret = "Successfully connected to host (0) on tcp port port"
        mock_socket.side_effect = MagicMock()
        mock_socket.settimeout().return_value = None
        mock_socket.connect().return_value = None
        mock_socket.shutdown().return_value = None
        with patch.dict(
            networkmod.__utils__,
            {"network.sanitize_host": MagicMock(return_value="A")},
        ):
            with patch.object(
                socket,
                "getaddrinfo",
                return_value=[["ipv4", "A", 6, "B", "0.0.0.0"]],
            ):
                assert networkmod.connect("host", "port") == {
                    "comment": ret,
                    "result": True,
                }


def test_is_private():
    """
    Test for Check if the given IP address is a private address
    """
    with patch.object(ipaddress.IPv4Address, "is_private", return_value=True):
        assert networkmod.is_private("0.0.0.0")
    with patch.object(ipaddress.IPv6Address, "is_private", return_value=True):
        assert networkmod.is_private("::1")


def test_is_loopback():
    """
    Test for Check if the given IP address is a loopback address
    """
    with patch.object(ipaddress.IPv4Address, "is_loopback", return_value=True):
        assert networkmod.is_loopback("127.0.0.1")
    with patch.object(ipaddress.IPv6Address, "is_loopback", return_value=True):
        assert networkmod.is_loopback("::1")


def test_get_bufsize():
    """
    Test for return network buffer sizes as a dict
    """
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.object(os.path, "exists", return_value=True):
            with patch.object(
                networkmod, "_get_bufsize_linux", return_value={"size": 1}
            ):
                assert networkmod.get_bufsize("iface") == {"size": 1}

    with patch.dict(networkmod.__grains__, {"kernel": "A"}):
        assert networkmod.get_bufsize("iface") == {}


def test_mod_bufsize():
    """
    Test for Modify network interface buffers (currently linux only)
    """
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.object(os.path, "exists", return_value=True):
            with patch.object(
                networkmod, "_mod_bufsize_linux", return_value={"size": 1}
            ):
                assert networkmod.mod_bufsize("iface") == {"size": 1}

    with patch.dict(networkmod.__grains__, {"kernel": "A"}):
        assert not networkmod.mod_bufsize("iface")


def test_routes():
    """
    Test for return currently configured routes from routing table
    """
    pytest.raises(CommandExecutionError, networkmod.routes, "family")

    with patch.dict(networkmod.__grains__, {"kernel": "A", "os": "B"}):
        pytest.raises(CommandExecutionError, networkmod.routes, "inet")

    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.object(
            networkmod,
            "_netstat_route_linux",
            side_effect=["A", [{"addr_family": "inet"}]],
        ):
            with patch.object(
                networkmod,
                "_ip_route_linux",
                side_effect=["A", [{"addr_family": "inet"}]],
            ):
                assert networkmod.routes(None) == "A"
                assert networkmod.routes("inet") == [{"addr_family": "inet"}]


def test_default_route():
    """
    Test for return default route(s) from routing table
    """
    pytest.raises(CommandExecutionError, networkmod.default_route, "family")

    with patch.object(
        networkmod,
        "routes",
        side_effect=[[{"addr_family": "inet"}, {"destination": "A"}], []],
    ):
        with patch.dict(networkmod.__grains__, {"kernel": "A", "os": "B"}):
            pytest.raises(CommandExecutionError, networkmod.default_route, "inet")

        with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
            assert networkmod.default_route("inet") == []


def test_default_route_ipv6():
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

    pytest.raises(CommandExecutionError, networkmod.default_route, "family")

    with patch.object(
        networkmod,
        "routes",
        side_effect=[[{"family": "inet6"}, {"destination": "A"}], []],
    ):
        with patch.dict(networkmod.__grains__, {"kernel": "A", "os": "B"}):
            pytest.raises(CommandExecutionError, networkmod.default_route, "inet6")

    cmd_mock = MagicMock(side_effect=[mock_iproute_ipv4, mock_iproute_ipv6])
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.dict(
            networkmod.__utils__, {"path.which": MagicMock(return_value=False)}
        ):
            with patch.dict(networkmod.__salt__, {"cmd.run": cmd_mock}):
                assert networkmod.default_route("inet6") == [
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
                ]


def test_get_route():
    """
    Test for return output from get_route
    """
    mock_iproute = MagicMock(
        return_value="8.8.8.8 via 10.10.10.1 dev eth0 src 10.10.10.10 uid 0\ncache"
    )
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.dict(networkmod.__salt__, {"cmd.run": mock_iproute}):
            expected = {
                "interface": "eth0",
                "source": "10.10.10.10",
                "destination": "8.8.8.8",
                "gateway": "10.10.10.1",
            }
            ret = networkmod.get_route("8.8.8.8")
            assert ret == expected

    mock_iproute = MagicMock(
        return_value=("8.8.8.8 via 10.10.10.1 dev eth0.1 src 10.10.10.10 uid 0\ncache")
    )
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.dict(networkmod.__salt__, {"cmd.run": mock_iproute}):
            expected = {
                "interface": "eth0.1",
                "source": "10.10.10.10",
                "destination": "8.8.8.8",
                "gateway": "10.10.10.1",
            }
            ret = networkmod.get_route("8.8.8.8")
            assert ret == expected

    mock_iproute = MagicMock(
        return_value=("8.8.8.8 via 10.10.10.1 dev eth0:1 src 10.10.10.10 uid 0\ncache")
    )
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.dict(networkmod.__salt__, {"cmd.run": mock_iproute}):
            expected = {
                "interface": "eth0:1",
                "source": "10.10.10.10",
                "destination": "8.8.8.8",
                "gateway": "10.10.10.1",
            }
            ret = networkmod.get_route("8.8.8.8")
            assert ret == expected

    mock_iproute = MagicMock(
        return_value=("8.8.8.8 via 10.10.10.1 dev lan-br0 src 10.10.10.10 uid 0\ncache")
    )
    with patch.dict(networkmod.__grains__, {"kernel": "Linux"}):
        with patch.dict(networkmod.__salt__, {"cmd.run": mock_iproute}):
            expected = {
                "interface": "lan-br0",
                "source": "10.10.10.10",
                "destination": "8.8.8.8",
                "gateway": "10.10.10.1",
            }
            ret = networkmod.get_route("8.8.8.8")
            assert ret == expected


@pytest.mark.skip_on_windows(reason="ip neigh not available in Windows")
def test_ip_neighs():
    """
    Test for return the ip neigh table for IPv4 addresses from the minion
    """
    mock_ipv4_neighbor = """192.168.0.67 dev enp0s3 lladdr b4:22:00:27:d4:75 STALE
192.168.0.107 dev enp0s3 lladdr 3c:18:a0:40:22:9d REACHABLE
192.168.0.103 dev enp0s3 lladdr d0:c2:4e:a0:dd:17 STALE
192.168.0.106 dev enp0s3 BAD
192.168.0.1 dev enp0s3 lladdr 9c:97:26:18:c4:1f DELAY
ff80::725:53ff:fe3d:10be dev eth1 BAD
fe80::825:63ff:fe2d:19be dev eth0 lladdr 0a:25:63:2d:19:be router STALE
    """
    expected = {
        "3c:18:a0:40:22:9d": "192.168.0.107",
        "9c:97:26:18:c4:1f": "192.168.0.1",
        "b4:22:00:27:d4:75": "192.168.0.67",
        "d0:c2:4e:a0:dd:17": "192.168.0.103",
    }

    with patch.dict(
        networkmod.__salt__, {"cmd.run": MagicMock(return_value=mock_ipv4_neighbor)}
    ):
        result = networkmod.ip_neighs()
        assert result == expected


@pytest.mark.skip_on_windows(reason="ip neigh not available in Windows")
def test_ip_neighs6():
    """
    Test for return the ip neigh table for IPv6 addresses from the minion
    """
    mock_ipv6_neighbor = """10.27.56.1 dev eth0 lladdr 0a:25:63:2d:19:be DELAY
192.168.0.103 dev enp0s3 lladdr d0:c2:4e:a0:dd:17 STALE
192.168.0.106 dev enp0s3 BAD
ff80::725:53ff:fe3d:10be dev eth1 BAD
fe80::825:63ff:fe2d:19be dev eth0 lladdr 0a:25:63:2d:19:be router STALE
    """
    expected = {"0a:25:63:2d:19:be": "fe80::825:63ff:fe2d:19be"}

    with patch.dict(
        networkmod.__salt__, {"cmd.run": MagicMock(return_value=mock_ipv6_neighbor)}
    ):
        result = networkmod.ip_neighs6()
        assert result == expected
