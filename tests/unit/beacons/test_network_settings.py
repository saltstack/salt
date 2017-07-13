# coding: utf-8

# Python libs
from __future__ import absolute_import
from collections import namedtuple

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.network_settings as network_settings
from salt.beacons.network_settings import _copy_interfaces_info

import logging
log = logging.getLogger(__name__)

STUB_LAST_STATS = _copy_interfaces_info({'eth0':
                                        {'family': 0, 'txqlen': 1000,
                                         'ipdb_scope': 'system', 'index': 2,
                                         'operstate': 'UP',
                                         'num_tx_queues': 1, 'group': 0,
                                         'carrier_changes': 2,
                                         'ipaddr': ['fe80::4789:8906:f3d5:b0e6/64',
                                                    '172.23.5.21/24'],
                                         'neighbours': [],
                                         'ifname': 'enp0s25',
                                         'promiscuity': 0, 'linkmode': 0,
                                         'broadcast': 'ff:ff:ff:ff:ff:ff',
                                         'address': 'b8:ae:ed:7e:17:3b',
                                         'vlans': [], 'ipdb_priority': 0,
                                         'gso_max_segs': 65535,
                                         'gso_max_size': 65536,
                                         'qdisc':
                                         'pfifo_fast', 'mtu': 1500,
                                         'num_rx_queues': 1, 'carrier': 1,
                                         'flags': 69699, 'ifi_type': 1,
                                         'proto_down': 0, 'ports': []}})

STUB_CURR_STATS = _copy_interfaces_info({'eth0':
                                        {'family': 0, 'txqlen': 1000,
                                         'ipdb_scope': 'system', 'index': 2,
                                         'operstate': 'UP',
                                         'num_tx_queues': 1, 'group': 0,
                                         'carrier_changes': 2,
                                         'ipaddr': ['fe80::4789:8906:f3d5:b0e6/64',
                                                    '172.23.5.21/24'],
                                         'neighbours': [],
                                         'ifname': 'enp0s25',
                                         'promiscuity': 1, 'linkmode': 0,
                                         'broadcast': 'ff:ff:ff:ff:ff:ff',
                                         'address': 'b8:ae:ed:7e:17:3b',
                                         'vlans': [], 'ipdb_priority': 0,
                                         'gso_max_segs': 65535,
                                         'gso_max_size': 65536,
                                         'qdisc':
                                         'pfifo_fast', 'mtu': 1500,
                                         'num_rx_queues': 1, 'carrier': 1,
                                         'flags': 69699, 'ifi_type': 1,
                                         'proto_down': 0, 'ports': []}})


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkInfoBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.network_settings
    '''

    def setup_loader_modules(self):
        return {
            network_settings: {
                '__context__': {},
                '__salt__': {},
                'LAST_STATS': STUB_LAST_STATS,
                'IP.by_name': STUB_CURR_STATS
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = network_settings.validate(config)

        self.assertEqual(ret, (False, 'Configuration for network_settings'
                                      ' beacon must be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = network_settings.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

    def test_network_settings_match(self):
            with patch('pyroute2.IPDB',
                       MagicMock(return_value=STUB_CURR_STATS)):

                config = [{'coalesce': True},
                          {'interfaces': {'eth0': {'ipaddr': '',
                                                   'promiscuity': ''}}}]

                ret = network_settings.validate(config)

                self.assertEqual(ret, (True, 'Valid beacon configuration'))

                _expected_return = []

                ret = network_settings.beacon(config)
                self.assertEqual(ret, _expected_return)
