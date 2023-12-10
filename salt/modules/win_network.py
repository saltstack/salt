"""
Module for gathering and managing network information
"""

import datetime
import hashlib
import re
import socket

import salt.utils.network
import salt.utils.platform
import salt.utils.validate.net
from salt._compat import ipaddress
from salt.modules.network import (
    calc_net,
    convert_cidr,
    get_fqdn,
    get_hostname,
    ifacestartswith,
    interface,
    interface_ip,
    ip_in_subnet,
    iphexval,
    subnets6,
    wol,
)
from salt.utils.functools import namespaced_function

try:
    import salt.utils.winapi

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


try:
    import wmi  # pylint: disable=import-error
except ImportError:
    HAS_DEPENDENCIES = False

if salt.utils.platform.is_windows() and HAS_DEPENDENCIES:

    wol = namespaced_function(wol, globals())
    get_hostname = namespaced_function(get_hostname, globals())
    interface = namespaced_function(interface, globals())
    interface_ip = namespaced_function(interface_ip, globals())
    subnets6 = namespaced_function(subnets6, globals())
    ip_in_subnet = namespaced_function(ip_in_subnet, globals())
    convert_cidr = namespaced_function(convert_cidr, globals())
    calc_net = namespaced_function(calc_net, globals())
    get_fqdn = namespaced_function(get_fqdn, globals())
    ifacestartswith = namespaced_function(ifacestartswith, globals())
    iphexval = namespaced_function(iphexval, globals())


# Define the module's virtual name
__virtualname__ = "network"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_network: Only available on Windows"

    if not HAS_DEPENDENCIES:
        return False, "Module win_network: Missing dependencies"

    return __virtualname__


def ping(host, timeout=False, return_boolean=False):
    """
    Performs a ping to a host

    CLI Example:

    .. code-block:: bash

        salt '*' network.ping archlinux.org

    .. versionadded:: 2016.11.0

    Return a True or False instead of ping output.

    .. code-block:: bash

        salt '*' network.ping archlinux.org return_boolean=True

    Set the time to wait for a response in seconds.

    .. code-block:: bash

        salt '*' network.ping archlinux.org timeout=3
    """
    if timeout:
        # Windows ping differs by having timeout be for individual echo requests.'
        # Divide timeout by tries to mimic BSD behaviour.
        timeout = int(timeout) * 1000 // 4
        cmd = [
            "ping",
            "-n",
            "4",
            "-w",
            str(timeout),
            salt.utils.network.sanitize_host(host),
        ]
    else:
        cmd = ["ping", "-n", "4", salt.utils.network.sanitize_host(host)]
    if return_boolean:
        ret = __salt__["cmd.run_all"](cmd, python_shell=False)
        if ret["retcode"] != 0:
            return False
        else:
            return True
    else:
        return __salt__["cmd.run"](cmd, python_shell=False)


def netstat():
    """
    Return information on open ports and states

    CLI Example:

    .. code-block:: bash

        salt '*' network.netstat
    """
    ret = []
    cmd = ["netstat", "-nao"]
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in lines:
        comps = line.split()
        if line.startswith("  TCP"):
            ret.append(
                {
                    "local-address": comps[1],
                    "proto": comps[0],
                    "remote-address": comps[2],
                    "state": comps[3],
                    "program": comps[4],
                }
            )
        if line.startswith("  UDP"):
            ret.append(
                {
                    "local-address": comps[1],
                    "proto": comps[0],
                    "remote-address": comps[2],
                    "state": None,
                    "program": comps[3],
                }
            )
    return ret


def traceroute(host):
    """
    Performs a traceroute to a 3rd party host

    CLI Example:

    .. code-block:: bash

        salt '*' network.traceroute archlinux.org
    """
    ret = []
    cmd = ["tracert", salt.utils.network.sanitize_host(host)]
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in lines:
        if " " not in line:
            continue
        if line.startswith("Trac"):
            continue
        if line.startswith("over"):
            continue
        comps = line.split()
        complength = len(comps)
        # This method still needs to better catch rows of other lengths
        # For example if some of the ms returns are '*'
        if complength == 9:
            result = {
                "count": comps[0],
                "hostname": comps[7],
                "ip": comps[8],
                "ms1": comps[1],
                "ms2": comps[3],
                "ms3": comps[5],
            }
            ret.append(result)
        elif complength == 8:
            result = {
                "count": comps[0],
                "hostname": None,
                "ip": comps[7],
                "ms1": comps[1],
                "ms2": comps[3],
                "ms3": comps[5],
            }
            ret.append(result)
        else:
            result = {
                "count": comps[0],
                "hostname": None,
                "ip": None,
                "ms1": None,
                "ms2": None,
                "ms3": None,
            }
            ret.append(result)
    return ret


def nslookup(host):
    """
    Query DNS for information about a domain or ip address

    CLI Example:

    .. code-block:: bash

        salt '*' network.nslookup archlinux.org
    """
    ret = []
    addresses = []
    cmd = ["nslookup", salt.utils.network.sanitize_host(host)]
    lines = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in lines:
        if addresses:
            # We're in the last block listing addresses
            addresses.append(line.strip())
            continue
        if line.startswith("Non-authoritative"):
            continue
        if "Addresses" in line:
            comps = line.split(":", 1)
            addresses.append(comps[1].strip())
            continue
        if ":" in line:
            comps = line.split(":", 1)
            ret.append({comps[0].strip(): comps[1].strip()})
    if addresses:
        ret.append({"Addresses": addresses})
    return ret


def get_route(ip):
    """
    Return routing information for given destination ip

    .. versionadded:: 2016.11.5

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_route 10.10.10.10
    """
    cmd = "Find-NetRoute -RemoteIPAddress {}".format(ip)
    out = __salt__["cmd.run"](cmd, shell="powershell", python_shell=True)
    regexp = re.compile(
        r"^IPAddress\s+:\s(?P<source>[\d\.:]+)?.*"
        r"^InterfaceAlias\s+:\s(?P<interface>[\w\.\:\-\ ]+)?.*"
        r"^NextHop\s+:\s(?P<gateway>[\d\.:]+)",
        flags=re.MULTILINE | re.DOTALL,
    )
    m = regexp.search(out)
    ret = {
        "destination": ip,
        "gateway": m.group("gateway"),
        "interface": m.group("interface"),
        "source": m.group("source"),
    }

    return ret


def dig(host):
    """
    Performs a DNS lookup with dig

    Note: dig must be installed on the Windows minion

    CLI Example:

    .. code-block:: bash

        salt '*' network.dig archlinux.org
    """
    cmd = ["dig", salt.utils.network.sanitize_host(host)]
    return __salt__["cmd.run"](cmd, python_shell=False)


def interfaces_names():
    """
    Return a list of all the interfaces names

    CLI Example:

    .. code-block:: bash

        salt '*' network.interfaces_names
    """

    ret = []
    with salt.utils.winapi.Com():
        c = wmi.WMI()
        for iface in c.Win32_NetworkAdapter(NetEnabled=True):
            ret.append(iface.NetConnectionID)
    return ret


def interfaces():
    """
    Return a dictionary of information about all the interfaces on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' network.interfaces
    """
    return salt.utils.network.win_interfaces()


def hw_addr(iface):
    """
    Return the hardware address (a.k.a. MAC address) for a given interface

    CLI Example:

    .. code-block:: bash

        salt '*' network.hw_addr 'Wireless Connection #1'
    """
    return salt.utils.network.hw_addr(iface)


# Alias hwaddr to preserve backward compat
hwaddr = salt.utils.functools.alias_function(hw_addr, "hwaddr")


def subnets():
    """
    Returns a list of subnets to which the host belongs

    CLI Example:

    .. code-block:: bash

        salt '*' network.subnets
    """
    return salt.utils.network.subnets()


def in_subnet(cidr):
    """
    Returns True if host is within specified subnet, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' network.in_subnet 10.0.0.0/16
    """
    return salt.utils.network.in_subnet(cidr)


def ip_addrs(interface=None, include_loopback=False, cidr=None, type=None):
    """
    Returns a list of IPv4 addresses assigned to the host.

    interface
        Only IP addresses from that interface will be returned.

    include_loopback : False
        Include loopback 127.0.0.1 IPv4 address.

    cidr
        Describes subnet using CIDR notation and only IPv4 addresses that belong
        to this subnet will be returned.

      .. versionchanged:: 2019.2.0

    type
        If option set to 'public' then only public addresses will be returned.
        Ditto for 'private'.

        .. versionchanged:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs
        salt '*' network.ip_addrs cidr=10.0.0.0/8
        salt '*' network.ip_addrs cidr=192.168.0.0/16 type=private
    """
    addrs = salt.utils.network.ip_addrs(
        interface=interface, include_loopback=include_loopback
    )
    if cidr:
        return [i for i in addrs if salt.utils.network.in_subnet(cidr, [i])]
    else:
        if type == "public":
            return [i for i in addrs if not is_private(i)]
        elif type == "private":
            return [i for i in addrs if is_private(i)]
        else:
            return addrs


ipaddrs = salt.utils.functools.alias_function(ip_addrs, "ipaddrs")


def ip_addrs6(interface=None, include_loopback=False, cidr=None):
    """
    Returns a list of IPv6 addresses assigned to the host.

    interface
        Only IP addresses from that interface will be returned.

    include_loopback : False
        Include loopback ::1 IPv6 address.

    cidr
        Describes subnet using CIDR notation and only IPv6 addresses that belong
        to this subnet will be returned.

        .. versionchanged:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs6
        salt '*' network.ip_addrs6 cidr=2000::/3
    """
    addrs = salt.utils.network.ip_addrs6(
        interface=interface, include_loopback=include_loopback
    )
    if cidr:
        return [i for i in addrs if salt.utils.network.in_subnet(cidr, [i])]
    else:
        return addrs


ipaddrs6 = salt.utils.functools.alias_function(ip_addrs6, "ipaddrs6")


def connect(host, port=None, **kwargs):
    """
    Test connectivity to a host using a particular
    port from the minion.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.connect archlinux.org 80

        salt '*' network.connect archlinux.org 80 timeout=3

        salt '*' network.connect archlinux.org 80 timeout=3 family=ipv4

        salt '*' network.connect google-public-dns-a.google.com port=53 proto=udp timeout=3
    """

    ret = {"result": None, "comment": ""}

    if not host:
        ret["result"] = False
        ret["comment"] = "Required argument, host, is missing."
        return ret

    if not port:
        ret["result"] = False
        ret["comment"] = "Required argument, port, is missing."
        return ret

    proto = kwargs.get("proto", "tcp")
    timeout = kwargs.get("timeout", 5)
    family = kwargs.get("family", None)

    if salt.utils.validate.net.ipv4_addr(host) or salt.utils.validate.net.ipv6_addr(
        host
    ):
        address = host
    else:
        address = "{}".format(salt.utils.network.sanitize_host(host))

    # just in case we encounter error on getaddrinfo
    _address = ("unknown",)

    try:
        if proto == "udp":
            __proto = socket.SOL_UDP
        else:
            __proto = socket.SOL_TCP
            proto = "tcp"

        if family:
            if family == "ipv4":
                __family = socket.AF_INET
            elif family == "ipv6":
                __family = socket.AF_INET6
            else:
                __family = 0
        else:
            __family = 0

        (family, socktype, _proto, garbage, _address) = socket.getaddrinfo(
            address, port, __family, 0, __proto
        )[0]

        skt = socket.socket(family, socktype, _proto)
        skt.settimeout(timeout)

        if proto == "udp":
            # Generate a random string of a
            # decent size to test UDP connection
            md5h = hashlib.md5()
            md5h.update(datetime.datetime.now().strftime("%s"))
            msg = md5h.hexdigest()
            skt.sendto(msg, _address)
            recv, svr = skt.recvfrom(255)
            skt.close()
        else:
            skt.connect(_address)
            skt.shutdown(2)
    except Exception as exc:  # pylint: disable=broad-except
        ret["result"] = False
        ret["comment"] = "Unable to connect to {} ({}) on {} port {}".format(
            host, _address[0], proto, port
        )
        return ret

    ret["result"] = True
    ret["comment"] = "Successfully connected to {} ({}) on {} port {}".format(
        host, _address[0], proto, port
    )
    return ret


def is_private(ip_addr):
    """
    Check if the given IP address is a private address

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.is_private 10.0.0.3
    """
    return ipaddress.ip_address(ip_addr).is_private
