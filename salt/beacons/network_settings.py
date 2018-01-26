# -*- coding: utf-8 -*-
'''
Beacon to monitor network adapter setting changes on Linux

.. versionadded:: 2016.3.0

'''
from __future__ import absolute_import, unicode_literals
# Import third party libs
try:
    from pyroute2 import IPDB
    IP = IPDB()
    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False

import ast
import re
import salt.loader
import logging
from salt.ext.six.moves import map

log = logging.getLogger(__name__)

__virtual_name__ = 'network_settings'

ATTRS = ['family', 'txqlen', 'ipdb_scope', 'index', 'operstate', 'group',
         'carrier_changes', 'ipaddr', 'neighbours', 'ifname', 'promiscuity',
         'linkmode', 'broadcast', 'address', 'num_tx_queues', 'ipdb_priority',
         'kind', 'qdisc', 'mtu', 'num_rx_queues', 'carrier', 'flags',
         'ifi_type', 'ports']

LAST_STATS = {}


class Hashabledict(dict):
    '''
    Helper class that implements a hash function for a dictionary
    '''
    def __hash__(self):
        return hash(tuple(sorted(self.items())))


def __virtual__():
    if HAS_PYROUTE2:
        return __virtual_name__
    return False


def validate(config):
    '''
    Validate the beacon configuration
    '''
    if not isinstance(config, list):
        return False, ('Configuration for network_settings '
                       'beacon must be a list.')
    else:
        _config = {}
        list(map(_config.update, config))

        for item in _config.get('interfaces', {}):
            if not isinstance(_config['interfaces'][item], dict):
                return False, ('Configuration for network_settings beacon '
                               ' must be a list of dictionaries.')
            else:
                if not all(j in ATTRS for j in _config['interfaces'][item]):
                    return False, ('Invalid configuration item in Beacon '
                                   'configuration.')
    return True, 'Valid beacon configuration'


def _copy_interfaces_info(interfaces):
    '''
    Return a dictionary with a copy of each interface attributes in ATTRS
    '''
    ret = {}

    for interface in interfaces:
        _interface_attrs_cpy = set()
        for attr in ATTRS:
            if attr in interfaces[interface]:
                attr_dict = Hashabledict()
                attr_dict[attr] = repr(interfaces[interface][attr])
                _interface_attrs_cpy.add(attr_dict)
        ret[interface] = _interface_attrs_cpy

    return ret


def beacon(config):
    '''
    Watch for changes on network settings

    By default, the beacon will emit when there is a value change on one of the
    settings on watch. The config also support the onvalue parameter for each
    setting, which instruct the beacon to only emit if the setting changed to
    the value defined.

    Example Config

    .. code-block:: yaml

        beacons:
          network_settings:
            - interfaces:
                - eth0:
                    ipaddr:
                    promiscuity:
                      onvalue: 1
                - eth1:
                    linkmode:

    The config above will check for value changes on eth0 ipaddr and eth1 linkmode. It will also
    emit if the promiscuity value changes to 1.

    Beacon items can use the * wildcard to make a definition apply to several interfaces. For
    example an eth* would apply to all ethernet interfaces.

    Setting the argument coalesce = True will combine all the beacon results on a single event.
    The example below shows how to trigger coalesced results:

    .. code-block:: yaml

        beacons:
          network_settings:
            - coalesce: True
            - interfaces:
                - eth0:
                    ipaddr:
                    promiscuity:

    '''
    _config = {}
    list(map(_config.update, config))

    ret = []
    interfaces = []
    expanded_config = {}

    global LAST_STATS

    coalesce = False

    _stats = _copy_interfaces_info(IP.by_name)

    if not LAST_STATS:
        LAST_STATS = _stats

    if 'coalesce' in _config and _config['coalesce']:
        coalesce = True
        changes = {}

    log.debug('_stats %s', _stats)
    # Get list of interfaces included in config that are registered in the
    # system, including interfaces defined by wildcards (eth*, wlan*)
    for interface in _config.get('interfaces', {}):
        if interface in _stats:
            interfaces.append(interface)
        else:
            # No direct match, try with * wildcard regexp
            interface_regexp = interface.replace('*', '[0-9]+')
            for interface in _stats:
                match = re.search(interface_regexp, interface)
                if match:
                    interfaces.append(match.group())
                    expanded_config[match.group()] = config['interfaces'][interface]

    if expanded_config:
        config.update(expanded_config)

        # config updated so update _config
        list(map(_config.update, config))

    log.debug('interfaces %s', interfaces)
    for interface in interfaces:
        _send_event = False
        _diff_stats = _stats[interface] - LAST_STATS[interface]
        _ret_diff = {}
        interface_config = _config['interfaces'][interface]

        log.debug('_diff_stats %s', _diff_stats)
        if _diff_stats:
            _diff_stats_dict = {}
            LAST_STATS[interface] = _stats[interface]

            for item in _diff_stats:
                _diff_stats_dict.update(item)
            for attr in interface_config:
                if attr in _diff_stats_dict:
                    config_value = None
                    if interface_config[attr] and \
                       'onvalue' in interface_config[attr]:
                        config_value = interface_config[attr]['onvalue']
                    new_value = ast.literal_eval(_diff_stats_dict[attr])
                    if not config_value or config_value == new_value:
                        _send_event = True
                        _ret_diff[attr] = new_value

            if _send_event:
                if coalesce:
                    changes[interface] = _ret_diff
                else:
                    ret.append({'tag': interface,
                                'interface': interface,
                                'change': _ret_diff})

    if coalesce and changes:
        grains_info = salt.loader.grains(__opts__, True)
        __grains__.update(grains_info)
        ret.append({'tag': 'result', 'changes': changes})

    return ret
