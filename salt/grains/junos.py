# -*- coding: utf-8 -*-
"""
Grains for junos.
NOTE this is a little complicated--junos can only be accessed
via salt-proxy-minion.Thus, some grains make sense to get them
from the minion (PYTHONPATH), but others don't (ip_interfaces)
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.platform
from salt.ext import six

__proxyenabled__ = ["junos"]
__virtualname__ = "junos"

# Get looging started
log = logging.getLogger(__name__)


def __virtual__():
    if not salt.utils.platform.is_proxy():
        return False, "junos: Not a proxy minion"
    try:
        if not __opts__["proxy"]["proxytype"] == "junos":
            return False, "junos: Missing proxy configuration"
    except KeyError:
        return False, "junos: Missing proxy configuration"

    return __virtualname__


def _remove_complex_types(dictionary):
    """
    Linode-python is now returning some complex types that
    are not serializable by msgpack.  Kill those.
    """
    for k, v in six.iteritems(dictionary):
        if isinstance(v, dict):
            dictionary[k] = _remove_complex_types(v)
        elif hasattr(v, "to_eng_string"):
            dictionary[k] = v.to_eng_string()

    return dictionary


def defaults():
    return {"os": "proxy", "kernel": "unknown", "osrelease": "proxy"}


def facts(proxy=None):
    if proxy is None or proxy["junos.initialized"]() is False:
        return {}
    return {"junos_facts": proxy["junos.get_serialized_facts"]()}


def os_family():
    return {"os_family": "junos"}
