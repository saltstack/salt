# -*- coding: utf-8 -*-
'''
Beacon to monitor statistics from ethernet adapters

.. versionadded:: 2015.5.0
'''

# Import Python libs
from __future__ import absolute_import
import logging

# Import third party libs
# pylint: disable=import-error
try:
    import salt.utils.psutil_compat as psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
# pylint: enable=import-error

log = logging.getLogger(__name__)

__virtualname__ = 'network_info'

__attrs = ['bytes_sent', 'bytes_recv', 'packets_sent',
           'packets_recv', 'errin', 'errout',
           'dropin', 'dropout']


def _to_list(obj):
    '''
    Convert snetinfo object to list
    '''
    ret = {}

    for attr in __attrs:
        # Better way to do this?
        ret[attr] = obj.__dict__[attr]
    return ret


def __virtual__():
    if not HAS_PSUTIL:
        return (False, 'cannot load network_info beacon: psutil not available')
    return __virtualname__


def validate(config):
    '''
    Validate the beacon configuration
    '''

    VALID_ITEMS = [
        'type', 'bytes_sent', 'bytes_recv', 'packets_sent',
        'packets_recv', 'errin', 'errout', 'dropin',
        'dropout'
    ]

    # Configuration for load beacon should be a list of dicts
    if not isinstance(config, dict):
        return False, ('Configuration for load beacon must be a dictionary.')
    else:
        for item in config:
            if not isinstance(config[item], dict):
                return False, ('Configuration for load beacon must '
                               'be a dictionary of dictionaries.')
            else:
                if not any(j in VALID_ITEMS for j in config[item]):
                    return False, ('Invalid configuration item in '
                                   'Beacon configuration.')
    return True, 'Valid beacon configuration'


def beacon(config):
    '''
    Emit the network statistics of this host.

    Specify thresholds for each network stat
    and only emit a beacon if any of them are
    exceeded.

    Emit beacon when any values are equal to
    configured values.

    .. code-block:: yaml

        beacons:
          network_info:
            eth0:
                - type: equal
                - bytes_sent: 100000
                - bytes_recv: 100000
                - packets_sent: 100000
                - packets_recv: 100000
                - errin: 100
                - errout: 100
                - dropin: 100
                - dropout: 100

    Emit beacon when any values are greater
    than configured values.

    .. code-block:: yaml

        beacons:
          network_info:
            eth0:
                - type: greater
                - bytes_sent: 100000
                - bytes_recv: 100000
                - packets_sent: 100000
                - packets_recv: 100000
                - errin: 100
                - errout: 100
                - dropin: 100
                - dropout: 100


    '''
    ret = []

    _stats = psutil.net_io_counters(pernic=True)

    for interface in config:
        if interface in _stats:
            _if_stats = _stats[interface]
            _diff = False
            for attr in __attrs:
                if attr in config[interface]:
                    if 'type' in config[interface] and config[interface]['type'] == 'equal':
                        if _if_stats.__dict__[attr] == int(config[interface][attr]):
                            _diff = True
                    elif 'type' in config[interface] and config[interface]['type'] == 'greater':
                        if _if_stats.__dict__[attr] > int(config[interface][attr]):
                            _diff = True
                    else:
                        if _if_stats.__dict__[attr] == int(config[interface][attr]):
                            _diff = True
            if _diff:
                ret.append({'interface': interface,
                            'network_info': _to_list(_if_stats)})
    return ret
