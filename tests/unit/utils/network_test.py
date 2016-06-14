# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch
ensure_in_syspath('../../')

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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkTestCase(TestCase):

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
            self.assertEqual(interfaces,
                             {'ilbext0': {'inet': [{'address': '10.10.11.11',
                                                    'broadcast': '10.10.11.31',
                                                    'netmask': '255.255.255.224'}],
                                          'inet6': [{'address': '::',
                                                     'prefixlen': '0'}],
                                          'up': True},
                              'ilbint0': {'inet': [{'address': '10.6.0.11',
                                                    'broadcast': '10.6.0.255',
                                                    'netmask': '255.255.255.0'}],
                                          'inet6': [{'address': '::',
                                                     'prefixlen': '0'}],
                                          'up': True},
                              'lo0': {'inet': [{'address': '127.0.0.1',
                                                'netmask': '255.0.0.0'}],
                                      'inet6': [{'address': '::1',
                                                 'prefixlen': '128'}],
                                      'up': True},
                              'net0': {'inet': [{'address': '10.10.10.38',
                                                 'broadcast': '10.10.10.63',
                                                 'netmask': '255.255.255.224'}],
                                       'inet6': [{'address': 'fe80::221:9bff:fefd:2a22',
                                                  'prefixlen': '10'}],
                                       'up': True},
                              'vpn0': {'inet': [{'address': '10.6.0.14',
                                                 'netmask': '255.0.0.0'}],
                                       'inet6': [{'address': '::',
                                                  'prefixlen': '0'}],
                                       'up': True}}
            )

    def test_freebsd_remotes_on(self):
        with patch('salt.utils.is_sunos', lambda: False):
            with patch('salt.utils.is_freebsd', lambda: True):
                with patch('subprocess.check_output',
                           return_value=FREEBSD_SOCKSTAT):
                    remotes = network._freebsd_remotes_on('4506', 'remote')
                    self.assertEqual(remotes, set(['127.0.0.1']))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetworkTestCase, needs_daemon=False)
