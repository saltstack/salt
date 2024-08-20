"""
The networking module for Non-RH/Deb Linux distros
"""

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils

__virtualname__ = "ip"


def __virtual__():
    """
    Confine this module to Non-RH/Deb Linux distros
    """
    if salt.utils.platform.is_windows():
        return (False, "Module linux_ip: Windows systems are not supported.")
    if __grains__["os_family"] == "RedHat":
        return (False, "Module linux_ip: RedHat systems are not supported.")
    if __grains__["os_family"] == "Suse":
        return (False, "Module linux_ip: SUSE systems are not supported.")
    if __grains__["os_family"] == "Debian":
        return (False, "Module linux_ip: Debian systems are not supported.")
    if __grains__["os_family"] == "NILinuxRT":
        return (False, "Module linux_ip: NILinuxRT systems are not supported.")
    if not salt.utils.path.which("ip"):
        return (
            False,
            "The linux_ip execution module cannot be loaded: "
            "the ip binary is not in the path.",
        )
    return __virtualname__


def down(iface, iface_type=None):
    """
    Shutdown a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.down eth0
    """
    # Slave devices are controlled by the master.
    if iface_type not in ["slave"]:
        return __salt__["cmd.run"](f"ip link set {iface} down")
    return None


def get_interface(iface):
    """
    Return the contents of an interface script

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface eth0
    """
    ifaces = _ip_ifaces()
    return ifaces.get(iface)


def _ip_ifaces():
    """
    Parse output from 'ip a'
    """
    tmp = {}
    ret = {}
    if_ = None
    at_ = None
    out = __salt__["cmd.run"]("ip a")
    for line in out.splitlines():
        if not line.startswith(" "):
            comps = line.split(":")
            if_ = comps[1].strip()
            opts_comps = comps[2].strip().split()
            flags = opts_comps.pop(0).lstrip("<").rstrip(">").split(",")
            opts_iter = iter(opts_comps)
            ret[if_] = {
                "flags": flags,
                "options": dict(list(zip(opts_iter, opts_iter))),
            }
        else:
            if line.strip().startswith("link"):
                comps = iter(line.strip().split())
                ret[if_]["link_layer"] = dict(list(zip(comps, comps)))
            elif line.strip().startswith("inet"):
                comps = line.strip().split()
                at_ = comps[0]
                if len(comps) % 2 != 0:
                    last = comps.pop()
                    comps[-1] += f" {last}"
                ifi = iter(comps)
                ret[if_][at_] = dict(list(zip(ifi, ifi)))
            else:
                comps = line.strip().split()
                ifi = iter(comps)
                ret[if_][at_].update(dict(list(zip(ifi, ifi))))
    return ret


def up(iface, iface_type=None):
    """
    Start up a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.up eth0
    """
    # Slave devices are controlled by the master.
    if iface_type not in ["slave"]:
        return __salt__["cmd.run"](f"ip link set {iface} up")
    return None


def get_routes(iface=None):
    """
    Return the current routing table

    CLI Examples:

    .. code-block:: bash

        salt '*' ip.get_routes
        salt '*' ip.get_routes eth0
    """
    routes = _parse_routes()
    if iface is not None:
        return routes.get(iface)
    return routes


def _parse_routes():
    """
    Parse the contents of ``/proc/net/route``
    """
    with salt.utils.files.fopen("/proc/net/route", "r") as fp_:
        out = salt.utils.stringutils.to_unicode(fp_.read())

    ret = {}
    for line in out.splitlines():
        tmp = {}
        if not line.strip():
            continue
        if line.startswith("Iface"):
            continue
        comps = line.split()
        tmp["iface"] = comps[0]
        tmp["destination"] = _hex_to_octets(comps[1])
        tmp["gateway"] = _hex_to_octets(comps[2])
        tmp["flags"] = _route_flags(int(comps[3]))
        tmp["refcnt"] = comps[4]
        tmp["use"] = comps[5]
        tmp["metric"] = comps[6]
        tmp["mask"] = _hex_to_octets(comps[7])
        tmp["mtu"] = comps[8]
        tmp["window"] = comps[9]
        tmp["irtt"] = comps[10]
        if comps[0] not in ret:
            ret[comps[0]] = []
        ret[comps[0]].append(tmp)
    return ret


def _hex_to_octets(addr):
    """
    Convert hex fields from /proc/net/route to octects
    """
    return "{}:{}:{}:{}".format(
        int(addr[6:8], 16),
        int(addr[4:6], 16),
        int(addr[2:4], 16),
        int(addr[0:2], 16),
    )


def _route_flags(rflags):
    """
    https://github.com/torvalds/linux/blob/master/include/uapi/linux/route.h
    https://github.com/torvalds/linux/blob/master/include/uapi/linux/ipv6_route.h
    """
    flags = ""
    fmap = {
        0x0001: "U",  # RTF_UP, route is up
        0x0002: "G",  # RTF_GATEWAY, use gateway
        0x0004: "H",  # RTF_HOST, target is a host
        0x0008: "R",  # RET_REINSTATE, reinstate route for dynamic routing
        0x0010: "D",  # RTF_DYNAMIC, dynamically installed by daemon or redirect
        0x0020: "M",  # RTF_MODIFIED, modified from routing daemon or redirect
        0x00040000: "A",  # RTF_ADDRCONF, installed by addrconf
        0x01000000: "C",  # RTF_CACHE, cache entry
        0x0200: "!",  # RTF_REJECT, reject route
    }
    for item in fmap:
        if rflags & item:
            flags += fmap[item]
    return flags
