"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import socket
import warnings

import pytest

import salt.modules.win_network as win_network
import salt.utils.network
from tests.support.mock import MagicMock, Mock, patch

try:
    import wmi

    HAS_WMI = True
except ImportError:
    HAS_WMI = False


class Mockwmi:
    """
    Mock wmi class
    """

    NetConnectionID = "Ethernet"

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

        class Com:
            """
            Mock Com method
            """

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False


@pytest.fixture
def configure_loader_modules():
    return {win_network: {}}


def test_ping():
    """
    Test if it performs a ping to a host.
    """
    mock = MagicMock(return_value=True)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.ping("127.0.0.1")


def test_netstat():
    """
    Test if it return information on open ports and states
    """
    ret = (
        "  Proto  Local Address    Foreign Address    State    PID\n"
        "  TCP    127.0.0.1:1434    0.0.0.0:0    LISTENING    1728\n"
        "  UDP    127.0.0.1:1900    *:*        4240"
    )
    mock = MagicMock(return_value=ret)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.netstat() == [
            {
                "local-address": "127.0.0.1:1434",
                "program": "1728",
                "proto": "TCP",
                "remote-address": "0.0.0.0:0",
                "state": "LISTENING",
            },
            {
                "local-address": "127.0.0.1:1900",
                "program": "4240",
                "proto": "UDP",
                "remote-address": "*:*",
                "state": None,
            },
        ]


def test_traceroute():
    """
    Test if it performs a traceroute to a 3rd party host
    """
    ret = (
        "  1     1 ms    <1 ms    <1 ms  172.27.104.1\n"
        "  2     1 ms    <1 ms     1 ms  121.242.35.1.s[121.242.35.1]\n"
        "  3     3 ms     2 ms     2 ms  121.242.4.53.s[121.242.4.53]\n"
    )
    mock = MagicMock(return_value=ret)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.traceroute("google.com") == [
            {
                "count": "1",
                "hostname": None,
                "ip": "172.27.104.1",
                "ms1": "1",
                "ms2": "<1",
                "ms3": "<1",
            },
            {
                "count": "2",
                "hostname": None,
                "ip": "121.242.35.1.s[121.242.35.1]",
                "ms1": "1",
                "ms2": "<1",
                "ms3": "1",
            },
            {
                "count": "3",
                "hostname": None,
                "ip": "121.242.4.53.s[121.242.4.53]",
                "ms1": "3",
                "ms2": "2",
                "ms3": "2",
            },
        ]


def test_nslookup():
    """
    Test if it query DNS for information about a domain or ip address
    """
    ret = (
        "Server:  ct-dc-3-2.cybage.com\n"
        "Address:  172.27.172.12\n"
        "Non-authoritative answer:\n"
        "Name:    google.com\n"
        "Addresses:  2404:6800:4007:806::200e\n"
        "216.58.196.110\n"
    )
    mock = MagicMock(return_value=ret)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.nslookup("google.com") == [
            {"Server": "ct-dc-3-2.cybage.com"},
            {"Address": "172.27.172.12"},
            {"Name": "google.com"},
            {"Addresses": ["2404:6800:4007:806::200e", "216.58.196.110"]},
        ]


def test_dig():
    """
    Test if it performs a DNS lookup with dig
    """
    mock = MagicMock(return_value=True)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.dig("google.com")


@pytest.mark.skipif(HAS_WMI is False, reason="WMI is available only on Windows")
def test_interfaces_names():
    """
    Test if it return a list of all the interfaces names
    """
    WMI = Mock()
    WMI.Win32_NetworkAdapter = MagicMock(return_value=Mockwmi)
    with patch("salt.utils.winapi.Com", MagicMock()), patch.object(
        WMI, "Win32_NetworkAdapter", return_value=[Mockwmi()]
    ), patch("salt.utils", Mockwinapi), patch.object(
        wmi, "WMI", Mock(return_value=WMI)
    ):
        assert win_network.interfaces_names() == ["Ethernet"]


def test_interfaces():
    """
    Test if it return information about all the interfaces on the minion
    """
    with patch.object(
        salt.utils.network, "win_interfaces", MagicMock(return_value=True)
    ):
        assert win_network.interfaces()


def test_hw_addr():
    """
    Test if it return the hardware address (a.k.a. MAC address)
    for a given interface
    """
    with patch.object(
        salt.utils.network, "hw_addr", MagicMock(return_value="Ethernet")
    ):
        assert win_network.hw_addr("Ethernet") == "Ethernet"


def test_subnets():
    """
    Test if it returns a list of subnets to which the host belongs
    """
    with patch.object(
        salt.utils.network, "subnets", MagicMock(return_value="10.1.1.0/24")
    ):
        assert win_network.subnets() == "10.1.1.0/24"


def test_in_subnet():
    """
    Test if it returns True if host is within specified subnet,
    otherwise False
    """
    with patch.object(salt.utils.network, "in_subnet", MagicMock(return_value=True)):
        assert win_network.in_subnet("10.1.1.0/16")


def test_get_route():
    """
    Test if it return information on open ports and states
    """
    ret = (
        "\n\n"
        "IPAddress         : 10.0.0.15\n"
        "InterfaceIndex    : 3\n"
        "InterfaceAlias    : Wi-Fi\n"
        "AddressFamily     : IPv4\n"
        "Type              : Unicast\n"
        "PrefixLength      : 24\n"
        "PrefixOrigin      : Dhcp\n"
        "SuffixOrigin      : Dhcp\n"
        "AddressState      : Preferred\n"
        "ValidLifetime     : 6.17:52:39\n"
        "PreferredLifetime : 6.17:52:39\n"
        "SkipAsSource      : False\n"
        "PolicyStore       : ActiveStore\n"
        "\n\n"
        "Caption            :\n"
        "Description        :\n"
        "ElementName        :\n"
        "InstanceID         : :8:8:8:9:55=55;:8;8;:8;55;\n"
        "AdminDistance      :\n"
        "DestinationAddress :\n"
        "IsStatic           :\n"
        "RouteMetric        : 0\n"
        "TypeOfRoute        : 3\n"
        "AddressFamily      : IPv4\n"
        "CompartmentId      : 1\n"
        "DestinationPrefix  : 0.0.0.0/0\n"
        "InterfaceAlias     : Wi-Fi\n"
        "InterfaceIndex     : 3\n"
        "NextHop            : 10.0.0.1\n"
        "PreferredLifetime  : 6.23:14:43\n"
        "Protocol           : NetMgmt\n"
        "Publish            : No\n"
        "Store              : ActiveStore\n"
        "ValidLifetime      : 6.23:14:43\n"
        "PSComputerName     :\n"
        "ifIndex            : 3"
    )
    mock = MagicMock(return_value=ret)
    with patch.dict(win_network.__salt__, {"cmd.run": mock}):
        assert win_network.get_route("192.0.0.8") == {
            "destination": "192.0.0.8",
            "gateway": "10.0.0.1",
            "interface": "Wi-Fi",
            "source": "10.0.0.15",
        }


def test_connect_53371():
    """
    Test that UnboundLocalError is not thrown on socket.gaierror
    as reported in #53371
    """
    with patch(
        "socket.getaddrinfo",
        autospec=True,
        side_effect=socket.gaierror("[Errno 11004] getaddrinfo failed"),
    ):
        rtn = win_network.connect("test-server", 80)
        assert rtn
        assert not rtn["result"]
        assert (
            rtn["comment"]
            == "Unable to connect to test-server (unknown) on tcp port 80"
        )


def test_arp_expand():
    """
    arp(expand=True) maps Get-NetNeighbor objects to entry dicts, skipping
    unresolved neighbours and the static multicast/broadcast
    pseudo-neighbours Windows keeps in its cache, normalizing MAC addresses
    to the lowercase colon-separated form and states to the uppercase NUD
    vocabulary used by the Unix network module.
    """
    neighbors = [
        {
            "IPAddress": "203.0.113.1",
            "LinkLayerAddress": "00-00-5E-00-53-01",
            "InterfaceAlias": "Ethernet0",
            "State": "Reachable",
        },
        {
            "IPAddress": "203.0.113.9",
            "LinkLayerAddress": "00-00-5E-00-53-01",
            "InterfaceAlias": "Ethernet0",
            "State": "Stale",
        },
        {
            "IPAddress": "203.0.113.66",
            "LinkLayerAddress": "",
            "InterfaceAlias": "Ethernet0",
            "State": "Unreachable",
        },
        {
            "IPAddress": "224.0.0.22",
            "LinkLayerAddress": "01-00-5E-00-00-16",
            "InterfaceAlias": "Ethernet0",
            "State": "Permanent",
        },
        {
            "IPAddress": "255.255.255.255",
            "LinkLayerAddress": "FF-FF-FF-FF-FF-FF",
            "InterfaceAlias": "Ethernet0",
            "State": "Permanent",
        },
        {
            # Subnet-directed broadcast: a real Windows Server 2025 entry. It is
            # neither multicast nor the limited broadcast address, so it can
            # only be recognized by its broadcast link-layer address.
            "IPAddress": "203.0.113.255",
            "LinkLayerAddress": "FF-FF-FF-FF-FF-FF",
            "InterfaceAlias": "Ethernet0",
            "State": "Permanent",
        },
    ]
    mock_powershell = MagicMock(return_value=neighbors)
    with patch.dict(win_network.__salt__, {"cmd.powershell": mock_powershell}):
        assert win_network.arp(expand=True) == [
            {
                "ip": "203.0.113.1",
                "mac": "00:00:5e:00:53:01",
                "dev": "Ethernet0",
                "state": "REACHABLE",
            },
            {
                "ip": "203.0.113.9",
                "mac": "00:00:5e:00:53:01",
                "dev": "Ethernet0",
                "state": "STALE",
            },
        ]
    assert "-AddressFamily IPv4" in mock_powershell.call_args[0][0]


def test_arp_default_warns_and_collapses():
    """
    Calling arp() without expand emits the deprecation warning and returns
    the legacy flat mapping, in which entries sharing a MAC collapse to the
    last one returned.
    """
    neighbors = [
        {
            "IPAddress": "203.0.113.1",
            "LinkLayerAddress": "00-00-5E-00-53-01",
            "InterfaceAlias": "Ethernet0",
            "State": "Reachable",
        },
        {
            "IPAddress": "203.0.113.9",
            "LinkLayerAddress": "00-00-5E-00-53-01",
            "InterfaceAlias": "Ethernet0",
            "State": "Stale",
        },
    ]
    with patch.dict(
        win_network.__salt__, {"cmd.powershell": MagicMock(return_value=neighbors)}
    ):
        with pytest.warns(DeprecationWarning, match="network.arp"):
            result = win_network.arp()
    assert result == {"00:00:5e:00:53:01": "203.0.113.9"}


def test_ip_neighs_single_neighbor():
    """
    A single neighbour serializes to a bare object instead of a list;
    ip_neighs handles both.
    """
    neighbor = {
        "IPAddress": "203.0.113.1",
        "LinkLayerAddress": "00-00-5E-00-53-01",
        "InterfaceAlias": "Ethernet0",
        "State": "Reachable",
    }
    with patch.dict(
        win_network.__salt__, {"cmd.powershell": MagicMock(return_value=neighbor)}
    ):
        assert win_network.ip_neighs(expand=False) == {
            "00:00:5e:00:53:01": "203.0.113.1"
        }


def test_ip_neighs6_expand():
    """
    ip_neighs6 queries the IPv6 address family and preserves the link-local
    and global addresses a host holds on the same MAC, which the legacy flat
    mapping collapses.
    """
    neighbors = [
        {
            "IPAddress": "2001:db8::52",
            "LinkLayerAddress": "00-00-5E-00-53-52",
            "InterfaceAlias": "Ethernet0",
            "State": "Reachable",
        },
        {
            "IPAddress": "fe80::200:5eff:fe00:5352",
            "LinkLayerAddress": "00-00-5E-00-53-52",
            "InterfaceAlias": "Ethernet0",
            "State": "Stale",
        },
        {
            "IPAddress": "ff02::16",
            "LinkLayerAddress": "33-33-00-00-00-16",
            "InterfaceAlias": "Ethernet0",
            "State": "Permanent",
        },
    ]
    mock_powershell = MagicMock(return_value=neighbors)
    with patch.dict(win_network.__salt__, {"cmd.powershell": mock_powershell}):
        expanded = win_network.ip_neighs6(expand=True)
        assert expanded == [
            {
                "ip": "2001:db8::52",
                "mac": "00:00:5e:00:53:52",
                "dev": "Ethernet0",
                "state": "REACHABLE",
            },
            {
                "ip": "fe80::200:5eff:fe00:5352",
                "mac": "00:00:5e:00:53:52",
                "dev": "Ethernet0",
                "state": "STALE",
            },
        ]
        # The legacy shape drops one of the two addresses.
        assert len(win_network.ip_neighs6(expand=False)) == 1
    assert "-AddressFamily IPv6" in mock_powershell.call_args[0][0]


def test_ip_neighs_expand_false_does_not_warn():
    """
    Passing expand=False explicitly keeps the legacy shape without emitting
    the deprecation warning.
    """
    neighbor = {
        "IPAddress": "203.0.113.1",
        "LinkLayerAddress": "00-00-5E-00-53-01",
        "InterfaceAlias": "Ethernet0",
        "State": "Reachable",
    }
    with patch.dict(
        win_network.__salt__, {"cmd.powershell": MagicMock(return_value=neighbor)}
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = win_network.ip_neighs(expand=False)
    assert result == {"00:00:5e:00:53:01": "203.0.113.1"}
