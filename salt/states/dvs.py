# -*- coding: utf-8 -*-
'''
Manage VMware distributed virtual switches (DVSs) and their distributed virtual
portgroups (DVportgroups).

Examples
========

Several settings can be changed for DVSs and DVporgroups. Here are two examples
covering all of the settings. Fewer settings can be used

DVS
---

.. code-block:: python

    'name': 'dvs1',
    'max_mtu': 1000,
    'uplink_names': [
        'dvUplink1',
        'dvUplink2',
        'dvUplink3'
    ],
    'capability': {
        'portgroup_operation_supported': false,
        'operation_supported': true,
        'port_operation_supported': false
    },
    'lacp_api_version': 'multipleLag',
    'contact_email': 'foo@email.com',
    'product_info': {
        'version':
        '6.0.0',
        'vendor':
        'VMware,
        Inc.',
        'name':
        'DVS'
    },
    'network_resource_management_enabled': true,
    'contact_name': 'me@email.com',
    'infrastructure_traffic_resource_pools': [
        {
            'reservation': 0,
            'limit': 1000,
            'share_level': 'high',
            'key': 'management',
            'num_shares': 100
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'faultTolerance',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': 32000,
            'share_level': 'normal',
            'key': 'vmotion',
            'num_shares': 50
        },
        {
            'reservation': 10000,
            'limit': -1,
            'share_level': 'normal',
            'key': 'virtualMachine',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'custom',
            'key': 'iSCSI',
            'num_shares': 75
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'nfs',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'hbr',
            'num_shares': 50
        },
        {
            'reservation': 8750,
            'limit': 15000,
            'share_level': 'high',
            'key': 'vsan',
            'num_shares': 100
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'vdp',
            'num_shares': 50
        }
    ],
    'link_discovery_protocol': {
        'operation':
        'listen',
        'protocol':
        'cdp'
    },
    'network_resource_control_version': 'version3',
    'description': 'Managed by Salt. Random settings.'

Note: The mandatory attribute is: ``name``.

Portgroup
---------

.. code-block:: python
    'security_policy': {
        'allow_promiscuous': true,
        'mac_changes': false,
        'forged_transmits': true
    },
    'name': 'vmotion-v702',
    'out_shaping': {
        'enabled': true,
        'average_bandwidth': 1500,
        'burst_size': 4096,
        'peak_bandwidth': 1500
    },
    'num_ports': 128,
    'teaming': {
        'port_order': {
            'active': [
                'dvUplink2'
            ],
            'standby': [
                'dvUplink1'
            ]
        },
        'notify_switches': false,
        'reverse_policy': true,
        'rolling_order': false,
        'policy': 'failover_explicit',
        'failure_criteria': {
            'check_error_percent': true,
            'full_duplex': false,
            'check_duplex': false,
            'percentage': 50,
            'check_speed': 'minimum',
            'speed': 20,
            'check_beacon': true
        }
    },
    'type': 'earlyBinding',
    'vlan_id': 100,
    'description': 'Managed by Salt. Random settings.'

Note: The mandatory attributes are: ``name``, ``type``.

Dependencies
============


- pyVmomi Python Module


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.
'''

# Import Python Libs
from __future__ import absolute_import
import logging
import traceback

# Import Salt Libs
import salt.exceptions
from salt.utils.dictupdate import update as dict_merge
import salt.utils

# Get Logging Started
log = logging.getLogger(__name__)

def __virtual__():
    return True


def mod_init(low):
    '''
    Init function
    '''
    return True
