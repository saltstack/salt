"""
    :codeauthor: Gary T. Giesen <ggiesen@giesen.me>
"""

import pytest

import salt.pillar.netbox as netbox
from tests.support.mock import patch


@pytest.fixture
def default_kwargs():
    return {
        "minion_id": "minion1",
        "pillar": None,
        "api_url": "http://netbox.example.com",
        "api_token": "yeic5oocizei7owuichoesh8ooqu6oob3uWiey9a",
        "api_query_result_limit": 65535,
    }


@pytest.fixture
def headers():
    return {"Authorization": "Token quin1Di5MoRooChaiph3Aenaxais5EeY1gie6eev"}


@pytest.fixture
def device_results():
    return {
        "dict": {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 511,
                    "url": "https://netbox.example.com/api/dcim/devices/511/",
                    "name": "minion1",
                    "display_name": "minion1",
                    "device_type": {
                        "id": 4,
                        "url": "https://netbox.example.com/api/dcim/device-types/4/",
                        "manufacturer": {
                            "id": 1,
                            "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                            "name": "Cisco",
                            "slug": "cisco",
                        },
                        "model": "ISR2901",
                        "slug": "isr2901",
                        "display_name": "Cisco ISR2901",
                    },
                    "device_role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "device",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "serial": "",
                    "asset_tag": None,
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "rack": None,
                    "position": None,
                    "face": None,
                    "parent_device": None,
                    "status": {"value": "active", "label": "Active"},
                    "primary_ip": {
                        "id": 1146,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                        "family": 4,
                        "address": "192.0.2.1/24",
                    },
                    "primary_ip4": {
                        "id": 1146,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                        "family": 4,
                        "address": "192.0.2.1/24",
                    },
                    "primary_ip6": None,
                    "cluster": None,
                    "virtual_chassis": None,
                    "vc_position": None,
                    "vc_priority": None,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:04.171105Z",
                }
            ],
        }
    }


@pytest.fixture
def multiple_device_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 511,
                    "url": "https://netbox.example.com/api/dcim/devices/511/",
                    "name": "minion1",
                    "display_name": "minion1",
                    "device_type": {
                        "id": 4,
                        "url": "https://netbox.example.com/api/dcim/device-types/4/",
                        "manufacturer": {
                            "id": 1,
                            "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                            "name": "Cisco",
                            "slug": "cisco",
                        },
                        "model": "ISR2901",
                        "slug": "isr2901",
                        "display_name": "Cisco ISR2901",
                    },
                    "device_role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "device",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "serial": "",
                    "asset_tag": None,
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "rack": None,
                    "position": None,
                    "face": None,
                    "parent_device": None,
                    "status": {"value": "active", "label": "Active"},
                    "primary_ip": {
                        "id": 1146,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                        "family": 4,
                        "address": "192.0.2.1/24",
                    },
                    "primary_ip4": {
                        "id": 1146,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                        "family": 4,
                        "address": "192.0.2.1/24",
                    },
                    "primary_ip6": None,
                    "cluster": None,
                    "virtual_chassis": None,
                    "vc_position": None,
                    "vc_priority": None,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:04.171105Z",
                },
                {
                    "id": 512,
                    "url": "https://netbox.example.com/api/dcim/devices/512/",
                    "name": "minion2",
                    "display_name": "minion2",
                    "device_type": {
                        "id": 4,
                        "url": "https://netbox.example.com/api/dcim/device-types/4/",
                        "manufacturer": {
                            "id": 1,
                            "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                            "name": "Cisco",
                            "slug": "cisco",
                        },
                        "model": "ISR2901",
                        "slug": "isr2901",
                        "display_name": "Cisco ISR2901",
                    },
                    "device_role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "device",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "serial": "",
                    "asset_tag": None,
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "rack": None,
                    "position": None,
                    "face": None,
                    "parent_device": None,
                    "status": {"value": "active", "label": "Active"},
                    "primary_ip": {
                        "id": 1150,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                        "family": 4,
                        "address": "192.0.2.3/24",
                    },
                    "primary_ip4": {
                        "id": 1150,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                        "family": 4,
                        "address": "192.0.2.3/24",
                    },
                    "primary_ip6": None,
                    "cluster": None,
                    "virtual_chassis": None,
                    "vc_position": None,
                    "vc_priority": None,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:04.171105Z",
                },
            ],
        }
    }


@pytest.fixture
def secondary_device_result():
    return {
        "dict": {
            "id": 512,
            "url": "https://netbox.example.com/api/dcim/devices/512/",
            "name": "minion2",
            "display_name": "minion2",
            "device_type": {
                "id": 4,
                "url": "https://netbox.example.com/api/dcim/device-types/4/",
                "manufacturer": {
                    "id": 1,
                    "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                    "name": "Cisco",
                    "slug": "cisco",
                },
                "model": "ISR2901",
                "slug": "isr2901",
                "display_name": "Cisco ISR2901",
            },
            "device_role": {
                "id": 45,
                "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                "name": "Network",
                "slug": "network",
            },
            "node_type": "device",
            "tenant": None,
            "platform": {
                "id": 1,
                "url": "https://netbox.example.com/api/dcim/platforms/1/",
                "name": "Cisco IOS",
                "slug": "ios",
            },
            "serial": "",
            "asset_tag": None,
            "site": {
                "id": 18,
                "url": "https://netbox.example.com/api/dcim/sites/18/",
                "name": "Site 1",
                "slug": "site1",
            },
            "rack": None,
            "position": None,
            "face": None,
            "parent_device": None,
            "status": {"value": "active", "label": "Active"},
            "primary_ip": {
                "id": 1150,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                "family": 4,
                "address": "192.0.2.3/24",
            },
            "primary_ip4": {
                "id": 1150,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                "family": 4,
                "address": "192.0.2.3/24",
            },
            "primary_ip6": None,
            "cluster": None,
            "virtual_chassis": None,
            "vc_position": None,
            "vc_priority": None,
            "comments": "",
            "local_context_data": None,
            "tags": [],
            "custom_fields": {},
            "config_context": {},
            "created": "2021-02-19",
            "last_updated": "2021-02-19T06:12:04.171105Z",
        }
    }


@pytest.fixture
def virtual_machine_results():
    return {
        "dict": {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 222,
                    "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                    "name": "minion1",
                    "status": {"value": "active", "label": "Active"},
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "cluster": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/virtualization/clusters/1/",
                        "name": "Cluster",
                    },
                    "role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "virtual-machine",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "primary_ip": {
                        "id": 1148,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                        "family": 4,
                        "address": "192.0.2.2/24",
                    },
                    "primary_ip4": {
                        "id": 1148,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                        "family": 4,
                        "address": "192.0.2.2/24",
                    },
                    "primary_ip6": None,
                    "vcpus": 1,
                    "memory": 1024,
                    "disk": 30,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:05.799541Z",
                }
            ],
        }
    }


@pytest.fixture
def multiple_virtual_machine_results():
    return {
        "dict": {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 222,
                    "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                    "name": "minion1",
                    "status": {"value": "active", "label": "Active"},
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "cluster": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/virtualization/clusters/1/",
                        "name": "Cluster",
                    },
                    "role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "virtual-machine",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "primary_ip": {
                        "id": 1148,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                        "family": 4,
                        "address": "192.0.2.2/24",
                    },
                    "primary_ip4": {
                        "id": 1148,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                        "family": 4,
                        "address": "192.0.2.2/24",
                    },
                    "primary_ip6": None,
                    "vcpus": 1,
                    "memory": 1024,
                    "disk": 30,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:05.799541Z",
                },
                {
                    "id": 223,
                    "url": "https://netbox.example.com/api/virtualization/virtual-machines/223/",
                    "name": "minion1",
                    "status": {"value": "active", "label": "Active"},
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "cluster": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/virtualization/clusters/1/",
                        "name": "Cluster",
                    },
                    "role": {
                        "id": 45,
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                        "name": "Network",
                        "slug": "network",
                    },
                    "node_type": "virtual-machine",
                    "tenant": None,
                    "platform": {
                        "id": 1,
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                        "name": "Cisco IOS",
                        "slug": "ios",
                    },
                    "primary_ip": {
                        "id": 1152,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1152/",
                        "family": 4,
                        "address": "192.0.2.4/24",
                    },
                    "primary_ip4": {
                        "id": 1152,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1152/",
                        "family": 4,
                        "address": "192.0.2.4/24",
                    },
                    "primary_ip6": None,
                    "vcpus": 1,
                    "memory": 1024,
                    "disk": 30,
                    "comments": "",
                    "local_context_data": None,
                    "tags": [],
                    "custom_fields": {},
                    "config_context": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:05.799541Z",
                },
            ],
        }
    }


@pytest.fixture
def no_results():
    return {"dict": {"count": 0, "next": None, "previous": None, "results": []}}


@pytest.fixture
def http_error():
    return {"error": "HTTP 404: Not Found", "status": 404}


@pytest.fixture
def device_interface_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 8158,
                    "url": "https://netbox.example.com/api/dcim/interfaces/8158/",
                    "device": {
                        "id": 511,
                        "url": "https://netbox.example.com/api/dcim/devices/511/",
                        "name": "minion1",
                        "display_name": "minion1",
                    },
                    "name": "GigabitEthernet0/0",
                    "label": "",
                    "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
                    "enabled": True,
                    "lag": None,
                    "mtu": None,
                    "mac_address": None,
                    "mgmt_only": False,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "cable": None,
                    "cable_peer": None,
                    "cable_peer_type": None,
                    "connected_endpoints": [
                        {
                            "id": 170,
                            "url": "https://demo.netbox.dev/api/dcim/interfaces/512/",
                            "display": "GigabitEthernet1/0/1",
                            "device": {
                                "id": 512,
                                "url": "https://demo.netbox.dev/api/dcim/devices/512/",
                                "display": "minion2",
                                "name": "minion2",
                            },
                            "name": "GigabitEthernet1/0/1",
                            "cable": 35,
                            "_occupied": True,
                        }
                    ],
                    "connected_endpoints_type": "dcim.interface",
                    "connected_endpoints_reachable": True,
                    "tags": [],
                    "count_ipaddresses": 1,
                },
                {
                    "id": 8159,
                    "url": "https://netbox.example.com/api/dcim/interfaces/8159/",
                    "device": {
                        "id": 511,
                        "url": "https://netbox.example.com/api/dcim/devices/511/",
                        "name": "minion1",
                        "display_name": "minion1",
                    },
                    "name": "GigabitEthernet0/1",
                    "label": "",
                    "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
                    "enabled": True,
                    "lag": None,
                    "mtu": None,
                    "mac_address": None,
                    "mgmt_only": False,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "cable": None,
                    "cable_peer": None,
                    "cable_peer_type": None,
                    "connected_endpoints": None,
                    "connected_endpoints_type": None,
                    "connected_endpoints_reachable": None,
                    "tags": [],
                    "count_ipaddresses": 1,
                },
            ],
        }
    }


@pytest.fixture
def device_interfaces_list():
    return [
        {
            "id": 8158,
            "url": "https://netbox.example.com/api/dcim/interfaces/8158/",
            "name": "GigabitEthernet0/0",
            "label": "",
            "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
            "enabled": True,
            "lag": None,
            "mtu": None,
            "mac_address": None,
            "mgmt_only": False,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "cable": None,
            "cable_peer": None,
            "cable_peer_type": None,
            "connected_endpoints": [
                {
                    "_occupied": True,
                    "cable": 35,
                    "device": {
                        "display": "minion2",
                        "id": 512,
                        "name": "minion2",
                        "url": "https://demo.netbox.dev/api/dcim/devices/512/",
                    },
                    "display": "GigabitEthernet1/0/1",
                    "id": 170,
                    "name": "GigabitEthernet1/0/1",
                    "url": "https://demo.netbox.dev/api/dcim/interfaces/512/",
                }
            ],
            "connected_endpoints_reachable": True,
            "connected_endpoints_type": "dcim.interface",
            "tags": [],
            "count_ipaddresses": 1,
        },
        {
            "id": 8159,
            "url": "https://netbox.example.com/api/dcim/interfaces/8159/",
            "name": "GigabitEthernet0/1",
            "label": "",
            "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
            "enabled": True,
            "lag": None,
            "mtu": None,
            "mac_address": None,
            "mgmt_only": False,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "cable": None,
            "cable_peer": None,
            "cable_peer_type": None,
            "connected_endpoints": None,
            "connected_endpoints_type": None,
            "connected_endpoints_reachable": None,
            "tags": [],
            "count_ipaddresses": 1,
        },
    ]


@pytest.fixture
def virtual_machine_interface_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 668,
                    "url": "https://netbox.example.com/api/virtualization/interfaces/668/",
                    "virtual_machine": {
                        "id": 222,
                        "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                        "name": "minion1",
                    },
                    "name": "GigabitEthernet0/0",
                    "enabled": True,
                    "mtu": None,
                    "mac_address": None,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "tags": [],
                },
                {
                    "id": 669,
                    "url": "https://netbox.example.com/api/virtualization/interfaces/669/",
                    "virtual_machine": {
                        "id": 222,
                        "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                        "name": "minion1",
                    },
                    "name": "GigabitEthernet0/1",
                    "enabled": True,
                    "mtu": None,
                    "mac_address": None,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "tags": [],
                },
            ],
        }
    }


@pytest.fixture
def virtual_machine_interfaces_list():
    return [
        {
            "id": 668,
            "url": "https://netbox.example.com/api/virtualization/interfaces/668/",
            "name": "GigabitEthernet0/0",
            "enabled": True,
            "mtu": None,
            "mac_address": None,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "tags": [],
        },
        {
            "id": 669,
            "url": "https://netbox.example.com/api/virtualization/interfaces/669/",
            "name": "GigabitEthernet0/1",
            "enabled": True,
            "mtu": None,
            "mac_address": None,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "tags": [],
        },
    ]


@pytest.fixture
def device_ip_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 1146,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "192.0.2.1/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": 8158,
                    "assigned_object": {
                        "id": 8158,
                        "url": "https://netbox.example.com/api/dcim/interfaces/8158/",
                        "device": {
                            "id": 511,
                            "url": "https://netbox.example.com/api/dcim/devices/511/",
                            "name": "minion1",
                            "display_name": "minion1",
                        },
                        "name": "GigabitEthernet0/0",
                        "cable": None,
                    },
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:04.153386Z",
                },
                {
                    "id": 1147,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1147/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "198.51.100.1/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": 8159,
                    "assigned_object": {
                        "id": 8159,
                        "url": "https://netbox.example.com/api/dcim/interfaces/8159/",
                        "device": {
                            "id": 511,
                            "url": "https://netbox.example.com/api/dcim/devices/511/",
                            "name": "minion1",
                            "display_name": "minion1",
                        },
                        "name": "GigabitEthernet0/1",
                        "cable": None,
                    },
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:40.508154Z",
                },
            ],
        }
    }


@pytest.fixture
def virtual_machine_ip_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 1148,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "192.0.2.2/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "assigned_object_type": "virtualization.vminterface",
                    "assigned_object_id": 668,
                    "assigned_object": {
                        "id": 668,
                        "url": "https://netbox.example.com/api/virtualization/interfaces/668/",
                        "virtual_machine": {
                            "id": 222,
                            "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                            "name": "minion1",
                        },
                        "name": "GigabitEthernet0/0",
                    },
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:05.784281Z",
                },
                {
                    "id": 1149,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1149/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "198.51.100.2/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "assigned_object_type": "virtualization.vminterface",
                    "assigned_object_id": 669,
                    "assigned_object": {
                        "id": 669,
                        "url": "https://netbox.example.com/api/virtualization/interfaces/669/",
                        "virtual_machine": {
                            "id": 222,
                            "url": "https://netbox.example.com/api/virtualization/virtual-machines/222/",
                            "name": "minion1",
                        },
                        "name": "GigabitEthernet0/1",
                    },
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:29.607428Z",
                },
            ],
        }
    }


@pytest.fixture
def device_interfaces_ip_list():
    return [
        {
            "id": 8158,
            "ip_addresses": [
                {
                    "id": 1146,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "192.0.2.1/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:04.153386Z",
                },
            ],
            "url": "https://netbox.example.com/api/dcim/interfaces/8158/",
            "name": "GigabitEthernet0/0",
            "label": "",
            "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
            "enabled": True,
            "lag": None,
            "mtu": None,
            "mac_address": None,
            "mgmt_only": False,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "cable": None,
            "cable_peer": None,
            "cable_peer_type": None,
            "connected_endpoints": [
                {
                    "id": 170,
                    "url": "https://demo.netbox.dev/api/dcim/interfaces/512/",
                    "display": "GigabitEthernet1/0/1",
                    "device": {
                        "id": 512,
                        "url": "https://demo.netbox.dev/api/dcim/devices/512/",
                        "display": "minion2",
                        "name": "minion2",
                    },
                    "name": "GigabitEthernet1/0/1",
                    "cable": 35,
                    "_occupied": True,
                }
            ],
            "connected_endpoints_type": "dcim.interface",
            "connected_endpoints_reachable": True,
            "tags": [],
            "count_ipaddresses": 1,
        },
        {
            "id": 8159,
            "ip_addresses": [
                {
                    "id": 1147,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1147/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "198.51.100.1/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:12:40.508154Z",
                },
            ],
            "url": "https://netbox.example.com/api/dcim/interfaces/8159/",
            "name": "GigabitEthernet0/1",
            "label": "",
            "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
            "enabled": True,
            "lag": None,
            "mtu": None,
            "mac_address": None,
            "mgmt_only": False,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "cable": None,
            "cable_peer": None,
            "cable_peer_type": None,
            "connected_endpoints": None,
            "connected_endpoints_type": None,
            "connected_endpoints_reachable": None,
            "tags": [],
            "count_ipaddresses": 1,
        },
    ]


@pytest.fixture
def virtual_machine_interfaces_ip_list():
    return [
        {
            "id": 668,
            "ip_addresses": [
                {
                    "id": 1148,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1148/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "192.0.2.2/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:05.784281Z",
                },
            ],
            "url": "https://netbox.example.com/api/virtualization/interfaces/668/",
            "name": "GigabitEthernet0/0",
            "enabled": True,
            "mtu": None,
            "mac_address": None,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "tags": [],
        },
        {
            "id": 669,
            "ip_addresses": [
                {
                    "id": 1149,
                    "url": "https://netbox.example.com/api/ipam/ip-addresses/1149/",
                    "family": {"value": 4, "label": "IPv4"},
                    "address": "198.51.100.2/24",
                    "vrf": None,
                    "tenant": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "nat_inside": None,
                    "nat_outside": None,
                    "dns_name": "",
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-19",
                    "last_updated": "2021-02-19T06:23:29.607428Z",
                },
            ],
            "url": "https://netbox.example.com/api/virtualization/interfaces/669/",
            "name": "GigabitEthernet0/1",
            "enabled": True,
            "mtu": None,
            "mac_address": None,
            "description": "",
            "mode": None,
            "untagged_vlan": None,
            "tagged_vlans": [],
            "tags": [],
        },
    ]


@pytest.fixture
def site_results():
    return {
        "dict": {
            "id": 18,
            "url": "https://netbox.example.com/api/dcim/sites/18/",
            "name": "Site 1",
            "slug": "site1",
            "status": {"value": "active", "label": "Active"},
            "region": None,
            "tenant": None,
            "facility": "",
            "asn": None,
            "time_zone": None,
            "description": "",
            "physical_address": "",
            "shipping_address": "",
            "latitude": None,
            "longitude": None,
            "contact_name": "",
            "contact_phone": "",
            "contact_email": "",
            "comments": "",
            "tags": [],
            "custom_fields": {},
            "created": "2021-02-25",
            "last_updated": "2021-02-25T14:21:07.898957Z",
            "circuit_count": 0,
            "device_count": 1,
            "prefix_count": 2,
            "rack_count": 0,
            "virtualmachine_count": 1,
            "vlan_count": 0,
        }
    }


@pytest.fixture
def site_prefixes_results():
    return {
        "dict": {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 284,
                    "url": "https://netbox.example.com/api/ipam/prefixes/284/",
                    "family": {"value": 4, "label": "IPv4"},
                    "prefix": "192.0.2.0/24",
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "vrf": None,
                    "tenant": None,
                    "vlan": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "is_pool": False,
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-25",
                    "last_updated": "2021-02-25T15:08:27.136305Z",
                },
                {
                    "id": 285,
                    "url": "https://netbox.example.com/api/ipam/prefixes/285/",
                    "family": {"value": 4, "label": "IPv4"},
                    "prefix": "198.51.100.0/24",
                    "site": {
                        "id": 18,
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                        "name": "Site 1",
                        "slug": "site1",
                    },
                    "vrf": None,
                    "tenant": None,
                    "vlan": None,
                    "status": {"value": "active", "label": "Active"},
                    "role": None,
                    "is_pool": False,
                    "description": "",
                    "tags": [],
                    "custom_fields": {},
                    "created": "2021-02-25",
                    "last_updated": "2021-02-25T15:08:59.880440Z",
                },
            ],
        }
    }


@pytest.fixture
def site_prefixes():
    return [
        {
            "id": 284,
            "url": "https://netbox.example.com/api/ipam/prefixes/284/",
            "family": {"value": 4, "label": "IPv4"},
            "prefix": "192.0.2.0/24",
            "vrf": None,
            "tenant": None,
            "vlan": None,
            "status": {"value": "active", "label": "Active"},
            "role": None,
            "is_pool": False,
            "description": "",
            "tags": [],
            "custom_fields": {},
            "created": "2021-02-25",
            "last_updated": "2021-02-25T15:08:27.136305Z",
        },
        {
            "id": 285,
            "url": "https://netbox.example.com/api/ipam/prefixes/285/",
            "family": {"value": 4, "label": "IPv4"},
            "prefix": "198.51.100.0/24",
            "vrf": None,
            "tenant": None,
            "vlan": None,
            "status": {"value": "active", "label": "Active"},
            "role": None,
            "is_pool": False,
            "description": "",
            "tags": [],
            "custom_fields": {},
            "created": "2021-02-25",
            "last_updated": "2021-02-25T15:08:59.880440Z",
        },
    ]


@pytest.fixture
def proxy_details_results():
    return {
        "dict": {
            "id": 1,
            "url": "https://netbox.example.com/api/dcim/platforms/1/",
            "name": "Cisco IOS",
            "slug": "ios",
            "manufacturer": {
                "id": 1,
                "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                "name": "Cisco",
                "slug": "cisco",
            },
            "napalm_driver": "ios",
            "napalm_args": None,
            "description": "",
            "device_count": 152,
            "virtualmachine_count": 1,
        }
    }


@pytest.fixture
def proxy_details():
    return {
        "host": "192.0.2.1",
        "driver": "ios",
        "proxytype": "napalm",
    }


@pytest.fixture
def pillar_results():
    return {
        "netbox": {
            "id": 511,
            "url": "https://netbox.example.com/api/dcim/devices/511/",
            "name": "minion1",
            "node_type": "device",
            "display_name": "minion1",
            "device_type": {
                "id": 4,
                "url": "https://netbox.example.com/api/dcim/device-types/4/",
                "manufacturer": {
                    "id": 1,
                    "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                    "name": "Cisco",
                    "slug": "cisco",
                },
                "model": "ISR2901",
                "slug": "isr2901",
                "display_name": "Cisco ISR2901",
            },
            "device_role": {
                "id": 45,
                "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                "name": "Network",
                "slug": "network",
            },
            "interfaces": [
                {
                    "id": 8158,
                    "ip_addresses": [
                        {
                            "id": 1146,
                            "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                            "family": {"value": 4, "label": "IPv4"},
                            "address": "192.0.2.1/24",
                            "vrf": None,
                            "tenant": None,
                            "status": {"value": "active", "label": "Active"},
                            "role": None,
                            "nat_inside": None,
                            "nat_outside": None,
                            "dns_name": "",
                            "description": "",
                            "tags": [],
                            "custom_fields": {},
                            "created": "2021-02-19",
                            "last_updated": "2021-02-19T06:12:04.153386Z",
                        },
                    ],
                    "url": "https://netbox.example.com/api/dcim/interfaces/8158/",
                    "name": "GigabitEthernet0/0",
                    "label": "",
                    "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
                    "enabled": True,
                    "lag": None,
                    "mtu": None,
                    "mac_address": None,
                    "mgmt_only": False,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "cable": None,
                    "cable_peer": None,
                    "cable_peer_type": None,
                    "connected_endpoints": [
                        {
                            "id": 170,
                            "url": "https://demo.netbox.dev/api/dcim/interfaces/512/",
                            "display": "GigabitEthernet1/0/1",
                            "device": {
                                "id": 512,
                                "url": "https://demo.netbox.dev/api/dcim/devices/512/",
                                "display": "minion2",
                                "name": "minion2",
                            },
                            "name": "GigabitEthernet1/0/1",
                            "cable": 35,
                            "_occupied": True,
                        }
                    ],
                    "connected_endpoints_type": "dcim.interface",
                    "connected_endpoints_reachable": True,
                    "tags": [],
                    "count_ipaddresses": 1,
                },
                {
                    "id": 8159,
                    "ip_addresses": [
                        {
                            "id": 1147,
                            "url": "https://netbox.example.com/api/ipam/ip-addresses/1147/",
                            "family": {"value": 4, "label": "IPv4"},
                            "address": "198.51.100.1/24",
                            "vrf": None,
                            "tenant": None,
                            "status": {"value": "active", "label": "Active"},
                            "role": None,
                            "nat_inside": None,
                            "nat_outside": None,
                            "dns_name": "",
                            "description": "",
                            "tags": [],
                            "custom_fields": {},
                            "created": "2021-02-19",
                            "last_updated": "2021-02-19T06:12:40.508154Z",
                        },
                    ],
                    "url": "https://netbox.example.com/api/dcim/interfaces/8159/",
                    "name": "GigabitEthernet0/1",
                    "label": "",
                    "type": {"value": "1000base-t", "label": "1000BASE-T (1GE)"},
                    "enabled": True,
                    "lag": None,
                    "mtu": None,
                    "mac_address": None,
                    "mgmt_only": False,
                    "description": "",
                    "mode": None,
                    "untagged_vlan": None,
                    "tagged_vlans": [],
                    "cable": None,
                    "cable_peer": None,
                    "cable_peer_type": None,
                    "connected_endpoints": None,
                    "connected_endpoints_type": None,
                    "connected_endpoints_reachable": None,
                    "tags": [],
                    "count_ipaddresses": 1,
                },
            ],
            "tenant": None,
            "platform": {
                "id": 1,
                "url": "https://netbox.example.com/api/dcim/platforms/1/",
                "name": "Cisco IOS",
                "slug": "ios",
            },
            "serial": "",
            "asset_tag": None,
            "site": {
                "id": 18,
                "url": "https://netbox.example.com/api/dcim/sites/18/",
                "name": "Site 1",
                "slug": "site1",
                "status": {"value": "active", "label": "Active"},
                "region": None,
                "tenant": None,
                "facility": "",
                "asn": None,
                "time_zone": None,
                "description": "",
                "physical_address": "",
                "shipping_address": "",
                "latitude": None,
                "longitude": None,
                "contact_name": "",
                "contact_phone": "",
                "contact_email": "",
                "comments": "",
                "tags": [],
                "custom_fields": {},
                "created": "2021-02-25",
                "last_updated": "2021-02-25T14:21:07.898957Z",
                "circuit_count": 0,
                "device_count": 1,
                "prefix_count": 2,
                "rack_count": 0,
                "virtualmachine_count": 1,
                "vlan_count": 0,
                "prefixes": [
                    {
                        "id": 284,
                        "url": "https://netbox.example.com/api/ipam/prefixes/284/",
                        "family": {"value": 4, "label": "IPv4"},
                        "prefix": "192.0.2.0/24",
                        "vrf": None,
                        "tenant": None,
                        "vlan": None,
                        "status": {"value": "active", "label": "Active"},
                        "role": None,
                        "is_pool": False,
                        "description": "",
                        "tags": [],
                        "custom_fields": {},
                        "created": "2021-02-25",
                        "last_updated": "2021-02-25T15:08:27.136305Z",
                    },
                    {
                        "id": 285,
                        "url": "https://netbox.example.com/api/ipam/prefixes/285/",
                        "family": {"value": 4, "label": "IPv4"},
                        "prefix": "198.51.100.0/24",
                        "vrf": None,
                        "tenant": None,
                        "vlan": None,
                        "status": {"value": "active", "label": "Active"},
                        "role": None,
                        "is_pool": False,
                        "description": "",
                        "tags": [],
                        "custom_fields": {},
                        "created": "2021-02-25",
                        "last_updated": "2021-02-25T15:08:59.880440Z",
                    },
                ],
            },
            "rack": None,
            "position": None,
            "face": None,
            "parent_device": None,
            "status": {"value": "active", "label": "Active"},
            "primary_ip": {
                "id": 1146,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                "family": 4,
                "address": "192.0.2.1/24",
            },
            "primary_ip4": {
                "id": 1146,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1146/",
                "family": 4,
                "address": "192.0.2.1/24",
            },
            "primary_ip6": None,
            "cluster": None,
            "virtual_chassis": None,
            "vc_position": None,
            "vc_priority": None,
            "comments": "",
            "local_context_data": None,
            "tags": [],
            "custom_fields": {},
            "config_context": {},
            "connected_devices": {
                512: {
                    "asset_tag": None,
                    "cluster": None,
                    "comments": "",
                    "config_context": {},
                    "created": "2021-02-19",
                    "custom_fields": {},
                    "device_role": {
                        "id": 45,
                        "name": "Network",
                        "slug": "network",
                        "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                    },
                    "device_type": {
                        "display_name": "Cisco " "ISR2901",
                        "id": 4,
                        "manufacturer": {
                            "id": 1,
                            "name": "Cisco",
                            "slug": "cisco",
                            "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                        },
                        "model": "ISR2901",
                        "slug": "isr2901",
                        "url": "https://netbox.example.com/api/dcim/device-types/4/",
                    },
                    "display_name": "minion2",
                    "face": None,
                    "id": 512,
                    "last_updated": "2021-02-19T06:12:04.171105Z",
                    "local_context_data": None,
                    "name": "minion2",
                    "node_type": "device",
                    "parent_device": None,
                    "platform": {
                        "id": 1,
                        "name": "Cisco IOS",
                        "slug": "ios",
                        "url": "https://netbox.example.com/api/dcim/platforms/1/",
                    },
                    "position": None,
                    "primary_ip": {
                        "address": "192.0.2.3/24",
                        "family": 4,
                        "id": 1150,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                    },
                    "primary_ip4": {
                        "address": "192.0.2.3/24",
                        "family": 4,
                        "id": 1150,
                        "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                    },
                    "primary_ip6": None,
                    "rack": None,
                    "serial": "",
                    "site": {
                        "id": 18,
                        "name": "Site 1",
                        "slug": "site1",
                        "url": "https://netbox.example.com/api/dcim/sites/18/",
                    },
                    "status": {"label": "Active", "value": "active"},
                    "tags": [],
                    "tenant": None,
                    "url": "https://netbox.example.com/api/dcim/devices/512/",
                    "vc_position": None,
                    "vc_priority": None,
                    "virtual_chassis": None,
                }
            },
            "created": "2021-02-19",
            "last_updated": "2021-02-19T06:12:04.171105Z",
        },
        "proxy": {"host": "192.0.2.1", "driver": "ios", "proxytype": "napalm"},
    }


@pytest.fixture
def connected_devices_results():
    return {
        512: {
            "id": 512,
            "url": "https://netbox.example.com/api/dcim/devices/512/",
            "name": "minion2",
            "display_name": "minion2",
            "device_type": {
                "id": 4,
                "url": "https://netbox.example.com/api/dcim/device-types/4/",
                "manufacturer": {
                    "id": 1,
                    "url": "https://netbox.example.com/api/dcim/manufacturers/1/",
                    "name": "Cisco",
                    "slug": "cisco",
                },
                "model": "ISR2901",
                "slug": "isr2901",
                "display_name": "Cisco ISR2901",
            },
            "device_role": {
                "id": 45,
                "url": "https://netbox.example.com/api/dcim/device-roles/45/",
                "name": "Network",
                "slug": "network",
            },
            "node_type": "device",
            "tenant": None,
            "platform": {
                "id": 1,
                "url": "https://netbox.example.com/api/dcim/platforms/1/",
                "name": "Cisco IOS",
                "slug": "ios",
            },
            "serial": "",
            "asset_tag": None,
            "site": {
                "id": 18,
                "url": "https://netbox.example.com/api/dcim/sites/18/",
                "name": "Site 1",
                "slug": "site1",
            },
            "rack": None,
            "position": None,
            "face": None,
            "parent_device": None,
            "status": {"value": "active", "label": "Active"},
            "primary_ip": {
                "id": 1150,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                "family": 4,
                "address": "192.0.2.3/24",
            },
            "primary_ip4": {
                "id": 1150,
                "url": "https://netbox.example.com/api/ipam/ip-addresses/1150/",
                "family": 4,
                "address": "192.0.2.3/24",
            },
            "primary_ip6": None,
            "cluster": None,
            "virtual_chassis": None,
            "vc_position": None,
            "vc_priority": None,
            "comments": "",
            "local_context_data": None,
            "tags": [],
            "custom_fields": {},
            "config_context": {},
            "created": "2021-02-19",
            "last_updated": "2021-02-19T06:12:04.171105Z",
        }
    }


def test_when_minion_id_is_star_then_result_should_be_empty_dict(default_kwargs):
    expected_result = {}
    default_kwargs["minion_id"] = "*"

    actual_result = netbox.ext_pillar(**default_kwargs)

    assert actual_result == expected_result


def test_when_api_url_is_not_http_or_https_then_error_message_should_be_logged(
    default_kwargs,
):
    default_kwargs["api_url"] = "ftp://netbox.example.com"

    with patch("salt.pillar.netbox.log.error", autospec=True) as fake_error:
        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'Provided URL for api_url "%s" is malformed or is not an http/https URL',
            "ftp://netbox.example.com",
        )


def test_when_neither_devices_or_virtual_machines_requested_then_error_message_should_be_logged(
    default_kwargs,
):
    default_kwargs["devices"] = default_kwargs["virtual_machines"] = False

    with patch("salt.pillar.netbox.log.error", autospec=True) as fake_error:
        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            "At least one of devices or virtual_machines must be True"
        )


def test_when_interface_ips_requested_but_not_interfaces_then_error_message_should_be_logged(
    default_kwargs,
):
    default_kwargs["interfaces"] = False
    default_kwargs["interface_ips"] = True

    with patch("salt.pillar.netbox.log.error", autospec=True) as fake_error:
        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            "The value for interfaces must be True if interface_ips is True"
        )


def test_when_api_query_result_limit_set_but_not_a_positive_integer_then_error_message_should_be_logged(
    default_kwargs,
):
    default_kwargs["api_query_result_limit"] = -1

    with patch("salt.pillar.netbox.log.error", autospec=True) as fake_error:
        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            "The value for api_query_result_limit must be a postive integer if set"
        )


def test_when_api_token_not_set_then_error_message_should_be_logged(
    default_kwargs,
):

    default_kwargs["api_token"] = ""

    with patch("salt.pillar.netbox.log.error", autospec=True) as fake_error:
        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with("The value for api_token is not set")


def test_when_we_retrieve_a_single_device_then_return_list(
    default_kwargs, headers, device_results
):

    expected_result = device_results["dict"]["results"]

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = device_results

        actual_result = netbox._get_devices(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_a_device_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):
    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_devices(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_a_single_virtual_machine_then_return_list(
    default_kwargs, headers, virtual_machine_results
):

    expected_result = virtual_machine_results["dict"]["results"]

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = virtual_machine_results

        actual_result = netbox._get_virtual_machines(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_a_virtual_machine_and_get_http_error_then_return_empty_dict(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_virtual_machines(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_device_interfaces_then_return_dict(
    default_kwargs, headers, device_interface_results, device_interfaces_list
):

    expected_result = device_interfaces_list

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = device_interface_results

        actual_result = netbox._get_interfaces(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            511,
            "device",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_device_interfaces_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_interfaces(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            511,
            "device",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_virtual_machine_interfaces_then_return_list(
    default_kwargs,
    headers,
    virtual_machine_interface_results,
    virtual_machine_interfaces_list,
):

    expected_result = virtual_machine_interfaces_list

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = virtual_machine_interface_results

        actual_result = netbox._get_interfaces(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            222,
            "virtual-machine",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_virtual_machine_interfaces_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_interfaces(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            222,
            "virtual-machine",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_device_interface_ips_then_return_list(
    default_kwargs, headers, device_ip_results
):

    expected_result = device_ip_results["dict"]["results"]

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = device_ip_results

        actual_result = netbox._get_interface_ips(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            511,
            "device",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_connected_endpoints(
    default_kwargs,
    headers,
    connected_devices_results,
    device_interfaces_list,
    secondary_device_result,
):

    expected_result = connected_devices_results

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = secondary_device_result

        actual_result = netbox._get_connected_devices(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            device_interfaces_list,
            headers,
        )

        assert actual_result == expected_result


def test_when_we_retrieve_device_interface_ips_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_interface_ips(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            511,
            "device",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_virtual_machine_interface_ips_then_return_list(
    default_kwargs, headers, virtual_machine_ip_results
):

    expected_result = virtual_machine_ip_results["dict"]["results"]

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = virtual_machine_ip_results

        actual_result = netbox._get_interface_ips(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            222,
            "virtual-machine",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_virtual_machine_interface_ips_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_interface_ips(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            222,
            "virtual-machine",
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_associate_ips_to_interfaces_then_return_list(
    default_kwargs, device_interfaces_list, device_ip_results, device_interfaces_ip_list
):

    expected_result = device_interfaces_ip_list

    interfaces_list = device_interfaces_list
    interface_ips_list = device_ip_results["dict"]["results"]

    actual_result = netbox._associate_ips_to_interfaces(
        interfaces_list, interface_ips_list
    )

    assert actual_result == expected_result


def test_associate_empty_ip_list_to_interfaces_then_return_list(
    default_kwargs, device_interfaces_list, device_ip_results
):

    expected_result = device_interfaces_list

    interfaces_list = device_interfaces_list
    interface_ips_list = []

    actual_result = netbox._associate_ips_to_interfaces(
        interfaces_list, interface_ips_list
    )

    assert actual_result == expected_result


def test_when_we_retrieve_site_details_then_return_dict(
    default_kwargs, headers, site_results
):

    expected_result = site_results["dict"]

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = site_results

        actual_result = netbox._get_site_details(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "Site 1",
            18,
            headers,
        )

        assert actual_result == expected_result


def test_when_we_retrieve_site_details_and_get_http_error_then_return_empty_dict(
    default_kwargs, headers, http_error
):

    expected_result = {}

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_site_details(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "Site 1",
            18,
            headers,
        )

        assert actual_result == expected_result


def test_when_we_retrieve_site_prefixes_then_return_list(
    default_kwargs, headers, site_prefixes_results, site_prefixes
):

    expected_result = site_prefixes

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = site_prefixes_results

        actual_result = netbox._get_site_prefixes(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "Site 1",
            18,
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_site_prefixes_and_get_http_error_then_return_empty_list(
    default_kwargs, headers, http_error
):

    expected_result = []

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_site_prefixes(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "Site 1",
            18,
            headers,
            default_kwargs["api_query_result_limit"],
        )

        assert actual_result == expected_result


def test_when_we_retrieve_proxy_details_then_return_dict(
    default_kwargs, headers, proxy_details_results, proxy_details
):

    expected_result = proxy_details

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = proxy_details_results

        actual_result = netbox._get_proxy_details(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "192.0.2.1/24",
            1,
            headers,
        )

        assert actual_result == expected_result


def test_when_we_retrieve_proxy_details_and_get_http_error_then_dont_return(
    default_kwargs, headers, http_error
):

    expected_result = None

    with patch("salt.utils.http.query", autospec=True) as query:
        query.return_value = http_error

        actual_result = netbox._get_proxy_details(
            default_kwargs["api_url"],
            default_kwargs["minion_id"],
            "192.0.2.1/24",
            1,
            headers,
        )

        assert actual_result == expected_result


def test_when_we_retrieve_multiple_devices_then_error_message_should_be_logged(
    default_kwargs, multiple_device_results
):

    with patch(
        "salt.pillar.netbox._get_devices", autospec=True
    ) as multiple_devices, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        multiple_devices.return_value = multiple_device_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'More than one node found for "%s"',
            "minion1",
        )


def test_when_we_retrieve_multiple_virtual_machines_then_error_message_should_be_logged(
    default_kwargs, multiple_virtual_machine_results
):
    default_kwargs["devices"] = False
    default_kwargs["virtual_machines"] = True

    with patch(
        "salt.pillar.netbox._get_virtual_machines", autospec=True
    ) as multiple_virtual_machines, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        multiple_virtual_machines.return_value = multiple_virtual_machine_results[
            "dict"
        ]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'More than one node found for "%s"',
            "minion1",
        )


def test_when_we_retrieve_a_device_and_a_virtual_machine_then_error_message_should_be_logged(
    default_kwargs, device_results, virtual_machine_results
):
    default_kwargs["virtual_machines"] = True

    with patch("salt.pillar.netbox._get_devices", autospec=True) as device, patch(
        "salt.pillar.netbox._get_virtual_machines", autospec=True
    ) as virtual_machine, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        device.return_value = device_results["dict"]["results"]
        virtual_machine.return_value = virtual_machine_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'More than one node found for "%s"',
            "minion1",
        )


def test_when_we_retrieve_no_devices_then_error_message_should_be_logged(
    default_kwargs, no_results
):

    with patch("salt.pillar.netbox._get_devices", autospec=True) as devices, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        devices.return_value = no_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'Unable to pull NetBox data for "%s"',
            "minion1",
        )


def test_when_we_retrieve_no_virtual_machines_then_error_message_should_be_logged(
    default_kwargs, no_results
):
    default_kwargs["devices"] = False
    default_kwargs["virtual_machines"] = True

    with patch(
        "salt.pillar.netbox._get_virtual_machines", autospec=True
    ) as virtual_machines, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:
        virtual_machines.return_value = no_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'Unable to pull NetBox data for "%s"',
            "minion1",
        )


def test_when_we_retrieve_everything_successfully_then_return_dict(
    default_kwargs,
    device_results,
    no_results,
    device_interfaces_list,
    device_ip_results,
    site_results,
    site_prefixes,
    proxy_details,
    pillar_results,
    connected_devices_results,
):

    expected_result = pillar_results

    default_kwargs["virtual_machines"] = False
    default_kwargs["interfaces"] = True
    default_kwargs["interface_ips"] = True
    default_kwargs["site_details"] = True
    default_kwargs["site_prefixes"] = True
    default_kwargs["proxy_return"] = True
    default_kwargs["connected_devices"] = True

    with patch("salt.pillar.netbox._get_devices", autospec=True) as get_devices, patch(
        "salt.pillar.netbox._get_virtual_machines", autospec=True
    ) as get_virtual_machines, patch(
        "salt.pillar.netbox._get_interfaces", autospec=True
    ) as get_interfaces, patch(
        "salt.pillar.netbox._get_interface_ips", autospec=True
    ) as get_interface_ips, patch(
        "salt.pillar.netbox._get_site_details", autospec=True
    ) as get_site_details, patch(
        "salt.pillar.netbox._get_site_prefixes", autospec=True
    ) as get_site_prefixes, patch(
        "salt.pillar.netbox._get_proxy_details", autospec=True
    ) as get_proxy_details, patch(
        "salt.pillar.netbox._get_connected_devices", autospec=True
    ) as get_connected_decvices:

        get_devices.return_value = device_results["dict"]["results"]
        get_virtual_machines.return_value = no_results["dict"]["results"]
        get_interfaces.return_value = device_interfaces_list
        get_interface_ips.return_value = device_ip_results["dict"]["results"]
        get_site_details.return_value = site_results["dict"]
        get_site_prefixes.return_value = site_prefixes
        get_proxy_details.return_value = proxy_details
        get_connected_decvices.return_value = connected_devices_results

        actual_result = netbox.ext_pillar(**default_kwargs)

        assert actual_result == expected_result


def test_when_we_set_proxy_return_but_get_no_value_for_platform_then_error_message_should_be_logged(
    default_kwargs, headers, device_results
):

    default_kwargs["site_details"] = False
    default_kwargs["site_prefixes"] = False
    default_kwargs["proxy_return"] = True
    device_results["dict"]["results"][0]["platform"] = None

    with patch("salt.pillar.netbox._get_devices", autospec=True) as devices, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        devices.return_value = device_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'You have set "proxy_return" to "True" but you have not set the platform in NetBox for "%s"',
            "minion1",
        )


def test_when_we_set_proxy_return_but_get_no_value_for_primary_ip_then_error_message_should_be_logged(
    default_kwargs, headers, device_results
):

    default_kwargs["site_details"] = False
    default_kwargs["site_prefixes"] = False
    default_kwargs["proxy_return"] = True
    device_results["dict"]["results"][0]["primary_ip"] = None

    with patch("salt.pillar.netbox._get_devices", autospec=True) as devices, patch(
        "salt.pillar.netbox.log.error", autospec=True
    ) as fake_error:

        devices.return_value = device_results["dict"]["results"]

        netbox.ext_pillar(**default_kwargs)

        fake_error.assert_called_with(
            'You have set "proxy_return" to "True" but you have not set the primary IPv4 or IPv6 address in NetBox for "%s"',
            "minion1",
        )
