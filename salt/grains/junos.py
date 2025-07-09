"""
Grains for junos.
NOTE this is a little complicated--junos can only be accessed
via salt-proxy-minion. Thus, some grains make sense to get them
from the minion (PYTHONPATH), but others don't (ip_interfaces)
"""

import logging

import salt.utils.platform

__proxyenabled__ = ["junos"]
__virtualname__ = "junos"

# Get looging started
log = logging.getLogger(__name__)


def __virtual__():
    if "proxy" not in __opts__:
        return False
    else:
        return __virtualname__


def _remove_complex_types(dictionary):
    """
    junos-eznc is now returning some complex types that
    are not serializable by msgpack.  Kill those.
    """
    for k, v in dictionary.items():
        if isinstance(v, dict):
            dictionary[k] = _remove_complex_types(v)
        elif hasattr(v, "to_eng_string"):
            dictionary[k] = v.to_eng_string()

    return dictionary


def defaults():
    if salt.utils.platform.is_proxy():
        return {"os": "proxy", "kernel": "unknown", "osrelease": "proxy"}
    else:
        return {
            "os": "junos",
            "kernel": "junos",
            "osrelease": "junos FIXME",
        }


def facts(proxy=None):
    if proxy is None or proxy["junos.initialized"]() is False:
        return {}

    ret_value = proxy["junos.get_serialized_facts"]()
    if salt.utils.platform.is_proxy():
        ret = {"junos_facts": ret_value}
    else:
        ret = {"junos_facts": ret_value, "osrelease": ret_value["version"]}

    return ret


def os_family():
    return {"os_family": "junos"}
