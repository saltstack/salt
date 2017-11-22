# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

from functools import wraps

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)


# Test data
TEST_FACTS = {
    '__opts__': {},
    'OPTIONAL_ARGS': {},
    'uptime': 'Forever',
    'UP': True,
    'HOSTNAME': 'test-device.com'
}

TEST_ENVIRONMENT = {
    'hot': 'yes'
}

TEST_COMMAND_RESPONSE = {
    'show run': 'all the command output'
}

TEST_TRACEROUTE_RESPONSE = {
    'success': {
        1: {
            'probes': {
                1: {
                    'rtt': 1.123,
                    'ip_address': u'206.223.116.21',
                    'host_name': u'eqixsj-google-gige.google.com'
                }
            }
        }
    }
}

TEST_PING_RESPONSE = {
    'success': {
        'probes_sent': 5,
        'packet_loss': 0,
        'rtt_min': 72.158,
        'rtt_max': 72.433,
        'rtt_avg': 72.268,
        'rtt_stddev': 0.094,
        'results': [
            {
                'ip_address': '1.1.1.1',
                'rtt': 72.248
            }
        ]
    }
}

TEST_ARP_TABLE = [
    {
        'interface': 'MgmtEth0/RSP0/CPU0/0',
        'mac': '5C:5E:AB:DA:3C:F0',
        'ip': '172.17.17.1',
        'age': 1454496274.84
    }
]

TEST_IPADDRS = {
    'FastEthernet8': {
        'ipv4': {
            '10.66.43.169': {
                'prefix_length': 22
            }
        }
    }
}

TEST_INTERFACES = {
    'Management1': {
        'is_up': False,
        'is_enabled': False,
        'description': u'',
        'last_flapped': -1,
        'speed': 1000,
        'mac_address': u'dead:beef:dead',
    }
}

TEST_LLDP_NEIGHBORS = {
    u'Ethernet2':
        [
            {
                'hostname': u'junos-unittest',
                'port': u'520',
            }
        ]
}

TEST_MAC_TABLE = [
    {
        'mac': '00:1C:58:29:4A:71',
        'interface': 'Ethernet47',
        'vlan': 100,
        'static': False,
        'active': True,
        'moves': 1,
        'last_move': 1454417742.58
    }
]

TEST_RUNNING_CONFIG = {
    'one': 'two'
}

TEST_OPTICS = {
    'et1': {
        'physical_channels': {
            'channel': [
                {
                    'index': 0,
                    'state': {
                        'input_power': {
                            'instant': 0.0,
                            'avg': 0.0,
                            'min': 0.0,
                            'max': 0.0,
                        },
                        'output_power': {
                            'instant': 0.0,
                            'avg': 0.0,
                            'min': 0.0,
                            'max': 0.0,
                        },
                        'laser_bias_current': {
                            'instant': 0.0,
                            'avg': 0.0,
                            'min': 0.0,
                            'max': 0.0,
                        },
                    }
                }
            ]
        }
    }
}


class MockNapalmDevice(object):
    '''Setup a mock device for our tests'''
    def get_facts(self):
        return TEST_FACTS

    def get_environment(self):
        return TEST_ENVIRONMENT

    def get_arp_table(self):
        return TEST_ARP_TABLE

    def get(self, key, default=None, *args, **kwargs):
        try:
            if key == 'DRIVER':
                return self
            return TEST_FACTS[key]
        except KeyError:
            return default

    def cli(self, commands, *args, **kwargs):
        assert commands[0] == 'show run'
        return TEST_COMMAND_RESPONSE

    def traceroute(self, destination, **kwargs):
        assert destination == 'destination.com'
        return TEST_TRACEROUTE_RESPONSE

    def ping(self, destination, **kwargs):
        assert destination == 'destination.com'
        return TEST_PING_RESPONSE

    def get_config(self, retrieve='all'):
        assert retrieve == 'running'
        return TEST_RUNNING_CONFIG

    def get_interfaces_ip(self, **kwargs):
        return TEST_IPADDRS

    def get_interfaces(self, **kwargs):
        return TEST_INTERFACES

    def get_lldp_neighbors_detail(self, **kwargs):
        return TEST_LLDP_NEIGHBORS

    def get_mac_address_table(self, **kwargs):
        return TEST_MAC_TABLE

    def get_optics(self, **kwargs):
        return TEST_OPTICS

    def load_merge_candidate(self, filename=None, config=None):
        assert config == 'new config'
        return TEST_RUNNING_CONFIG

    def load_replace_candidate(self, filename=None, config=None):
        assert config == 'new config'
        return TEST_RUNNING_CONFIG

    def commit_config(self, **kwargs):
        return TEST_RUNNING_CONFIG

    def discard_config(self, **kwargs):
        return TEST_RUNNING_CONFIG

    def compare_config(self, **kwargs):
        return TEST_RUNNING_CONFIG

    def rollback(self, **kwargs):
        return TEST_RUNNING_CONFIG


def mock_proxy_napalm_wrap(func):
    '''
    The proper decorator checks for proxy minions. We don't care
    so just pass back to the origination function
    '''

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        func.__globals__['napalm_device'] = MockNapalmDevice()
        return func(*args, **kwargs)
    return func_wrapper


import salt.utils.napalm as napalm_utils  # NOQA
napalm_utils.proxy_napalm_wrap = mock_proxy_napalm_wrap  # pylint: disable=E9502

import salt.modules.napalm_network as napalm_network  # NOQA


def true(name):
    assert name == 'set_ntp_peers'
    return True


def random_hash(source, method):
    return 12346789


def join(*files):
    return True


def get_managed_file(*args, **kwargs):
    return 'True'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmNetworkModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                }),
                'file.file_exists': true,
                'file.join': join,
                'file.get_managed': get_managed_file,
                'random.hash': random_hash
            }
        }

        return {napalm_network: module_globals}

    def test_connected_pass(self):
        ret = napalm_network.connected()
        assert ret['out'] is True

    def test_facts(self):
        ret = napalm_network.facts()
        assert ret['out'] == TEST_FACTS

    def test_environment(self):
        ret = napalm_network.environment()
        assert ret['out'] == TEST_ENVIRONMENT

    def test_cli_single_command(self):
        '''
        Test that CLI works with 1 arg
        '''
        ret = napalm_network.cli("show run")
        assert ret['out'] == TEST_COMMAND_RESPONSE

    def test_cli_multi_command(self):
        '''
        Test that CLI works with 2 arg
        '''
        ret = napalm_network.cli("show run", "show run")
        assert ret['out'] == TEST_COMMAND_RESPONSE

    def test_traceroute(self):
        ret = napalm_network.traceroute('destination.com')
        assert list(ret['out'].keys())[0] == 'success'

    def test_ping(self):
        ret = napalm_network.ping('destination.com')
        assert list(ret['out'].keys())[0] == 'success'

    def test_arp(self):
        ret = napalm_network.arp()
        assert ret['out'] == TEST_ARP_TABLE

    def test_ipaddrs(self):
        ret = napalm_network.ipaddrs()
        assert ret['out'] == TEST_IPADDRS

    def test_interfaces(self):
        ret = napalm_network.interfaces()
        assert ret['out'] == TEST_INTERFACES

    def test_lldp(self):
        ret = napalm_network.lldp()
        assert ret['out'] == TEST_LLDP_NEIGHBORS

    def test_mac(self):
        ret = napalm_network.mac()
        assert ret['out'] == TEST_MAC_TABLE

    def test_config(self):
        ret = napalm_network.config('running')
        assert ret['out'] == TEST_RUNNING_CONFIG

    def test_optics(self):
        ret = napalm_network.optics()
        assert ret['out'] == TEST_OPTICS

    def test_load_config(self):
        ret = napalm_network.load_config(text='new config')
        assert ret['result']

    def test_load_config_replace(self):
        ret = napalm_network.load_config(text='new config', replace=True)
        assert ret['result']

    def test_load_template(self):
        ret = napalm_network.load_template('set_ntp_peers',
                                           peers=['192.168.0.1'])
        assert ret['out'] is None

    def test_commit(self):
        ret = napalm_network.commit()
        assert ret['out'] == TEST_RUNNING_CONFIG

    def test_discard_config(self):
        ret = napalm_network.discard_config()
        assert ret['out'] == TEST_RUNNING_CONFIG

    def test_compare_config(self):
        ret = napalm_network.compare_config()
        assert ret['out'] == TEST_RUNNING_CONFIG

    def test_rollback(self):
        ret = napalm_network.rollback()
        assert ret['out'] == TEST_RUNNING_CONFIG

    def test_config_changed(self):
        ret = napalm_network.config_changed()
        assert ret == (True, '')

    def test_config_control(self):
        ret = napalm_network.config_control()
        assert ret == (True, '')
