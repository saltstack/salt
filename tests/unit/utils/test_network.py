# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import socket
import textwrap

import salt.exceptions

# Import salt libs
import salt.utils.network as network
from salt._compat import ipaddress
from tests.support.mock import MagicMock, create_autospec, mock_open, patch

# Import Salt Testing libs
from tests.support.unit import TestCase

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

NETLINK_SS = """
State      Recv-Q Send-Q               Local Address:Port                 Peer Address:Port
ESTAB      0      0                    127.0.0.1:56726                    127.0.0.1:4505
ESTAB      0      0                    ::ffff:1.2.3.4:5678                ::ffff:1.2.3.4:4505
"""

LINUX_NETLINK_SS_OUTPUT = """\
State       Recv-Q Send-Q                                                            Local Address:Port                                                                           Peer Address:Port
TIME-WAIT   0      0                                                                         [::1]:8009                                                                                  [::1]:40368
LISTEN      0      128                                                                   127.0.0.1:5903                                                                                0.0.0.0:*
ESTAB       0      0                                                            [::ffff:127.0.0.1]:4506                                                                    [::ffff:127.0.0.1]:32315
ESTAB       0      0                                                                 192.168.122.1:4506                                                                       192.168.122.177:24545
"""

IPV4_SUBNETS = {
    True: ("10.10.0.0/24",),
    False: ("10.10.0.0", "10.10.0.0/33", "FOO", 9, "0.9.800.1000/24"),
}
IPV6_SUBNETS = {
    True: ("::1/128",),
    False: ("::1", "::1/129", "FOO", 9, "aj01::feac/64"),
}


class NetworkTestCase(TestCase):
    def test_sanitize_host(self):
        ret = network.sanitize_host("10.1./2.$3")
        self.assertEqual(ret, "10.1.2.3")

    def test_host_to_ips(self):
        """
        NOTE: When this test fails it's usually because the IP address has
        changed. In these cases, we just need to update the IP address in the
        assertion.
        """

        def _side_effect(host, *args):
            try:
                return {
                    "github.com": [
                        (2, 1, 6, "", ("192.30.255.112", 0)),
                        (2, 1, 6, "", ("192.30.255.113", 0)),
                    ],
                    "ipv6host.foo": [
                        (socket.AF_INET6, 1, 6, "", ("2001:a71::1", 0, 0, 0)),
                    ],
                }[host]
            except KeyError:
                raise socket.gaierror(-2, "Name or service not known")

        getaddrinfo_mock = MagicMock(side_effect=_side_effect)
        with patch.object(socket, "getaddrinfo", getaddrinfo_mock):
            # Test host that can be resolved
            ret = network.host_to_ips("github.com")
            self.assertEqual(ret, ["192.30.255.112", "192.30.255.113"])
            # Test ipv6
            ret = network.host_to_ips("ipv6host.foo")
            self.assertEqual(ret, ["2001:a71::1"])
            # Test host that can't be resolved
            ret = network.host_to_ips("someothersite.com")
            self.assertEqual(ret, None)

    def test_generate_minion_id(self):
        self.assertTrue(network.generate_minion_id())

    def test__generate_minion_id_with_unicode_in_etc_hosts(self):
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

    def test_is_ip(self):
        self.assertTrue(network.is_ip("10.10.0.3"))
        self.assertFalse(network.is_ip("0.9.800.1000"))
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        self.assertFalse(network.is_ipv6("sixteen-char-str"))

    def test_is_ipv4(self):
        self.assertTrue(network.is_ipv4("10.10.0.3"))
        self.assertFalse(network.is_ipv4("10.100.1"))
        self.assertFalse(network.is_ipv4("2001:db8:0:1:1:1:1:1"))
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        self.assertFalse(network.is_ipv4("sixteen-char-str"))

    def test_is_ipv6(self):
        self.assertTrue(network.is_ipv6("2001:db8:0:1:1:1:1:1"))
        self.assertTrue(network.is_ipv6("0:0:0:0:0:0:0:1"))
        self.assertTrue(network.is_ipv6("::1"))
        self.assertTrue(network.is_ipv6("::"))
        self.assertTrue(network.is_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334"))
        self.assertTrue(network.is_ipv6("2001:0db8:85a3::8a2e:0370:7334"))
        self.assertFalse(network.is_ipv6("2001:0db8:0370:7334"))
        self.assertFalse(network.is_ipv6("2001:0db8:::0370:7334"))
        self.assertFalse(network.is_ipv6("10.0.1.2"))
        self.assertFalse(network.is_ipv6("2001.0db8.85a3.0000.0000.8a2e.0370.7334"))
        # Check 16-char-long unicode string
        # https://github.com/saltstack/salt/issues/51258
        self.assertFalse(network.is_ipv6("sixteen-char-str"))

    def test_ipv6(self):
        self.assertTrue(network.ipv6("2001:db8:0:1:1:1:1:1"))
        self.assertTrue(network.ipv6("0:0:0:0:0:0:0:1"))
        self.assertTrue(network.ipv6("::1"))
        self.assertTrue(network.ipv6("::"))
        self.assertTrue(network.ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:7334"))
        self.assertTrue(network.ipv6("2001:0db8:85a3::8a2e:0370:7334"))
        self.assertTrue(network.ipv6("2001:67c:2e8::/48"))

    def test_parse_host_port(self):
        _ip = ipaddress.ip_address
        good_host_ports = {
            "10.10.0.3": (_ip("10.10.0.3").compressed, None),
            "10.10.0.3:1234": (_ip("10.10.0.3").compressed, 1234),
            "2001:0db8:85a3::8a2e:0370:7334": (
                _ip("2001:0db8:85a3::8a2e:0370:7334").compressed,
                None,
            ),
            "[2001:0db8:85a3::8a2e:0370:7334]:1234": (
                _ip("2001:0db8:85a3::8a2e:0370:7334").compressed,
                1234,
            ),
            "2001:0db8:85a3::7334": (_ip("2001:0db8:85a3::7334").compressed, None),
            "[2001:0db8:85a3::7334]:1234": (
                _ip("2001:0db8:85a3::7334").compressed,
                1234,
            ),
        }
        bad_host_ports = [
            "10.10.0.3/24",
            "10.10.0.3::1234",
            "2001:0db8:0370:7334",
            "2001:0db8:0370::7334]:1234",
            "2001:0db8:0370:0:a:b:c:d:1234",
        ]
        for host_port, assertion_value in good_host_ports.items():
            host = port = None
            host, port = network.parse_host_port(host_port)
            self.assertEqual((host, port), assertion_value)

        for host_port in bad_host_ports:
            try:
                self.assertRaises(ValueError, network.parse_host_port, host_port)
            except AssertionError as _e_:
                log.error(
                    'bad host_port value: "%s" failed to trigger ValueError exception',
                    host_port,
                )
                raise _e_

    def test_dns_check(self):
        hosts = [
            {
                "host": "10.10.0.3",
                "port": "",
                "mocked": [(2, 1, 6, "", ("10.10.0.3", 0))],
                "ret": "10.10.0.3",
            },
            {
                "host": "10.10.0.3",
                "port": "1234",
                "mocked": [(2, 1, 6, "", ("10.10.0.3", 0))],
                "ret": "10.10.0.3",
            },
            {
                "host": "2001:0db8:85a3::8a2e:0370:7334",
                "port": "",
                "mocked": [(10, 1, 6, "", ("2001:db8:85a3::8a2e:370:7334", 0, 0, 0))],
                "ret": "[2001:db8:85a3::8a2e:370:7334]",
            },
            {
                "host": "2001:0db8:85a3::8a2e:370:7334",
                "port": "1234",
                "mocked": [(10, 1, 6, "", ("2001:db8:85a3::8a2e:370:7334", 0, 0, 0))],
                "ret": "[2001:db8:85a3::8a2e:370:7334]",
            },
            {
                "host": "salt-master",
                "port": "1234",
                "mocked": [(2, 1, 6, "", ("127.0.0.1", 0))],
                "ret": "127.0.0.1",
            },
        ]
        for host in hosts:
            with patch.object(
                socket,
                "getaddrinfo",
                create_autospec(socket.getaddrinfo, return_value=host["mocked"]),
            ):
                with patch("socket.socket", create_autospec(socket.socket)):
                    ret = network.dns_check(host["host"], host["port"])
                    self.assertEqual(ret, host["ret"])

    def test_dns_check_ipv6_filter(self):
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
                with self.assertRaises(Exception):
                    network.dns_check("foo", "1", ipv6=ipv6)
                getaddrinfo.assert_called_with("foo", "1", param, socket.SOCK_STREAM)

    def test_dns_check_errors(self):
        with patch.object(
            socket, "getaddrinfo", create_autospec(socket.getaddrinfo, return_value=[])
        ):
            with self.assertRaisesRegex(
                salt.exceptions.SaltSystemExit,
                "DNS lookup or connection check of 'foo' failed",
            ):
                network.dns_check("foo", "1")

        with patch.object(
            socket,
            "getaddrinfo",
            create_autospec(socket.getaddrinfo, side_effect=TypeError),
        ):
            with self.assertRaisesRegex(
                salt.exceptions.SaltSystemExit, "Invalid or unresolveable address"
            ):
                network.dns_check("foo", "1")

    def test_test_addrs(self):
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
            self.assertTrue(len(addrs) == 1)
            self.assertTrue(addrs[0] == addrinfo[0][4][0])

            # the first lookup fails, succeeds on next check
            s.side_effect = [socket.error, MagicMock()]
            addrs = network._test_addrs(addrinfo, 80)
            self.assertTrue(len(addrs) == 1)
            self.assertTrue(addrs[0] == addrinfo[2][4][0])

            # nothing can connect, but we've eliminated duplicates
            s.side_effect = socket.error
            addrs = network._test_addrs(addrinfo, 80)
            self.assertTrue(len(addrs) == 5)

    def test_is_subnet(self):
        for subnet_data in (IPV4_SUBNETS, IPV6_SUBNETS):
            for item in subnet_data[True]:
                log.debug("Testing that %s is a valid subnet", item)
                self.assertTrue(network.is_subnet(item))
            for item in subnet_data[False]:
                log.debug("Testing that %s is not a valid subnet", item)
                self.assertFalse(network.is_subnet(item))

    def test_is_ipv4_subnet(self):
        for item in IPV4_SUBNETS[True]:
            log.debug("Testing that %s is a valid subnet", item)
            self.assertTrue(network.is_ipv4_subnet(item))
        for item in IPV4_SUBNETS[False]:
            log.debug("Testing that %s is not a valid subnet", item)
            self.assertFalse(network.is_ipv4_subnet(item))

    def test_is_ipv6_subnet(self):
        for item in IPV6_SUBNETS[True]:
            log.debug("Testing that %s is a valid subnet", item)
            self.assertTrue(network.is_ipv6_subnet(item))
        for item in IPV6_SUBNETS[False]:
            log.debug("Testing that %s is not a valid subnet", item)
            self.assertFalse(network.is_ipv6_subnet(item))

    def test_cidr_to_ipv4_netmask(self):
        self.assertEqual(network.cidr_to_ipv4_netmask(24), "255.255.255.0")
        self.assertEqual(network.cidr_to_ipv4_netmask(21), "255.255.248.0")
        self.assertEqual(network.cidr_to_ipv4_netmask(17), "255.255.128.0")
        self.assertEqual(network.cidr_to_ipv4_netmask(9), "255.128.0.0")
        self.assertEqual(network.cidr_to_ipv4_netmask(36), "")
        self.assertEqual(network.cidr_to_ipv4_netmask("lol"), "")

    def test_number_of_set_bits_to_ipv4_netmask(self):
        set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xFFFFFF00)
        self.assertEqual(set_bits_to_netmask, "255.255.255.0")
        set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xFFFF6400)

    def test_hex2ip(self):
        self.assertEqual(network.hex2ip("0x4A7D2B63"), "74.125.43.99")
        self.assertEqual(network.hex2ip("0x4A7D2B63", invert=True), "99.43.125.74")
        self.assertEqual(
            network.hex2ip("00000000000000000000FFFF7F000001"), "127.0.0.1"
        )
        self.assertEqual(
            network.hex2ip("0000000000000000FFFF00000100007F", invert=True), "127.0.0.1"
        )
        self.assertEqual(
            network.hex2ip("20010DB8000000000000000000000000"), "2001:db8::"
        )
        self.assertEqual(
            network.hex2ip("B80D0120000000000000000000000000", invert=True),
            "2001:db8::",
        )

    def test_interfaces_ifconfig_linux(self):
        interfaces = network._interfaces_ifconfig(LINUX)
        self.assertEqual(
            interfaces,
            {
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
            },
        )

    def test_interfaces_ifconfig_freebsd(self):
        interfaces = network._interfaces_ifconfig(FREEBSD)
        self.assertEqual(
            interfaces,
            {
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
            },
        )

    def test_interfaces_ifconfig_solaris(self):
        with patch("salt.utils.platform.is_sunos", lambda: True):
            interfaces = network._interfaces_ifconfig(SOLARIS)
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
                    "inet6": [
                        {"prefixlen": "10", "address": "fe80::221:9bff:fefd:2a22"}
                    ],
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
            self.assertEqual(interfaces, expected_interfaces)

    def test_interfaces_ifconfig_netbsd(self):
        interfaces = network._netbsd_interfaces_ifconfig(NETBSD)
        self.assertEqual(
            interfaces,
            {
                "lo0": {
                    "inet": [{"address": "127.0.0.1", "netmask": "255.0.0.0"}],
                    "inet6": [
                        {"address": "fe80::1", "prefixlen": "64", "scope": "lo0"}
                    ],
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
            },
        )

    def test_freebsd_remotes_on(self):
        with patch("salt.utils.platform.is_sunos", lambda: False):
            with patch("salt.utils.platform.is_freebsd", lambda: True):
                with patch("subprocess.check_output", return_value=FREEBSD_SOCKSTAT):
                    remotes = network._freebsd_remotes_on("4506", "remote")
                    self.assertEqual(remotes, set(["127.0.0.1"]))

    def test_freebsd_remotes_on_with_fat_pid(self):
        with patch("salt.utils.platform.is_sunos", lambda: False):
            with patch("salt.utils.platform.is_freebsd", lambda: True):
                with patch(
                    "subprocess.check_output",
                    return_value=FREEBSD_SOCKSTAT_WITH_FAT_PID,
                ):
                    remotes = network._freebsd_remotes_on("4506", "remote")
                    self.assertEqual(remotes, set(["127.0.0.1"]))

    def test_netlink_tool_remote_on_a(self):
        with patch("salt.utils.platform.is_sunos", lambda: False):
            with patch("salt.utils.platform.is_linux", lambda: True):
                with patch(
                    "subprocess.check_output", return_value=LINUX_NETLINK_SS_OUTPUT
                ):
                    remotes = network._netlink_tool_remote_on("4506", "local")
                    self.assertEqual(
                        remotes, set(["192.168.122.177", "::ffff:127.0.0.1"])
                    )

    def test_netlink_tool_remote_on_b(self):
        with patch("subprocess.check_output", return_value=NETLINK_SS):
            remotes = network._netlink_tool_remote_on("4505", "remote_port")
            self.assertEqual(remotes, set(["127.0.0.1", "::ffff:1.2.3.4"]))

    def test_generate_minion_id_distinct(self):
        """
        Test if minion IDs are distinct in the pool.

        :return:
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
            self.assertEqual(
                network._generate_minion_id(),
                [
                    "hostname.domainname.blank",
                    "nodename",
                    "hostname",
                    "1.2.3.4",
                    "5.6.7.8",
                ],
            )

    def test_generate_minion_id_127_name(self):
        """
        Test if minion IDs can be named 127.foo

        :return:
        """
        with patch("platform.node", MagicMock(return_value="127")), patch(
            "socket.gethostname", MagicMock(return_value="127")
        ), patch(
            "socket.getfqdn", MagicMock(return_value="127.domainname.blank")
        ), patch(
            "socket.getaddrinfo",
            MagicMock(return_value=[(2, 3, 0, "attrname", ("127.0.1.1", 0))]),
        ), patch(
            "salt.utils.files.fopen", mock_open()
        ), patch(
            "salt.utils.network.ip_addrs",
            MagicMock(return_value=["1.2.3.4", "5.6.7.8"]),
        ):
            self.assertEqual(
                network._generate_minion_id(),
                ["127.domainname.blank", "127", "1.2.3.4", "5.6.7.8"],
            )

    def test_generate_minion_id_127_name_startswith(self):
        """
        Test if minion IDs can be named starting from "127"

        :return:
        """
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
            self.assertEqual(
                network._generate_minion_id(),
                ["127890.domainname.blank", "127890", "1.2.3.4", "5.6.7.8"],
            )

    def test_generate_minion_id_duplicate(self):
        """
        Test if IP addresses in the minion IDs are distinct in the pool

        :return:
        """
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
            self.assertEqual(network._generate_minion_id(), ["hostname", "1.2.3.4"])

    def test_generate_minion_id_platform_used(self):
        """
        Test if platform.node is used for the first occurrence.
        The platform.node is most common hostname resolver before anything else.

        :return:
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
            self.assertEqual(
                network.generate_minion_id(), "very.long.and.complex.domain.name"
            )

    def test_generate_minion_id_platform_localhost_filtered(self):
        """
        Test if localhost is filtered from the first occurrence.

        :return:
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
            self.assertEqual(network.generate_minion_id(), "hostname.domainname.blank")

    def test_generate_minion_id_platform_localhost_filtered_all(self):
        """
        Test if any of the localhost is filtered from everywhere.

        :return:
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
            MagicMock(
                return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1", "1.2.3.4"]
            ),
        ):
            self.assertEqual(network.generate_minion_id(), "1.2.3.4")

    def test_generate_minion_id_platform_localhost_only(self):
        """
        Test if there is no other choice but localhost.

        :return:
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
            self.assertEqual(network.generate_minion_id(), "localhost")

    def test_generate_minion_id_platform_fqdn(self):
        """
        Test if fqdn is picked up.

        :return:
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
            self.assertEqual(network.generate_minion_id(), "pick.me")

    def test_generate_minion_id_platform_localhost_addrinfo(self):
        """
        Test if addinfo is picked up.

        :return:
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
            self.assertEqual(network.generate_minion_id(), "pick.me")

    def test_generate_minion_id_platform_ip_addr_only(self):
        """
        Test if IP address is the only what is used as a Minion ID in case no DNS name.

        :return:
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
            MagicMock(
                return_value=["127.0.0.1", "::1", "fe00::0", "fe02::1", "1.2.3.4"]
            ),
        ):
            self.assertEqual(network.generate_minion_id(), "1.2.3.4")

    def test_gen_mac(self):
        with patch("random.randint", return_value=1) as random_mock:
            self.assertEqual(random_mock.return_value, 1)
            ret = network.gen_mac("00:16:3E")
            expected_mac = "00:16:3E:01:01:01"
            self.assertEqual(ret, expected_mac)

    def test_mac_str_to_bytes(self):
        self.assertRaises(ValueError, network.mac_str_to_bytes, "31337")
        self.assertRaises(ValueError, network.mac_str_to_bytes, "0001020304056")
        self.assertRaises(ValueError, network.mac_str_to_bytes, "00:01:02:03:04:056")
        self.assertRaises(ValueError, network.mac_str_to_bytes, "a0:b0:c0:d0:e0:fg")
        self.assertEqual(
            b"\x10\x08\x06\x04\x02\x00", network.mac_str_to_bytes("100806040200")
        )
        self.assertEqual(
            b"\xf8\xe7\xd6\xc5\xb4\xa3", network.mac_str_to_bytes("f8e7d6c5b4a3")
        )

    def test_generate_minion_id_with_long_hostname(self):
        """
        Validate the fix for:

        https://github.com/saltstack/salt/issues/51160
        """
        long_name = "localhost-abcdefghijklmnopqrstuvwxyz-abcdefghijklmnopqrstuvwxyz"
        with patch("socket.gethostname", MagicMock(return_value=long_name)):
            # An exception is raised if unicode is passed to socket.getfqdn
            minion_id = network.generate_minion_id()
        assert minion_id != "", minion_id
