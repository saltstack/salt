# -*- coding: utf-8 -*-
"""
Base classes for napalm unit tests

:codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

from __future__ import absolute_import

from functools import wraps

TEST_INTERFACES = {
    "Management1": {
        "is_up": False,
        "is_enabled": False,
        "description": u"",
        "last_flapped": -1,
        "speed": 1000,
        "mac_address": u"dead:beef:dead",
    }
}

# Test data
TEST_FACTS = {
    "__opts__": {},
    "OPTIONAL_ARGS": {},
    "uptime": "Forever",
    "UP": True,
    "HOSTNAME": "test-device.com",
    "hostname": "test-device.com",
    "username": "admin",
    "os_version": "1.2.3",
    "model": "test_model",
    "serial_number": "123456",
    "vendor": "cisco",
    "interface_list": TEST_INTERFACES,
}

TEST_ENVIRONMENT = {"hot": "yes"}

TEST_COMMAND_RESPONSE = {"show run": "all the command output"}

TEST_TRACEROUTE_RESPONSE = {
    "success": {
        1: {
            "probes": {
                1: {
                    "rtt": 1.123,
                    "ip_address": u"206.223.116.21",
                    "host_name": u"eqixsj-google-gige.google.com",
                }
            }
        }
    }
}

TEST_PING_RESPONSE = {
    "success": {
        "probes_sent": 5,
        "packet_loss": 0,
        "rtt_min": 72.158,
        "rtt_max": 72.433,
        "rtt_avg": 72.268,
        "rtt_stddev": 0.094,
        "results": [{"ip_address": "1.1.1.1", "rtt": 72.248}],
    }
}

TEST_ARP_TABLE = [
    {
        "interface": "MgmtEth0/RSP0/CPU0/0",
        "mac": "5C:5E:AB:DA:3C:F0",
        "ip": "172.17.17.1",
        "age": 1454496274.84,
    }
]

TEST_IPADDRS = {"FastEthernet8": {"ipv4": {"10.66.43.169": {"prefix_length": 22}}}}

TEST_INTERFACES = {
    "Management1": {
        "is_up": False,
        "is_enabled": False,
        "description": u"",
        "last_flapped": -1,
        "speed": 1000,
        "mac_address": u"dead:beef:dead",
    }
}

TEST_LLDP_NEIGHBORS = {u"Ethernet2": [{"hostname": u"junos-unittest", "port": u"520"}]}

TEST_MAC_TABLE = [
    {
        "mac": "00:1C:58:29:4A:71",
        "interface": "Ethernet47",
        "vlan": 100,
        "static": False,
        "active": True,
        "moves": 1,
        "last_move": 1454417742.58,
    }
]

TEST_RUNNING_CONFIG = {"one": "two"}

TEST_OPTICS = {
    "et1": {
        "physical_channels": {
            "channel": [
                {
                    "index": 0,
                    "state": {
                        "input_power": {
                            "instant": 0.0,
                            "avg": 0.0,
                            "min": 0.0,
                            "max": 0.0,
                        },
                        "output_power": {
                            "instant": 0.0,
                            "avg": 0.0,
                            "min": 0.0,
                            "max": 0.0,
                        },
                        "laser_bias_current": {
                            "instant": 0.0,
                            "avg": 0.0,
                            "min": 0.0,
                            "max": 0.0,
                        },
                    },
                }
            ]
        }
    }
}

TEST_BGP_CONFIG = {"test": "value"}

TEST_BGP_NEIGHBORS = {
    "default": {
        8121: [
            {
                "up": True,
                "local_as": 13335,
                "remote_as": 8121,
                "local_address": u"172.101.76.1",
                "local_address_configured": True,
                "local_port": 179,
                "remote_address": u"192.247.78.0",
                "router_id": u"192.168.0.1",
                "remote_port": 58380,
                "multihop": False,
                "import_policy": u"4-NTT-TRANSIT-IN",
                "export_policy": u"4-NTT-TRANSIT-OUT",
                "input_messages": 123,
                "output_messages": 13,
                "input_updates": 123,
                "output_updates": 5,
                "messages_queued_out": 23,
                "connection_state": u"Established",
                "previous_connection_state": u"EstabSync",
                "last_event": u"RecvKeepAlive",
                "suppress_4byte_as": False,
                "local_as_prepend": False,
                "holdtime": 90,
                "configured_holdtime": 90,
                "keepalive": 30,
                "configured_keepalive": 30,
                "active_prefix_count": 132808,
                "received_prefix_count": 566739,
                "accepted_prefix_count": 566479,
                "suppressed_prefix_count": 0,
                "advertise_prefix_count": 0,
                "flap_count": 27,
            }
        ]
    }
}

TEST_TERM_CONFIG = {"result": True, "already_configured": False}

TEST_NTP_PEERS = {
    "192.168.0.1": 1,
    "172.17.17.1": 2,
    "172.17.17.2": 3,
    "2400:cb00:6:1024::c71b:840a": 4,
}

TEST_NTP_SERVERS = {
    "192.168.0.1": 1,
    "172.17.17.1": 2,
    "172.17.17.2": 3,
    "2400:cb00:6:1024::c71b:840a": 4,
}

TEST_NTP_STATS = [
    {
        "remote": u"188.114.101.4",
        "referenceid": u"188.114.100.1",
        "synchronized": True,
        "stratum": 4,
        "type": u"-",
        "when": u"107",
        "hostpoll": 256,
        "reachability": 377,
        "delay": 164.228,
        "offset": -13.866,
        "jitter": 2.695,
    }
]

TEST_PROBES_CONFIG = {
    "probe1": {
        "test1": {
            "probe_type": "icmp-ping",
            "target": "192.168.0.1",
            "source": "192.168.0.2",
            "probe_count": 13,
            "test_interval": 3,
        },
        "test2": {
            "probe_type": "http-ping",
            "target": "172.17.17.1",
            "source": "192.17.17.2",
            "probe_count": 5,
            "test_interval": 60,
        },
    }
}

TEST_PROBES_RESULTS = {
    "probe1": {
        "test1": {
            "last_test_min_delay": 63.120,
            "global_test_min_delay": 62.912,
            "current_test_avg_delay": 63.190,
            "global_test_max_delay": 177.349,
            "current_test_max_delay": 63.302,
            "global_test_avg_delay": 63.802,
            "last_test_avg_delay": 63.438,
            "last_test_max_delay": 65.356,
            "probe_type": "icmp-ping",
            "rtt": 63.138,
            "last_test_loss": 0,
            "round_trip_jitter": -59.0,
            "target": "192.168.0.1",
            "source": "192.168.0.2",
            "probe_count": 15,
            "current_test_min_delay": 63.138,
        },
        "test2": {
            "last_test_min_delay": 176.384,
            "global_test_min_delay": 169.226,
            "current_test_avg_delay": 177.098,
            "global_test_max_delay": 292.628,
            "current_test_max_delay": 180.055,
            "global_test_avg_delay": 177.959,
            "last_test_avg_delay": 177.178,
            "last_test_max_delay": 184.671,
            "probe_type": "icmp-ping",
            "rtt": 176.449,
            "last_test_loss": 0,
            "round_trip_jitter": -34.0,
            "target": "172.17.17.1",
            "source": "172.17.17.2",
            "probe_count": 15,
            "current_test_min_delay": 176.402,
        },
    }
}

TEST_ROUTE = {
    "172.16.0.0/25": [
        {
            "protocol": "BGP",
            "last_active": True,
            "current_active": True,
            "age": 1178693,
            "routing_table": "inet.0",
            "next_hop": "192.168.0.11",
            "outgoing_interface": "xe-1/1/1.100",
            "preference": 170,
            "selected_next_hop": False,
            "protocol_attributes": {
                "remote_as": 65001,
                "metric": 5,
                "local_as": 13335,
                "as_path": "",
                "remote_address": "192.168.0.11",
                "metric2": 0,
                "local_preference": 0,
                "communities": ["0:2", "no-export"],
                "preference2": -1,
            },
            "inactive_reason": "",
        },
        {
            "protocol": "BGP",
            "last_active": False,
            "current_active": False,
            "age": 2359429,
            "routing_table": "inet.0",
            "next_hop": "192.168.0.17",
            "outgoing_interface": "xe-1/1/1.100",
            "preference": 170,
            "selected_next_hop": True,
            "protocol_attributes": {
                "remote_as": 65001,
                "metric": 5,
                "local_as": 13335,
                "as_path": "",
                "remote_address": "192.168.0.17",
                "metric2": 0,
                "local_preference": 0,
                "communities": ["0:3", "no-export"],
                "preference2": -1,
            },
            "inactive_reason": "Not Best in its group - Router ID",
        },
    ]
}

TEST_SNMP_INFO = {"test_": "value"}

TEST_USERS = {
    "mircea": {
        "level": 15,
        "password": "$1$0P70xKPa$4jt5/10cBTckk6I/w/",
        "sshkeys": [
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC4pFn+shPwTb2yELO4L7NtQrKOJXNeCl1je\
            l9STXVaGnRAnuc2PXl35vnWmcUq6YbUEcgUTRzzXfmelJKuVJTJIlMXii7h2xkbQp0YZIEs4P\
            8ipwnRBAxFfk/ZcDsdfsdfsdfsdN56ejk345jhk345jk345jk341p3A/9LIL7l6YewLBCwJj6\
            D+fWSJ0/YW+7oH17Fk2HH+tw0L5PcWLHkwA4t60iXn16qDbIk/ze6jv2hDGdCdz7oYQeCE55C\
            CHOHMJWYfN3jcL4s0qv8/u6Ka1FVkV7iMmro7ChThoV/5snI4Ljf2wKqgHH7TfNaCfpU0WvHA\
            nTs8zhOrGScSrtb mircea@master-roshi"
        ],
    }
}


class MockNapalmDevice(object):
    """Setup a mock device for our tests"""

    def get_facts(self):
        return TEST_FACTS

    def get_environment(self):
        return TEST_ENVIRONMENT

    def get_arp_table(self):
        return TEST_ARP_TABLE

    def get(self, key, default=None, *args, **kwargs):
        try:
            if key == "DRIVER":
                return self
            return TEST_FACTS[key]
        except KeyError:
            return default

    def cli(self, commands, *args, **kwargs):
        assert commands[0] == "show run"
        return TEST_COMMAND_RESPONSE

    def traceroute(self, destination, **kwargs):
        assert destination == "destination.com"
        return TEST_TRACEROUTE_RESPONSE

    def ping(self, destination, **kwargs):
        assert destination == "destination.com"
        return TEST_PING_RESPONSE

    def get_config(self, retrieve="all"):
        assert retrieve == "running"
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
        assert config == "new config"
        return TEST_RUNNING_CONFIG

    def load_replace_candidate(self, filename=None, config=None):
        assert config == "new config"
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

    def get_ntp_peers(self, **kwargs):
        return TEST_NTP_PEERS

    def get_ntp_servers(self, **kwargs):
        return TEST_NTP_SERVERS

    def get_ntp_stats(self, **kwargs):
        return TEST_NTP_STATS

    def get_probes_config(self, **kwargs):
        return TEST_PROBES_CONFIG

    def get_probes_results(self, **kwargs):
        return TEST_PROBES_RESULTS

    def get_route_to(self, destination, protocol=None, **kwargs):
        assert destination == "1.2.3.4"
        return TEST_ROUTE

    def get_snmp_information(self, **kwargs):
        return TEST_SNMP_INFO

    def get_users(self, **kwargs):
        return TEST_USERS


def mock_proxy_napalm_wrap(func):
    """
    The proper decorator checks for proxy minions. We don't care
    so just pass back to the origination function
    """

    @wraps(func)
    def func_wrapper(*args, **kwargs):
        func.__globals__["napalm_device"] = MockNapalmDevice()
        return func(*args, **kwargs)

    return func_wrapper


import salt.utils.napalm as napalm_utils  # NOQA

napalm_utils.proxy_napalm_wrap = mock_proxy_napalm_wrap  # NOQA


def true(name):
    return True


def random_hash(source, method):
    return 12346789


def join(*files):
    return True


def get_managed_file(*args, **kwargs):
    return "True"
