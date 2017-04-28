# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf
from tests.support.unit import TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

# Import salt libs
from salt.utils import network

LINUX = '''\
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
'''

FREEBSD = '''
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
'''

SOLARIS = '''\
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
'''

FREEBSD_SOCKSTAT = '''\
USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506
'''

FREEBSD_SOCKSTAT_WITH_FAT_PID = '''\
USER     COMMAND    PID   FD PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
salt-master python2.781106 35 tcp4  127.0.0.1:61115  127.0.0.1:4506
'''


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkTestCase(TestCase):

    def test_sanitize_host(self):
        ret = network.sanitize_host('10.1./2.$3')
        self.assertEqual(ret, '10.1.2.3')

    def test_host_to_ips(self):
        ret = network.host_to_ips('www.saltstack.com')
        self.assertEqual(ret, ['104.199.122.13'])

    def test_generate_minion_id(self):
        self.assertTrue(network.generate_minion_id())

    def test_is_ip(self):
        self.assertTrue(network.is_ip('10.10.0.3'))
        self.assertFalse(network.is_ip('0.9.800.1000'))

    def test_is_ipv4(self):
        self.assertTrue(network.is_ipv4('10.10.0.3'))
        self.assertFalse(network.is_ipv4('10.100.1'))
        self.assertFalse(network.is_ipv4('2001:db8:0:1:1:1:1:1'))

    def test_is_ipv6(self):
        self.assertTrue(network.is_ipv6('2001:db8:0:1:1:1:1:1'))
        self.assertTrue(network.is_ipv6('0:0:0:0:0:0:0:1'))
        self.assertTrue(network.is_ipv6('::1'))
        self.assertTrue(network.is_ipv6('::'))
        self.assertTrue(network.is_ipv6('2001:0db8:85a3:0000:0000:8a2e:0370:7334'))
        self.assertTrue(network.is_ipv6('2001:0db8:85a3::8a2e:0370:7334'))
        self.assertFalse(network.is_ipv6('2001:0db8:0370:7334'))
        self.assertFalse(network.is_ipv6('2001:0db8:::0370:7334'))
        self.assertFalse(network.is_ipv6('10.0.1.2'))
        self.assertFalse(network.is_ipv6('2001.0db8.85a3.0000.0000.8a2e.0370.7334'))

    def test_cidr_to_ipv4_netmask(self):
        self.assertEqual(network.cidr_to_ipv4_netmask(24), '255.255.255.0')
        self.assertEqual(network.cidr_to_ipv4_netmask(21), '255.255.248.0')
        self.assertEqual(network.cidr_to_ipv4_netmask(17), '255.255.128.0')
        self.assertEqual(network.cidr_to_ipv4_netmask(9), '255.128.0.0')
        self.assertEqual(network.cidr_to_ipv4_netmask(36), '')
        self.assertEqual(network.cidr_to_ipv4_netmask('lol'), '')

    def test_number_of_set_bits_to_ipv4_netmask(self):
        set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xffffff00)
        self.assertEqual(set_bits_to_netmask, '255.255.255.0')
        set_bits_to_netmask = network._number_of_set_bits_to_ipv4_netmask(0xffff6400)

    def test_hex2ip(self):
        self.assertEqual(network.hex2ip('0x4A7D2B63'), '74.125.43.99')
        self.assertEqual(network.hex2ip('0x4A7D2B63', invert=True), '99.43.125.74')

    def test_interfaces_ifconfig_linux(self):
        interfaces = network._interfaces_ifconfig(LINUX)
        self.assertEqual(interfaces,
                         {'eth0': {'hwaddr': 'e0:3f:49:85:6a:af',
                                   'inet': [{'address': '10.10.10.56',
                                             'broadcast': '10.10.10.255',
                                             'netmask': '255.255.252.0'}],
                                   'inet6': [{'address': 'fe80::e23f:49ff:fe85:6aaf',
                                              'prefixlen': '64',
                                              'scope': 'link'}],
                                   'up': True},
                          'lo': {'inet': [{'address': '127.0.0.1',
                                           'netmask': '255.0.0.0'}],
                                 'inet6': [{'address': '::1',
                                            'prefixlen': '128',
                                            'scope': 'host'}],
                                 'up': True}}
        )

    def test_interfaces_ifconfig_freebsd(self):
        interfaces = network._interfaces_ifconfig(FREEBSD)
        self.assertEqual(interfaces,
                         {'': {'up': False},
                          'em0': {'hwaddr': '00:30:48:ff:ff:ff',
                                  'inet': [{'address': '10.10.10.250',
                                            'broadcast': '10.10.10.255',
                                            'netmask': '255.255.255.224'},
                                           {'address': '10.10.10.56',
                                            'broadcast': '10.10.10.63',
                                            'netmask': '255.255.255.192'}],
                                  'up': True},
                          'em1': {'hwaddr': '00:30:48:aa:aa:aa',
                                  'up': False},
                          'lo0': {'inet': [{'address': '127.0.0.1',
                                            'netmask': '255.0.0.0'}],
                                  'inet6': [{'address': 'fe80::1',
                                             'prefixlen': '64',
                                             'scope': '0x8'},
                                            {'address': '::1',
                                             'prefixlen': '128',
                                             'scope': None}],
                                  'up': True},
                          'plip0': {'up': False},
                          'tun0': {'inet': [{'address': '10.12.0.1',
                                             'netmask': '255.255.255.255'}],
                                   'up': True}}

        )

    def test_interfaces_ifconfig_solaris(self):
        with patch('salt.utils.is_sunos', lambda: True):
            interfaces = network._interfaces_ifconfig(SOLARIS)
            expected_interfaces = {'ilbint0':
                                       {'inet6': [],
                                        'inet': [{'broadcast': '10.6.0.255',
                                                  'netmask': '255.255.255.0',
                                                  'address': '10.6.0.11'}],
                                        'up': True},
                                   'lo0':
                                       {'inet6': [{'prefixlen': '128',
                                                   'address': '::1'}],
                                       'inet': [{'netmask': '255.0.0.0',
                                                 'address': '127.0.0.1'}],
                                        'up': True},
                                   'ilbext0': {'inet6': [],
                                               'inet': [{'broadcast': '10.10.11.31',
                                                         'netmask': '255.255.255.224',
                                                         'address': '10.10.11.11'},
                                                        {'broadcast': '10.10.11.31',
                                                         'netmask': '255.255.255.224',
                                                         'address': '10.10.11.12'}],
                                               'up': True},
                                   'vpn0': {'inet6': [],
                                            'inet': [{'netmask': '255.0.0.0',
                                                      'address': '10.6.0.14'}],
                                            'up': True},
                                   'net0': {'inet6': [{'prefixlen': '10',
                                                       'address': 'fe80::221:9bff:fefd:2a22'}],
                                   'inet': [{'broadcast': '10.10.10.63',
                                             'netmask': '255.255.255.224',
                                             'address': '10.10.10.38'}],
                                            'up': True}}
            self.assertEqual(interfaces, expected_interfaces)

    def test_freebsd_remotes_on(self):
        with patch('salt.utils.is_sunos', lambda: False):
            with patch('salt.utils.is_freebsd', lambda: True):
                with patch('subprocess.check_output',
                           return_value=FREEBSD_SOCKSTAT):
                    remotes = network._freebsd_remotes_on('4506', 'remote')
                    self.assertEqual(remotes, set(['127.0.0.1']))

    def test_freebsd_remotes_on_with_fat_pid(self):
        with patch('salt.utils.is_sunos', lambda: False):
            with patch('salt.utils.is_freebsd', lambda: True):
                with patch('subprocess.check_output',
                           return_value=FREEBSD_SOCKSTAT_WITH_FAT_PID):
                    remotes = network._freebsd_remotes_on('4506', 'remote')
                    self.assertEqual(remotes, set(['127.0.0.1']))

    def test_generate_minion_id_distinct(self):
        '''
        Test if minion IDs are distinct in the pool.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='nodename')), \
                patch('socket.gethostname', MagicMock(return_value='hostname')), \
                patch('socket.getfqdn', MagicMock(return_value='hostname.domainname.blank')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'attrname', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4', '5.6.7.8'])):
            self.assertEqual(network._generate_minion_id(),
                             ['hostname.domainname.blank', 'nodename', 'hostname', '1.2.3.4', '5.6.7.8'])

    def test_generate_minion_id_duplicate(self):
        '''
        Test if IP addresses in the minion IDs are distinct in the pool

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='hostname')), \
                patch('socket.gethostname', MagicMock(return_value='hostname')), \
                patch('socket.getfqdn', MagicMock(return_value='hostname')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'hostname', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4', '1.2.3.4', '1.2.3.4'])):
            self.assertEqual(network._generate_minion_id(), ['hostname', '1.2.3.4'])

    def test_generate_minion_id_platform_used(self):
        '''
        Test if platform.node is used for the first occurrence.
        The platform.node is most common hostname resolver before anything else.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='very.long.and.complex.domain.name')), \
                patch('socket.gethostname', MagicMock(return_value='hostname')), \
                patch('socket.getfqdn', MagicMock(return_value='')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'hostname', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4', '1.2.3.4', '1.2.3.4'])):
            self.assertEqual(network.generate_minion_id(), 'very.long.and.complex.domain.name')

    def test_generate_minion_id_platform_localhost_filtered(self):
        '''
        Test if localhost is filtered from the first occurrence.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='pick.me')), \
                patch('socket.getfqdn', MagicMock(return_value='hostname.domainname.blank')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'hostname', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['1.2.3.4', '1.2.3.4', '1.2.3.4'])):
            self.assertEqual(network.generate_minion_id(), 'hostname.domainname.blank')

    def test_generate_minion_id_platform_localhost_filtered_all(self):
        '''
        Test if any of the localhost is filtered from everywhere.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='ip6-loopback')), \
                patch('socket.getfqdn', MagicMock(return_value='ip6-localhost')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'localhost', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['127.0.0.1', '::1', 'fe00::0', 'fe02::1', '1.2.3.4'])):
            self.assertEqual(network.generate_minion_id(), '1.2.3.4')

    def test_generate_minion_id_platform_localhost_only(self):
        '''
        Test if there is no other choice but localhost.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='ip6-loopback')), \
                patch('socket.getfqdn', MagicMock(return_value='ip6-localhost')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'localhost', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['127.0.0.1', '::1', 'fe00::0', 'fe02::1'])):
            self.assertEqual(network.generate_minion_id(), 'localhost')

    def test_generate_minion_id_platform_fqdn(self):
        '''
        Test if fqdn is picked up.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='ip6-loopback')), \
                patch('socket.getfqdn', MagicMock(return_value='pick.me')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'localhost', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['127.0.0.1', '::1', 'fe00::0', 'fe02::1'])):
            self.assertEqual(network.generate_minion_id(), 'pick.me')

    def test_generate_minion_id_platform_localhost_addrinfo(self):
        '''
        Test if addinfo is picked up.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='ip6-loopback')), \
                patch('socket.getfqdn', MagicMock(return_value='ip6-localhost')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'pick.me', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['127.0.0.1', '::1', 'fe00::0', 'fe02::1'])):
            self.assertEqual(network.generate_minion_id(), 'pick.me')

    def test_generate_minion_id_platform_ip_addr_only(self):
        '''
        Test if IP address is the only what is used as a Minion ID in case no DNS name.

        :return:
        '''
        with patch('platform.node', MagicMock(return_value='localhost')), \
                patch('socket.gethostname', MagicMock(return_value='ip6-loopback')), \
                patch('socket.getfqdn', MagicMock(return_value='ip6-localhost')), \
                patch('socket.getaddrinfo', MagicMock(return_value=[(2, 3, 0, 'localhost', ('127.0.1.1', 0))])), \
                patch('salt.utils.fopen', MagicMock(return_value=False)), \
                patch('os.path.exists', MagicMock(return_value=False)), \
                patch('salt.utils.network.ip_addrs', MagicMock(return_value=['127.0.0.1', '::1', 'fe00::0', 'fe02::1', '1.2.3.4'])):
            self.assertEqual(network.generate_minion_id(), '1.2.3.4')
