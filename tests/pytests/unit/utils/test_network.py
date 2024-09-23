import logging
import socket
import textwrap

import pytest

import salt.exceptions
import salt.utils.network
import salt.utils.network as network
import salt.utils.platform
from salt._compat import ipaddress
from tests.support.mock import MagicMock, create_autospec, mock_open, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


log = logging.getLogger(__name__)

LINUX = """\
eth0      Link encap:Ethernet  HWaddr e0:3f:49:85:6a:af
          inet addr:10.10.10.56  Bcast:10.10.10.255  Mask:255.255.252.0
          inet6 addr: fe80::e23f:49ff:fe85:6aaf/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:643363 errors:0 dropped:0 overruns:0 frame:0
          TX packets:196539 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:386388355 (368.4 MiB)  TX bytes:25600939 (24.4 MiB)

lo        Link encap:Local Loopback
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:65536  Metric:1
          RX packets:548901 errors:0 dropped:0 overruns:0 frame:0
          TX packets:548901 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0
          RX bytes:613479895 (585.0 MiB)  TX bytes:613479895 (585.0 MiB)
"""

FREEBSD = """
em0: flags=8843<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> metric 0 mtu 1500
        options=4219b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,WOL_MAGIC,VLAN_HWTSO>
        ether 00:30:48:ff:ff:ff
        inet 10.10.10.250 netmask 0xffffffe0 broadcast 10.10.10.255
        inet 10.10.10.56 netmask 0xffffffc0 broadcast 10.10.10.63
        media: Ethernet autoselect (1000baseT <full-duplex>)
        status: active
em1: flags=8c02<BROADCAST,OACTIVE,SIMPLEX,MULTICAST> metric 0 mtu 1500
        options=4219b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,WOL_MAGIC,VLAN_HWTSO>
        ether 00:30:48:aa:aa:aa
        media: Ethernet autoselect
        status: no carrier
plip0: flags=8810<POINTOPOINT,SIMPLEX,MULTICAST> metric 0 mtu 1500
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> metric 0 mtu 16384
        options=3<RXCSUM,TXCSUM>
        inet6 fe80::1%lo0 prefixlen 64 scopeid 0x8
        inet6 ::1 prefixlen 128
        inet 127.0.0.1 netmask 0xff000000
        nd6 options=3<PERFORMNUD,ACCEPT_RTADV>
tun0: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> metric 0 mtu 1500
        options=80000<LINKSTATE>
        inet 10.12.0.1 --> 10.12.0.2 netmask 0xffffffff
        Opened by PID 1964
"""

SOLARIS = """\
lo0: flags=2001000849<UP,LOOPBACK,RUNNING,MULTICAST,IPv4,VIRTUAL> mtu 8232 index 1
        inet 127.0.0.1 netmask ff000000
net0: flags=100001100943<UP,BROADCAST,RUNNING,PROMISC,MULTICAST,ROUTER,IPv4,PHYSRUNNING> mtu 1500 index 2
        inet 10.10.10.38 netmask ffffffe0 broadcast 10.10.10.63
ilbint0: flags=110001100843<UP,BROADCAST,RUNNING,MULTICAST,ROUTER,IPv4,VRRP,PHYSRUNNING> mtu 1500 index 3
        inet 10.6.0.11 netmask ffffff00 broadcast 10.6.0.255
ilbext0: flags=110001100843<UP,BROADCAST,RUNNING,MULTICAST,ROUTER,IPv4,VRRP,PHYSRUNNING> mtu 1500 index 4
        inet 10.10.11.11 netmask ffffffe0 broadcast 10.10.11.31
ilbext0:1: flags=110001100843<UP,BROADCAST,RUNNING,MULTICAST,ROUTER,IPv4,VRRP,PHYSRUNNING> mtu 1500 index 4
        inet 10.10.11.12 netmask ffffffe0 broadcast 10.10.11.31
vpn0: flags=1000011008d1<UP,POINTOPOINT,RUNNING,NOARP,MULTICAST,ROUTER,IPv4,PHYSRUNNING> mtu 1480 index 5
        inet tunnel src 10.10.11.12 tunnel dst 10.10.5.5
        tunnel hop limit 64
        inet 10.6.0.14 --> 10.6.0.15 netmask ff000000
lo0: flags=2002000849<UP,LOOPBACK,RUNNING,MULTICAST,IPv6,VIRTUAL> mtu 8252 index 1
        inet6 ::1/128
net0: flags=120002004941<UP,RUNNING,PROMISC,MULTICAST,DHCP,IPv6,PHYSRUNNING> mtu 1500 index 2
        inet6 fe80::221:9bff:fefd:2a22/10
ilbint0: flags=120002000840<RUNNING,MULTICAST,IPv6,PHYSRUNNING> mtu 1500 index 3
        inet6 ::/0
ilbext0: flags=120002000840<RUNNING,MULTICAST,IPv6,PHYSRUNNING> mtu 1500 index 4
        inet6 ::/0
vpn0: flags=120002200850<POINTOPOINT,RUNNING,MULTICAST,NONUD,IPv6,PHYSRUNNING> mtu 1480 index 5
        inet tunnel src 10.10.11.12 tunnel dst 10.10.5.5
        tunnel hop limit 64
        inet6 ::/0 --> fe80::b2d6:7c10
"""

NETBSD = """\
vioif0: flags=0x8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> mtu 1500
        ec_capabilities=1<VLAN_MTU>
        ec_enabled=0
        address: 00:a0:98:e6:83:18
        inet 192.168.1.80/24 broadcast 192.168.1.255 flags 0x0
        inet6 fe80::2a0:98ff:fee6:8318%vioif0/64 flags 0x0 scopeid 0x1
lo0: flags=0x8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 33624
        inet 127.0.0.1/8 flags 0x0
        inet6 ::1/128 flags 0x20<NODAD>
        inet6 fe80::1%lo0/64 flags 0x0 scopeid 0x2
"""

FREEBSD_SOCKSTAT = """\
USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506
"""

FREEBSD_SOCKSTAT_WITH_FAT_PID = """\
USER     COMMAND    PID   FD PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
salt-master python2.781106 35 tcp4  127.0.0.1:61115  127.0.0.1:4506
"""

OPENBSD_NETSTAT = """\
Active Internet connections
Proto   Recv-Q Send-Q  Local Address          Foreign Address        (state)
tcp          0      0  127.0.0.1.61115        127.0.0.1.4506         ESTABLISHED
"""

LINUX_NETLINK_SS_OUTPUT = """\
State       Recv-Q Send-Q                                                            Local Address:Port                                                                           Peer Address:Port
TIME-WAIT   0      0                                                                         [::1]:8009                                                                                  [::1]:40368
LISTEN      0      128                                                                   127.0.0.1:5903                                                                                0.0.0.0:*
ESTAB       0      0                                                            [::ffff:127.0.0.1]:4506                                                                    [::ffff:127.0.0.1]:32315
ESTAB       0      0                                                                 192.168.122.1:4506                                                                       192.168.122.177:24545
ESTAB       0      0                                                                    127.0.0.1:56726                                                                             127.0.0.1:4505
ESTAB       0      0                                                                ::ffff:1.2.3.4:5678                                                                        ::ffff:1.2.3.4:4505
"""

IPV4_SUBNETS = {
    True: ("10.10.0.0/24",),
    False: ("10.10.0.0", "10.10.0.0/33", "FOO", 9, "0.9.800.1000/24"),
}
IPV6_SUBNETS = {
    True: ("::1/128",),
    False: ("::1", "::1/129", "FOO", 9, "aj01::feac/64"),
}


_ip = ipaddress.ip_address


@pytest.fixture(scope="module")
def linux_interfaces_dict():
    return {
        "eth0": {
            "hwaddr": "e0:3f:49:85:6a:af",
            "inet": [
                {
                    "address": "10.10.10.56",
                    "broadcast": "10.10.10.255",
                    "netmask": "255.255.252.0",
                }
            ],
            "inet6": [
                {
                    "address": "fe80::e23f:49ff:fe85:6aaf",
                    "prefixlen": "64",
                    "scope": "link",
                }
            ],
            "up": True,
        },
        "lo": {
            "inet": [{"address": "127.0.0.1", "netmask": "255.0.0.0"}],
            "inet6": [{"address": "::1", "prefixlen": "128", "scope": "host"}],
            "up": True,
        },
    }


@pytest.fixture(scope="module")
def freebsd_interfaces_dict():
    return {
        "": {"up": False},
        "em0": {
            "hwaddr": "00:30:48:ff:ff:ff",
            "inet": [
                {
                    "address": "10.10.10.250",
                    "broadcast": "10.10.10.255",
                    "netmask": "255.255.255.224",
                },
                {
                    "address": "10.10.10.56",
                    "broadcast": "10.10.10.63",
                    "netmask": "255.255.255.192",
                },
            ],
            "up": True,
        },
        "em1": {"hwaddr": "00:30:48:aa:aa:aa", "up": False},
        "lo0": {
            "inet": [{"address": "127.0.0.1", "netmask": "255.0.0.0"}],
            "inet6": [
                {"address": "fe80::1", "prefixlen": "64", "scope": "0x8"},
                {"address": "::1", "prefixlen": "128", "scope": None},
            ],
            "up": True,
        },
        "plip0": {"up": False},
        "tun0": {
            "inet": [{"address": "10.12.0.1", "netmask": "255.255.255.255"}],
            "up": True,
        },
    }


def test_sanitize_host_ip():
    ret = network.sanitize_host("10.1./2.$3")
    assert ret == "10.1.2.3"


def test_sanitize_host_name():
    """
    Should not remove the underscore
    """
    ret = network.sanitize_host("foo_bar")
    assert ret == "foo_bar"


def test_host_to_ips():
    """
    NOTE: When this test fails it's usually because the IP address has
    changed. In these cases, we just need to update the IP address in the
    assertion.
    """

    def getaddrinfo_side_effect(host, *args):
        if host == "github.com":
            return [
                (2, 1, 6, "", ("192.30.255.112", 0)),
                (2, 1, 6, "", ("192.30.255.113", 0)),
            ]
        if host == "ipv6host.foo":
            return [
                (socket.AF_INET6, 1, 6, "", ("2001:a71::1", 0, 0, 0)),
            ]
        raise socket.gaierror(-2, "Name or service not known")

    getaddrinfo_mock = MagicMock(side_effect=getaddrinfo_side_effect)
    with patch.object(socket, "getaddrinfo", getaddrinfo_mock):
        # Test host that can be resolved
        ret = network.host_to_ips("github.com")
        assert ret == ["192.30.255.112", "192.30.255.113"]

        # Test ipv6
        ret = network.host_to_ips("ipv6host.foo")
        assert ret == ["2001:a71::1"]
        # Test host that can't be resolved
        ret = network.host_to_ips("someothersite.com")
        assert ret is None


def test_generate_minion_id():
    assert network.generate_minion_id()


def test__generate_minion_id_with_unicode_in_etc_hosts():
    """
    Test that unicode in /etc/hosts doesn't raise an error when
    _generate_minion_id() helper is called to gather the hosts.
    """
    content = textwrap.dedent(
        """\
    # 以下为主机名解析
    ## ccc
    127.0.0.1       localhost thisismyhostname     # 本机
    """
    )
    fopen_mock = mock_open(read_data={"/etc/hosts": content})
    with patch("salt.utils.files.fopen", fopen_mock):
        assert "thisismyhostname" in network._generate_minion_id()


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("10.10.0.3", True),
        ("0.9.800.1000", False),
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        ("sixteen-char-str", False),
    ),
)
def test_is_ip(addr, expected):
    assert network.is_ip(addr) is expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("10.10.0.3", True),
        ("10.100.1", False),
        ("2001:db8:0:1:1:1:1:1", False),
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        ("sixteen-char-str", False),
    ),
)
def test_is_ipv4(addr, expected):
    assert network.is_ipv4(addr) is expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("2001:db8:0:1:1:1:1:1", True),
        ("0:0:0:0:0:0:0:1", True),
        ("::1", True),
        ("::", True),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", True),
        ("2001:0db8:85a3::8a2e:0370:7334", True),
        ("2001:0db8:0370:7334", False),
        ("2001:0db8:::0370:7334", False),
        ("10.0.1.2", False),
        ("2001.0db8.85a3.0000.0000.8a2e.0370.7334", False),
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        ("sixteen-char-str", False),
    ),
)
def test_is_ipv6(addr, expected):
    assert network.is_ipv6(addr) is expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("2001:db8:0:1:1:1:1:1", "2001:db8:0:1:1:1:1:1"),
        ("0:0:0:0:0:0:0:1", "::1"),
        ("::1", "::1"),
        ("::", "::"),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", "2001:db8:85a3::8a2e:370:7334"),
        ("2001:0db8:85a3::8a2e:0370:7334", "2001:db8:85a3::8a2e:370:7334"),
        ("2001:67c:2e8::/48", "2001:67c:2e8::/48"),
    ),
)
def test_ipv6(addr, expected):
    assert network.ipv6(addr) == expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("127.0.1.1", True),
        ("::1", True),
        ("10.0.1.2", False),
        ("2001:db8:0:1:1:1:1:1", False),
    ),
)
def test_is_loopback(addr, expected):
    assert network.is_loopback(addr) is expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("10.10.0.3", (_ip("10.10.0.3").compressed, None)),
        ("10.10.0.3:1234", (_ip("10.10.0.3").compressed, 1234)),
        (
            "2001:0db8:85a3::8a2e:0370:7334",
            (
                _ip("2001:0db8:85a3::8a2e:0370:7334").compressed,
                None,
            ),
        ),
        (
            "[2001:0db8:85a3::8a2e:0370:7334]:1234",
            (
                _ip("2001:0db8:85a3::8a2e:0370:7334").compressed,
                1234,
            ),
        ),
        ("2001:0db8:85a3::7334", (_ip("2001:0db8:85a3::7334").compressed, None)),
        (
            "[2001:0db8:85a3::7334]:1234",
            (
                _ip("2001:0db8:85a3::7334").compressed,
                1234,
            ),
        ),
    ),
)
def test_parse_host_port_good(addr, expected):
    assert network.parse_host_port(addr) == expected


@pytest.mark.parametrize(
    "addr",
    (
        "10.10.0.3/24",
        "10.10.0.3::1234",
        "2001:0db8:0370:7334",
        "2001:0db8:0370::7334]:1234",
        "2001:0db8:0370:0:a:b:c:d:1234",
        "host name",
        "host name:1234",
        "10.10.0.3:abcd",
    ),
)
def test_parse_host_port_bad_raises_value_error(addr):
    with pytest.raises(ValueError):
        network.parse_host_port(addr)


@pytest.mark.parametrize(
    "host",
    (
        (
            {
                "host": "10.10.0.3",
                "port": "",
                "mocked": [(2, 1, 6, "", ("10.10.0.3", 0))],
                "ret": "10.10.0.3",
            }
        ),
        (
            {
                "host": "10.10.0.3",
                "port": "1234",
                "mocked": [(2, 1, 6, "", ("10.10.0.3", 0))],
                "ret": "10.10.0.3",
            }
        ),
        (
            {
                "host": "2001:0db8:85a3::8a2e:0370:7334",
                "port": "",
                "mocked": [(10, 1, 6, "", ("2001:db8:85a3::8a2e:370:7334", 0, 0, 0))],
                "ret": "[2001:db8:85a3::8a2e:370:7334]",
            }
        ),
        (
            {
                "host": "2001:0db8:85a3::8a2e:370:7334",
                "port": "1234",
                "mocked": [(10, 1, 6, "", ("2001:db8:85a3::8a2e:370:7334", 0, 0, 0))],
                "ret": "[2001:db8:85a3::8a2e:370:7334]",
            }
        ),
        (
            {
                "host": "salt-master",
                "port": "1234",
                "mocked": [(2, 1, 6, "", ("127.0.0.1", 0))],
                "ret": "127.0.0.1",
            }
        ),
    ),
)
def test_dns_check(host):
    with patch.object(
        socket,
        "getaddrinfo",
        create_autospec(socket.getaddrinfo, return_value=host["mocked"]),
    ):
        with patch("socket.socket", create_autospec(socket.socket)):
            ret = network.dns_check(host["host"], host["port"])
            assert ret == host["ret"]


def test_dns_check_ipv6_filter():
    # raise exception to skip everything after the getaddrinfo call
    with patch.object(
        socket,
        "getaddrinfo",
        create_autospec(socket.getaddrinfo, side_effect=Exception),
    ) as getaddrinfo:
        for ipv6, param in [
            (None, socket.AF_UNSPEC),
            (True, socket.AF_INET6),
            (False, socket.AF_INET),
        ]:
            with pytest.raises(Exception):
                network.dns_check("foo", "1", ipv6=ipv6)
            getaddrinfo.assert_called_with("foo", "1", param, socket.SOCK_STREAM)


def test_dns_check_errors():
    with patch.object(
        socket, "getaddrinfo", create_autospec(socket.getaddrinfo, return_value=[])
    ):
        with pytest.raises(
            salt.exceptions.SaltSystemExit,
            match="DNS lookup or connection check of 'foo' failed.",
        ) as exc_info:
            network.dns_check("foo", "1")

    with patch.object(
        socket,
        "getaddrinfo",
        create_autospec(socket.getaddrinfo, side_effect=TypeError),
    ):
        with pytest.raises(
            salt.exceptions.SaltSystemExit, match="Invalid or unresolveable address"
        ) as exc_info2:
            network.dns_check("foo", "1")


def test_test_addrs():
    # subset of real data from getaddrinfo against saltstack.com
    addrinfo = [
        (30, 2, 17, "", ("2600:9000:21eb:a800:8:1031:abc0:93a1", 0, 0, 0)),
        (30, 1, 6, "", ("2600:9000:21eb:a800:8:1031:abc0:93a1", 0, 0, 0)),
        (30, 2, 17, "", ("2600:9000:21eb:b400:8:1031:abc0:93a1", 0, 0, 0)),
        (30, 1, 6, "", ("2600:9000:21eb:b400:8:1031:abc0:93a1", 0, 0, 0)),
        (2, 1, 6, "", ("13.35.99.52", 0)),
        (2, 2, 17, "", ("13.35.99.85", 0)),
        (2, 1, 6, "", ("13.35.99.85", 0)),
        (2, 2, 17, "", ("13.35.99.122", 0)),
    ]
    with patch("socket.socket", create_autospec(socket.socket)) as s:
        # we connect to the first address
        addrs = network._test_addrs(addrinfo, 80)
        assert len(addrs) == 1
        assert addrs[0] == addrinfo[0][4][0]

        # the first lookup fails, succeeds on next check
        s.side_effect = [socket.error, MagicMock()]
        addrs = network._test_addrs(addrinfo, 80)
        assert len(addrs) == 1
        assert addrs[0] == addrinfo[2][4][0]

        # attempt to connect to resolved address with default timeout
        s.side_effect = socket.error
        addrs = network._test_addrs(addrinfo, 80)
        assert not len(addrs) == 0

        # nothing can connect, but we've eliminated duplicates
        s.side_effect = socket.error
        addrs = network._test_addrs(addrinfo, 80)
        assert len(addrs) == 5


def test_is_subnet():
    for subnet_data in (IPV4_SUBNETS, IPV6_SUBNETS):
        for item in subnet_data[True]:
            log.debug("Testing that %s is a valid subnet", item)
            assert network.is_subnet(item)
        for item in subnet_data[False]:
            log.debug("Testing that %s is not a valid subnet", item)
            assert not network.is_subnet(item)


def test_is_ipv4_subnet():
    for item in IPV4_SUBNETS[True]:
        log.debug("Testing that %s is a valid subnet", item)
        assert network.is_ipv4_subnet(item)
    for item in IPV4_SUBNETS[False]:
        log.debug("Testing that %s is not a valid subnet", item)
        assert not network.is_ipv4_subnet(item)


def test_is_ipv6_subnet():
    for item in IPV6_SUBNETS[True]:
        log.debug("Testing that %s is a valid subnet", item)
        assert network.is_ipv6_subnet(item) is True
    for item in IPV6_SUBNETS[False]:
        log.debug("Testing that %s is not a valid subnet", item)
        assert network.is_ipv6_subnet(item) is False


@pytest.mark.parametrize(
    "addr,expected",
    (
        (24, "255.255.255.0"),
        (21, "255.255.248.0"),
        (17, "255.255.128.0"),
        (9, "255.128.0.0"),
        (36, ""),
        ("lol", ""),
    ),
)
def test_cidr_to_ipv4_netmask(addr, expected):
    assert network.cidr_to_ipv4_netmask(addr) == expected


def test_number_of_set_bits_to_ipv4_netmask():
    set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xFFFFFF00)
    assert set_bits_to_netmask == "255.255.255.0"
    set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xFFFF6400)
    assert set_bits_to_netmask == "255.255.100.0"


@pytest.mark.parametrize(
    "hex_num,inversion,expected",
    (
        ("0x4A7D2B63", False, "74.125.43.99"),
        ("0x4A7D2B63", True, "99.43.125.74"),
        ("00000000000000000000FFFF7F000001", False, "127.0.0.1"),
        ("0000000000000000FFFF00000100007F", True, "127.0.0.1"),
        ("20010DB8000000000000000000000000", False, "2001:db8::"),
        ("B80D0120000000000000000000000000", True, "2001:db8::"),
    ),
)
def test_hex2ip(hex_num, inversion, expected):
    assert network.hex2ip(hex_num, inversion) == expected


def test_interfaces_ifconfig_linux(linux_interfaces_dict):
    interfaces = network._interfaces_ifconfig(LINUX)
    assert interfaces == linux_interfaces_dict


def test_interfaces_ifconfig_freebsd(freebsd_interfaces_dict):
    interfaces = network._interfaces_ifconfig(FREEBSD)
    assert interfaces == freebsd_interfaces_dict


def test_interfaces_ifconfig_solaris():
    with patch("salt.utils.platform.is_sunos", return_value=True):
        expected_interfaces = {
            "ilbint0": {
                "inet6": [],
                "inet": [
                    {
                        "broadcast": "10.6.0.255",
                        "netmask": "255.255.255.0",
                        "address": "10.6.0.11",
                    }
                ],
                "up": True,
            },
            "lo0": {
                "inet6": [{"prefixlen": "128", "address": "::1"}],
                "inet": [{"netmask": "255.0.0.0", "address": "127.0.0.1"}],
                "up": True,
            },
            "ilbext0": {
                "inet6": [],
                "inet": [
                    {
                        "broadcast": "10.10.11.31",
                        "netmask": "255.255.255.224",
                        "address": "10.10.11.11",
                    },
                    {
                        "broadcast": "10.10.11.31",
                        "netmask": "255.255.255.224",
                        "address": "10.10.11.12",
                    },
                ],
                "up": True,
            },
            "vpn0": {
                "inet6": [],
                "inet": [{"netmask": "255.0.0.0", "address": "10.6.0.14"}],
                "up": True,
            },
            "net0": {
                "inet6": [{"prefixlen": "10", "address": "fe80::221:9bff:fefd:2a22"}],
                "inet": [
                    {
                        "broadcast": "10.10.10.63",
                        "netmask": "255.255.255.224",
                        "address": "10.10.10.38",
                    }
                ],
                "up": True,
            },
        }
        interfaces = network._interfaces_ifconfig(SOLARIS)
        assert interfaces == expected_interfaces


def test_interfaces_ifconfig_netbsd():
    expected_interfaces = {
        "lo0": {
            "inet": [{"address": "127.0.0.1", "netmask": "255.0.0.0"}],
            "inet6": [{"address": "fe80::1", "prefixlen": "64", "scope": "lo0"}],
            "up": True,
        },
        "vioif0": {
            "hwaddr": "00:a0:98:e6:83:18",
            "inet": [
                {
                    "address": "192.168.1.80",
                    "broadcast": "192.168.1.255",
                    "netmask": "255.255.255.0",
                }
            ],
            "inet6": [
                {
                    "address": "fe80::2a0:98ff:fee6:8318",
                    "prefixlen": "64",
                    "scope": "vioif0",
                }
            ],
            "up": True,
        },
    }
    interfaces = network._netbsd_interfaces_ifconfig(NETBSD)
    assert interfaces == expected_interfaces


def test_freebsd_remotes_on():
    with patch("salt.utils.platform.is_sunos", return_value=False):
        with patch("salt.utils.platform.is_freebsd", return_value=True):
            with patch("subprocess.check_output", return_value=FREEBSD_SOCKSTAT):
                remotes = network._freebsd_remotes_on("4506", "remote")
                assert remotes == {"127.0.0.1"}


def test_freebsd_remotes_on_with_fat_pid():
    with patch("salt.utils.platform.is_sunos", return_value=False):
        with patch("salt.utils.platform.is_freebsd", return_value=True):
            with patch(
                "subprocess.check_output",
                return_value=FREEBSD_SOCKSTAT_WITH_FAT_PID,
            ):
                remotes = network._freebsd_remotes_on("4506", "remote")
                assert remotes == {"127.0.0.1"}


def test_netlink_tool_remote_on_a():
    with patch("salt.utils.platform.is_sunos", return_value=False):
        with patch("salt.utils.platform.is_linux", return_value=True):
            with patch("subprocess.check_output", return_value=LINUX_NETLINK_SS_OUTPUT):
                remotes = network._netlink_tool_remote_on("4506", "local_port")
                assert remotes == {"192.168.122.177", "127.0.0.1"}


def test_netlink_tool_remote_on_b():
    with patch("subprocess.check_output", return_value=LINUX_NETLINK_SS_OUTPUT):
        remotes = network._netlink_tool_remote_on("4505", "remote_port")
        assert remotes == {"127.0.0.1", "1.2.3.4"}


def test_openbsd_remotes_on():
    with patch("subprocess.check_output", return_value=OPENBSD_NETSTAT):
        remotes = network._openbsd_remotes_on("4506", "remote")
        assert remotes == {"127.0.0.1"}


def test_openbsd_remotes_on_issue_61966():
    """
    Test that the command output is correctly converted to string before
    treating it as such
    """
    with patch("subprocess.check_output", return_value=OPENBSD_NETSTAT.encode()):
        remotes = network._openbsd_remotes_on("4506", "remote")
        assert remotes == {"127.0.0.1"}


def test_generate_minion_id_distinct():
    """
    Test if minion IDs are distinct in the pool.
    """
    with patch("platform.node", MagicMock(return_value="nodename")), patch(
        "socket.gethostname", MagicMock(return_value="hostname")
    ), patch(
        "socket.getfqdn", MagicMock(return_value="hostname.domainname.blank")
    ), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "attrname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "5.6.7.8"]),
    ):
        assert network._generate_minion_id() == [
            "hostname.domainname.blank",
            "nodename",
            "hostname",
            "1.2.3.4",
            "5.6.7.8",
        ]


def test_generate_minion_id_127_name():
    """
    Test if minion IDs can be named 127.foo
    """
    with patch("platform.node", MagicMock(return_value="127")), patch(
        "socket.gethostname", MagicMock(return_value="127")
    ), patch("socket.getfqdn", MagicMock(return_value="127.domainname.blank")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "attrname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "5.6.7.8"]),
    ):
        assert network._generate_minion_id() == [
            "127.domainname.blank",
            "127",
            "1.2.3.4",
            "5.6.7.8",
        ]


def test_generate_minion_id_127_name_startswith():
    """
    Test if minion IDs can be named starting from "127"
    """
    expected = [
        "127890.domainname.blank",
        "127890",
        "1.2.3.4",
        "5.6.7.8",
    ]
    with patch("platform.node", MagicMock(return_value="127890")), patch(
        "socket.gethostname", MagicMock(return_value="127890")
    ), patch(
        "socket.getfqdn", MagicMock(return_value="127890.domainname.blank")
    ), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "attrname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "5.6.7.8"]),
    ):
        assert network._generate_minion_id() == expected


def test_generate_minion_id_duplicate():
    """
    Test if IP addresses in the minion IDs are distinct in the pool
    """
    expected = ["hostname", "1.2.3.4"]
    with patch("platform.node", MagicMock(return_value="hostname")), patch(
        "socket.gethostname", MagicMock(return_value="hostname")
    ), patch("socket.getfqdn", MagicMock(return_value="hostname")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "hostname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "1.2.3.4", "1.2.3.4"]),
    ):
        assert network._generate_minion_id() == expected


def test_generate_minion_id_platform_used():
    """
    Test if platform.node is used for the first occurrence.
    The platform.node is most common hostname resolver before anything else.
    """
    with patch(
        "platform.node", MagicMock(return_value="very.long.and.complex.domain.name")
    ), patch("socket.gethostname", MagicMock(return_value="hostname")), patch(
        "socket.getfqdn", MagicMock(return_value="")
    ), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "hostname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "1.2.3.4", "1.2.3.4"]),
    ):
        assert network.generate_minion_id() == "very.long.and.complex.domain.name"


def test_generate_minion_id_platform_localhost_filtered():
    """
    Test if localhost is filtered from the first occurrence.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="pick.me")
    ), patch(
        "socket.getfqdn", MagicMock(return_value="hostname.domainname.blank")
    ), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "hostname", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["1.2.3.4", "1.2.3.4", "1.2.3.4"]),
    ):
        assert network.generate_minion_id() == "hostname.domainname.blank"


def test_generate_minion_id_platform_localhost_filtered_all():
    """
    Test if any of the localhost is filtered from everywhere.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="ip6-loopback")
    ), patch("socket.getfqdn", MagicMock(return_value="ip6-localhost")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "localhost", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1", "1.2.3.4"]),
    ):
        assert network.generate_minion_id() == "1.2.3.4"


def test_generate_minion_id_platform_localhost_only():
    """
    Test if there is no other choice but localhost.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="ip6-loopback")
    ), patch("socket.getfqdn", MagicMock(return_value="ip6-localhost")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "localhost", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1"]),
    ):
        assert network.generate_minion_id() == "localhost"


def test_generate_minion_id_platform_fqdn():
    """
    Test if fqdn is picked up.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="ip6-loopback")
    ), patch("socket.getfqdn", MagicMock(return_value="pick.me")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "localhost", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1"]),
    ):
        assert network.generate_minion_id() == "pick.me"


def test_generate_minion_id_platform_localhost_addrinfo():
    """
    Test if addinfo is picked up.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="ip6-loopback")
    ), patch("socket.getfqdn", MagicMock(return_value="ip6-localhost")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "pick.me", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1"]),
    ):
        assert network.generate_minion_id() == "pick.me"


def test_generate_minion_id_platform_ip_addr_only():
    """
    Test if IP address is the only what is used as a Minion ID in case no DNS name.
    """
    with patch("platform.node", MagicMock(return_value="localhost")), patch(
        "socket.gethostname", MagicMock(return_value="ip6-loopback")
    ), patch("socket.getfqdn", MagicMock(return_value="ip6-localhost")), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "localhost", ("127.0.1.1", 0))]),
    ), patch(
        "salt.utils.files.fopen", mock_open()
    ), patch(
        "salt.utils.network.ip_addrs",
        MagicMock(return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1", "1.2.3.4"]),
    ):
        assert network.generate_minion_id() == "1.2.3.4"


def test_gen_mac():
    expected_mac = "00:16:3E:01:01:01"
    with patch("random.randint", return_value=1) as random_mock:
        assert random_mock.return_value == 1
        ret = network.gen_mac("00:16:3E")
        assert ret == expected_mac


@pytest.mark.parametrize(
    "mac_addr",
    (
        ("31337"),
        ("0001020304056"),
        ("00:01:02:03:04:056"),
        ("a0:b0:c0:d0:e0:fg"),
    ),
)
def test_mac_str_to_bytes_exceptions(mac_addr):
    with pytest.raises(ValueError):
        network.mac_str_to_bytes(mac_addr)


def test_mac_str_to_bytes():
    assert network.mac_str_to_bytes("100806040200") == b"\x10\x08\x06\x04\x02\x00"
    assert network.mac_str_to_bytes("f8e7d6c5b4a3") == b"\xf8\xe7\xd6\xc5\xb4\xa3"


@pytest.mark.slow_test
def test_generate_minion_id_with_long_hostname():
    """
    Validate the fix for:

    https://github.com/saltstack/salt/issues/51160
    """
    long_name = "localhost-abcdefghijklmnopqrstuvwxyz-abcdefghijklmnopqrstuvwxyz"
    with patch("socket.gethostname", MagicMock(return_value=long_name)):
        # An exception is raised if unicode is passed to socket.getfqdn
        minion_id = network.generate_minion_id()
    assert minion_id != ""


def test_filter_by_networks_with_no_filter():
    ips = ["10.0.123.200", "10.10.10.10"]
    with pytest.raises(TypeError):
        network.filter_by_networks(ips)  # pylint: disable=no-value-for-parameter


def test_filter_by_networks_empty_filter():
    ips = ["10.0.123.200", "10.10.10.10"]
    assert network.filter_by_networks(ips, []) == []


def test_filter_by_networks_ips_list():
    ips = [
        "10.0.123.200",
        "10.10.10.10",
        "193.124.233.5",
        "fe80::d210:cf3f:64e7:5423",
    ]
    expected = [
        "10.0.123.200",
        "10.10.10.10",
        "fe80::d210:cf3f:64e7:5423",
    ]
    networks = ["10.0.0.0/8", "fe80::/64"]
    assert network.filter_by_networks(ips, networks) == expected


def test_filter_by_networks_interfaces_dict():
    interfaces = {
        "wlan0": ["192.168.1.100", "217.5.140.67", "2001:db8::ff00:42:8329"],
        "eth0": [
            "2001:0DB8:0:CD30:123:4567:89AB:CDEF",
            "192.168.1.101",
            "10.0.123.201",
        ],
    }
    expected = {
        "wlan0": ["192.168.1.100", "2001:db8::ff00:42:8329"],
        "eth0": ["2001:0DB8:0:CD30:123:4567:89AB:CDEF", "192.168.1.101"],
    }
    ret = network.filter_by_networks(interfaces, ["192.168.1.0/24", "2001:db8::/48"])
    assert ret == expected


def test_filter_by_networks_catch_all():
    ips = [
        "10.0.123.200",
        "10.10.10.10",
        "193.124.233.5",
        "fe80::d210:cf3f:64e7:5423",
    ]
    assert network.filter_by_networks(ips, ["0.0.0.0/0", "::/0"]) == ips


def test_ip_networks():
    # We don't need to test with each platform's ifconfig/iproute2 output,
    # since this test isn't testing getting the interfaces. We already have
    # tests for that.
    interface_data = network._interfaces_ifconfig(LINUX)

    # Without loopback
    ret = network.ip_networks(interface_data=interface_data)
    assert ret == ["10.10.8.0/22"]
    # Without loopback, specific interface
    ret = network.ip_networks(interface="eth0", interface_data=interface_data)
    assert ret == ["10.10.8.0/22"]
    # Without loopback, multiple specific interfaces
    ret = network.ip_networks(interface="eth0,lo", interface_data=interface_data)
    assert ret == ["10.10.8.0/22"]
    # Without loopback, specific interface (not present)
    ret = network.ip_networks(interface="eth1", interface_data=interface_data)
    assert ret == []
    # With loopback
    ret = network.ip_networks(include_loopback=True, interface_data=interface_data)
    assert ret == ["10.10.8.0/22", "127.0.0.0/8"]
    # With loopback, specific interface
    ret = network.ip_networks(
        interface="eth0", include_loopback=True, interface_data=interface_data
    )
    assert ret == ["10.10.8.0/22"]
    # With loopback, multiple specific interfaces
    ret = network.ip_networks(
        interface="eth0,lo", include_loopback=True, interface_data=interface_data
    )
    assert ret == ["10.10.8.0/22", "127.0.0.0/8"]
    # With loopback, specific interface (not present)
    ret = network.ip_networks(
        interface="eth1", include_loopback=True, interface_data=interface_data
    )
    assert ret == []

    # Verbose, without loopback
    ret = network.ip_networks(verbose=True, interface_data=interface_data)
    expected_ret1 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
    }
    assert ret == expected_ret1

    # Verbose, without loopback, specific interface
    ret = network.ip_networks(
        interface="eth0", verbose=True, interface_data=interface_data
    )
    expected_ret2 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
    }
    assert ret == expected_ret2

    # Verbose, without loopback, multiple specific interfaces
    ret = network.ip_networks(
        interface="eth0,lo", verbose=True, interface_data=interface_data
    )
    expected_ret3 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
    }
    assert ret == expected_ret3

    # Verbose, without loopback, specific interface (not present)
    ret = network.ip_networks(
        interface="eth1", verbose=True, interface_data=interface_data
    )
    assert ret == {}
    # Verbose, with loopback
    ret = network.ip_networks(
        include_loopback=True, verbose=True, interface_data=interface_data
    )
    expected_ret4 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
        "127.0.0.0/8": {
            "prefixlen": 8,
            "netmask": "255.0.0.0",
            "num_addresses": 16777216,
            "address": "127.0.0.0",
        },
    }
    assert ret == expected_ret4

    # Verbose, with loopback, specific interface
    ret = network.ip_networks(
        interface="eth0",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    expected_ret5 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
    }
    assert ret == expected_ret5

    # Verbose, with loopback, multiple specific interfaces
    ret = network.ip_networks(
        interface="eth0,lo",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    expected_ret6 = {
        "10.10.8.0/22": {
            "prefixlen": 22,
            "netmask": "255.255.252.0",
            "num_addresses": 1024,
            "address": "10.10.8.0",
        },
        "127.0.0.0/8": {
            "prefixlen": 8,
            "netmask": "255.0.0.0",
            "num_addresses": 16777216,
            "address": "127.0.0.0",
        },
    }
    assert ret == expected_ret6

    # Verbose, with loopback, specific interface (not present)
    ret = network.ip_networks(
        interface="eth1",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    assert ret == {}


def test_ip_networks6():
    # We don't need to test with each platform's ifconfig/iproute2 output,
    # since this test isn't testing getting the interfaces. We already have
    # tests for that.
    interface_data = network._interfaces_ifconfig(LINUX)

    # Without loopback
    ret = network.ip_networks6(interface_data=interface_data)
    assert ret == ["fe80::/64"]
    # Without loopback, specific interface
    ret = network.ip_networks6(interface="eth0", interface_data=interface_data)
    assert ret == ["fe80::/64"]
    # Without loopback, multiple specific interfaces
    ret = network.ip_networks6(interface="eth0,lo", interface_data=interface_data)
    assert ret == ["fe80::/64"]
    # Without loopback, specific interface (not present)
    ret = network.ip_networks6(interface="eth1", interface_data=interface_data)
    assert ret == []
    # With loopback
    ret = network.ip_networks6(include_loopback=True, interface_data=interface_data)
    assert ret == ["::1/128", "fe80::/64"]
    # With loopback, specific interface
    ret = network.ip_networks6(
        interface="eth0", include_loopback=True, interface_data=interface_data
    )
    assert ret == ["fe80::/64"]
    # With loopback, multiple specific interfaces
    ret = network.ip_networks6(
        interface="eth0,lo", include_loopback=True, interface_data=interface_data
    )
    assert ret == ["::1/128", "fe80::/64"]
    # With loopback, specific interface (not present)
    ret = network.ip_networks6(
        interface="eth1", include_loopback=True, interface_data=interface_data
    )
    assert ret == []

    # Verbose, without loopback
    ret = network.ip_networks6(verbose=True, interface_data=interface_data)
    expected_ret1 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
    }
    assert ret == expected_ret1

    # Verbose, without loopback, specific interface
    ret = network.ip_networks6(
        interface="eth0", verbose=True, interface_data=interface_data
    )
    expected_ret2 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
    }
    assert ret == expected_ret2

    # Verbose, without loopback, multiple specific interfaces
    ret = network.ip_networks6(
        interface="eth0,lo", verbose=True, interface_data=interface_data
    )
    expected_ret3 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
    }
    assert ret == expected_ret3

    # Verbose, without loopback, specific interface (not present)
    ret = network.ip_networks6(
        interface="eth1", verbose=True, interface_data=interface_data
    )
    assert ret == {}

    # Verbose, with loopback
    ret = network.ip_networks6(
        include_loopback=True, verbose=True, interface_data=interface_data
    )
    expected_ret4 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
        "::1/128": {
            "prefixlen": 128,
            "netmask": "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
            "num_addresses": 1,
            "address": "::1",
        },
    }
    assert ret == expected_ret4

    # Verbose, with loopback, specific interface
    ret = network.ip_networks6(
        interface="eth0",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    expected_ret5 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
    }
    assert ret == expected_ret5

    # Verbose, with loopback, multiple specific interfaces
    ret = network.ip_networks6(
        interface="eth0,lo",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    expected_ret6 = {
        "fe80::/64": {
            "prefixlen": 64,
            "netmask": "ffff:ffff:ffff:ffff::",
            "num_addresses": 18446744073709551616,
            "address": "fe80::",
        },
        "::1/128": {
            "prefixlen": 128,
            "netmask": "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
            "num_addresses": 1,
            "address": "::1",
        },
    }
    assert ret == expected_ret6

    # Verbose, with loopback, specific interface (not present)
    ret = network.ip_networks6(
        interface="eth1",
        include_loopback=True,
        verbose=True,
        interface_data=interface_data,
    )
    assert ret == {}


def test_get_fqhostname_return():
    """
    Test if proper hostname is used when RevDNS differ from hostname
    """
    with patch("socket.gethostname", MagicMock(return_value="hostname")), patch(
        "socket.getfqdn",
        MagicMock(return_value="very.long.and.complex.domain.name"),
    ), patch(
        "socket.getaddrinfo",
        MagicMock(return_value=[(2, 3, 0, "hostname", ("127.0.1.1", 0))]),
    ):
        assert network.get_fqhostname() == "hostname"


def test_get_fqhostname_return_empty_hostname():
    """
    Test if proper hostname is used when hostname returns empty string
    """
    host = "hostname"
    with patch("socket.gethostname", MagicMock(return_value=host)), patch(
        "socket.getfqdn",
        MagicMock(return_value="very.long.and.complex.domain.name"),
    ), patch(
        "socket.getaddrinfo",
        MagicMock(
            return_value=[
                (2, 3, 0, host, ("127.0.1.1", 0)),
                (2, 3, 0, "", ("127.0.1.1", 0)),
            ]
        ),
    ):
        assert network.get_fqhostname() == host


@pytest.mark.parametrize(
    "addr,expected,strip",
    (
        ("127.0.0.1", "127.0.0.1", False),
        ("[::1]", "::1", True),
        ("::1", "[::1]", False),
        ("[::1]", "[::1]", False),
        (ipaddress.ip_address("127.0.0.1"), "127.0.0.1", False),
    ),
)
def test_ip_bracket(addr, expected, strip):
    assert network.ip_bracket(addr, strip=strip) == expected


def test_junos_ifconfig_output_parsing():
    ret = network._junos_interfaces_ifconfig("inet mtu 0 local=" + " " * 3456)
    assert ret == {"inet": {"up": False}}


def test_isportopen_false():
    ret = network.isportopen("127.0.0.1", "66000")
    assert ret is False


def test_isportopen():
    if salt.utils.platform.is_windows():
        port = "135"
    else:
        port = "22"
    ret = network.isportopen("127.0.0.1", port)
    assert ret == 0


def test_get_socket():
    ret = network.get_socket("127.0.0.1")
    assert ret.family == socket.AF_INET
    assert ret.type == socket.SOCK_STREAM

    ret = network.get_socket("2001:a71::1")
    assert ret.family == socket.AF_INET6
    assert ret.type == socket.SOCK_STREAM


# @pytest.mark.skip_on_windows(reason="Do not run on Windows")
def test_ip_to_host(grains):
    if salt.utils.platform.is_windows():
        hostname = socket.gethostname()
    else:
        hostname = "localhost"

    ret = network.ip_to_host("127.0.0.1")
    if grains.get("oscodename") == "Photon":
        # Photon returns this for IPv4
        assert ret == "ipv6-localhost"
    else:
        assert ret == hostname

    ret = network.ip_to_host("2001:a71::1")
    assert ret is None

    ret = network.ip_to_host("::1")
    if grains["os"] == "Amazon":
        assert ret == "localhost6"
    elif grains["os_family"] == "Debian":
        if grains["osmajorrelease"] == 12:
            assert ret == hostname
        else:
            assert ret == "ip6-localhost"
    elif grains["os_family"] == "RedHat":
        if grains["oscodename"] == "Photon":
            assert ret == "ipv6-localhost"
        else:
            assert ret == hostname
    elif grains["os_family"] == "Arch":
        if grains.get("osmajorrelease", None) is None:
            # running doesn't have osmajorrelease grains
            assert ret == hostname
        else:
            assert ret == "ip6-localhost"
    else:
        assert ret == hostname


@pytest.mark.parametrize(
    "addr,fmtr,expected",
    (
        ("192.168.0.115", "prefixlen", "/24"),
        ("192.168.1.80", "prefixlen", "/24"),
        ("10.10.10.250", "prefixlen", "/8"),
        ("192.168.0.115", "netmask", "255.255.255.0"),
        ("192.168.1.80", "netmask", "255.255.255.0"),
        ("10.10.10.250", "netmask", "255.0.0.0"),
    ),
)
def test_natural_ipv4_netmask(addr, fmtr, expected):
    assert network.natural_ipv4_netmask(addr, fmt=fmtr) == expected


@pytest.mark.parametrize(
    "addr,expected",
    (
        ("127.0", "127.0.0.0"),
        ("192.168.3", "192.168.3.0"),
        ("10.209", "10.209.0.0"),
    ),
)
def test_rpad_ipv4_network(addr, expected):
    assert network.rpad_ipv4_network(addr) == expected


def test_hw_addr(linux_interfaces_dict, freebsd_interfaces_dict):

    with patch(
        "salt.utils.network.interfaces",
        MagicMock(return_value=linux_interfaces_dict),
    ):
        hw_addrs = network.hw_addr("eth0")
        assert hw_addrs == "e0:3f:49:85:6a:af"

    with patch(
        "salt.utils.network.interfaces", MagicMock(return_value=freebsd_interfaces_dict)
    ), patch("salt.utils.platform.is_netbsd", MagicMock(return_value=True)):
        hw_addrs = network.hw_addr("em0")
        assert hw_addrs == "00:30:48:ff:ff:ff"

        hw_addrs = network.hw_addr("em1")
        assert hw_addrs == "00:30:48:aa:aa:aa"

        hw_addrs = network.hw_addr("dog")
        assert (
            hw_addrs
            == 'Interface "dog" not in available interfaces: "", "em0", "em1", "lo0", "plip0", "tun0"'
        )


def test_interface_and_ip(linux_interfaces_dict):

    with patch(
        "salt.utils.network.interfaces",
        MagicMock(return_value=linux_interfaces_dict),
    ):
        expected = [
            {
                "address": "10.10.10.56",
                "broadcast": "10.10.10.255",
                "netmask": "255.255.252.0",
            }
        ]
        ret = network.interface("eth0")
        assert ret == expected

        ret = network.interface("dog")
        assert ret == 'Interface "dog" not in available interfaces: "eth0", "lo"'

        ret = network.interface_ip("eth0")
        assert ret == "10.10.10.56"

        ret = network.interface_ip("dog")
        assert ret == 'Interface "dog" not in available interfaces: "eth0", "lo"'


def test_subnets(linux_interfaces_dict):

    with patch(
        "salt.utils.network.interfaces",
        MagicMock(return_value=linux_interfaces_dict),
    ):
        ret = network.subnets()
        assert ret == ["10.10.8.0/22"]

        ret = network.subnets6()
        assert ret == ["fe80::/64"]


def test_in_subnet(caplog):
    assert network.in_subnet("fe80::/64", "fe80::e23f:49ff:fe85:6aaf")
    assert network.in_subnet("10.10.8.0/22", "10.10.10.56")
    assert not network.in_subnet("10.10.8.0/22")

    caplog.clear()
    ret = network.in_subnet("10.10.8.0/40")
    assert "Invalid CIDR '10.10.8.0/40'" in caplog.text
    assert not ret


def test_ip_addrs(linux_interfaces_dict):
    with patch(
        "salt.utils.network.interfaces",
        MagicMock(return_value=linux_interfaces_dict),
    ):
        ret = network.ip_addrs("eth0")
        assert ret == ["10.10.10.56"]

    with patch(
        "salt.utils.network.interfaces",
        MagicMock(return_value=linux_interfaces_dict),
    ):
        ret = network.ip_addrs6("eth0")
        assert ret == ["fe80::e23f:49ff:fe85:6aaf"]
