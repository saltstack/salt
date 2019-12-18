# -*- coding: utf-8 -*-
'''
Grains for junos.
NOTE this is a little complicated--junos can only be accessed
via salt-proxy-minion.Thus, some grains make sense to get them
from the minion (PYTHONPATH), but others don't (ip_interfaces)
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
from salt.ext import six

__proxyenabled__ = ['junos']
__virtualname__ = 'junos'

# Get looging started
log = logging.getLogger(__name__)


def __virtual__():
    if 'proxy' not in __opts__:
        return False
    else:
        return __virtualname__


def _remove_complex_types(dictionary):
    '''
    Linode-python is now returning some complex types that
    are not serializable by msgpack.  Kill those.
    '''
    for k, v in six.iteritems(dictionary):
        if isinstance(v, dict):
            dictionary[k] = _remove_complex_types(v)
        elif hasattr(v, 'to_eng_string'):
            dictionary[k] = v.to_eng_string()

    return dictionary


def defaults():
    return {'os': 'proxy', 'kernel': 'unknown', 'osrelease': 'proxy'}


def facts(proxy=None):
    if proxy is None or proxy['junos.initialized']() is False:
        return {}
    return {'junos_facts': proxy['junos.get_serialized_facts']()}


def os_family():
    return {'os_family': 'junos'}
