# -*- coding: utf-8 -*-
"""
Support for Wireless Tools for Linux
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.path
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if iwconfig is installed
    """
    if salt.utils.path.which("iwconfig"):
        return True
    return (
        False,
        "The iwtools execution module cannot be loaded: iwconfig is not installed.",
    )


def scan(iface, style=None):
    """
    List networks on a wireless interface

    CLI Examples:

        salt minion iwtools.scan wlp3s0
        salt minion iwtools.scan wlp3s0 list
    """
    if not _valid_iface(iface):
        raise SaltInvocationError("The interface specified is not valid")

    out = __salt__["cmd.run"]("iwlist {0} scan".format(iface))
    if "Network is down" in out:
        __salt__["cmd.run"]("ip link set {0} up".format(iface))
        out = __salt__["cmd.run"]("iwlist {0} scan".format(iface))
    ret = {}
    tmp = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        if "Scan completed" in line:
            continue
        if line.strip().startswith("Cell"):
            comps = line.split(" - ")
            line = comps[1]
            if tmp:
                ret[tmp["Address"]] = tmp
                tmp = {}
        comps = line.split(":")
        if comps[0].strip() == "Address":
            # " is a valid character in SSIDs, but iwlist likes to wrap SSIDs in them
            comps[1] = comps[1].lstrip('"').rstrip('"')
        if comps[0].strip() == "IE":
            if "IE" not in tmp:
                tmp["IE"] = []
            tmp["IE"].append(":".join(comps[1:]).strip())
        else:
            tmp[comps[0].strip()] = ":".join(comps[1:]).strip()

    ret[tmp["Address"]] = tmp

    if style == "list":
        return ret.keys()

    return ret


def set_mode(iface, mode):
    """
    List networks on a wireless interface

    CLI Example:

        salt minion iwtools.set_mode wlp3s0 Managed
    """
    if not _valid_iface(iface):
        raise SaltInvocationError("The interface specified is not valid")

    valid_modes = (
        "Managed",
        "Ad-Hoc",
        "Master",
        "Repeater",
        "Secondary",
        "Monitor",
        "Auto",
    )
    if mode not in valid_modes:
        raise SaltInvocationError(
            "One of the following modes must be specified: {0}".format(
                ", ".join(valid_modes)
            )
        )
    __salt__["ip.down"](iface)
    out = __salt__["cmd.run"]("iwconfig {0} mode {1}".format(iface, mode))
    __salt__["ip.up"](iface)

    return mode


def _valid_iface(iface):
    """
    Validate the specified interface
    """
    ifaces = list_interfaces()
    if iface in ifaces.keys():
        return True
    return False


def list_interfaces(style=None):
    """
    List all of the wireless interfaces

    CLI Example:

        salt minion iwtools.list_interfaces
    """
    ret = {}
    tmp = None
    iface = None
    out = __salt__["cmd.run"]("iwconfig")
    for line in out.splitlines():
        if not line:
            continue
        if "no wireless extensions" in line:
            continue
        comps = line.strip().split("  ")
        if not line.startswith(" "):
            if tmp is not None:
                ret[iface] = tmp.copy()
            iface = comps.pop(0)
            tmp = {"extra": []}
        for item in comps:
            if ":" in item:
                parts = item.split(":")
                key = parts[0].strip()
                value = parts[1].strip()
                if key == "ESSID":
                    value = value.lstrip('"').rstrip('"')
                tmp[key] = value
            elif "=" in item:
                parts = item.split("=")
                tmp[parts[0].strip()] = parts[1].strip()
            else:
                tmp["extra"].append(item)

    ret[iface] = tmp.copy()

    if style == "list":
        return ret.keys()

    return ret
