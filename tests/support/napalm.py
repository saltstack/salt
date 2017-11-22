# -*- coding: utf-8 -*-
'''
Base classes for napalm unit tests

:codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

from functools import wraps


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

TEST_BGP_CONFIG = {
    'test': 'value'
}

TEST_BGP_NEIGHBORS = {
    'default': {
        8121: [
            {
                'up': True,
                'local_as': 13335,
                'remote_as': 8121,
                'local_address': u'172.101.76.1',
                'local_address_configured': True,
                'local_port': 179,
                'remote_address': u'192.247.78.0',
                'router_id': u'192.168.0.1',
                'remote_port': 58380,
                'multihop': False,
                'import_policy': u'4-NTT-TRANSIT-IN',
                'export_policy': u'4-NTT-TRANSIT-OUT',
                'input_messages': 123,
                'output_messages': 13,
                'input_updates': 123,
                'output_updates': 5,
                'messages_queued_out': 23,
                'connection_state': u'Established',
                'previous_connection_state': u'EstabSync',
                'last_event': u'RecvKeepAlive',
                'suppress_4byte_as': False,
                'local_as_prepend': False,
                'holdtime': 90,
                'configured_holdtime': 90,
                'keepalive': 30,
                'configured_keepalive': 30,
                'active_prefix_count': 132808,
                'received_prefix_count': 566739,
                'accepted_prefix_count': 566479,
                'suppressed_prefix_count': 0,
                'advertise_prefix_count': 0,
                'flap_count': 27
            }
        ]
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

    def get_bgp_config(self, **kwargs):
        return TEST_BGP_CONFIG

    def get_bgp_neighbors_detail(self, neighbor_address=None, **kwargs):
        assert neighbor_address is None or "test_address"
        return TEST_BGP_NEIGHBORS


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
napalm_utils.proxy_napalm_wrap = mock_proxy_napalm_wrap  # NOQA


def true(name):
    assert name == 'set_ntp_peers'
    return True


def random_hash(source, method):
    return 12346789


def join(*files):
    return True


def get_managed_file(*args, **kwargs):
    return 'True'
