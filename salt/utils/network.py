# pylint: disable=invalid-name
"""
Define some generic socket functions for network modules
"""


import fnmatch
import itertools
import logging
import os
import platform
import random
import re
import socket
import subprocess
import types
from collections.abc import Mapping, Sequence
from string import ascii_letters, digits

import salt.utils.args
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.zeromq
from salt._compat import ipaddress
from salt.exceptions import SaltClientError, SaltSystemExit
from salt.utils.decorators.jinja import jinja_filter
from salt.utils.versions import LooseVersion

try:
    import salt.utils.win_network

    WIN_NETWORK_LOADED = True
except ImportError:
    WIN_NETWORK_LOADED = False

log = logging.getLogger(__name__)

try:
    import ctypes
    import ctypes.util

    LIBC = ctypes.cdll.LoadLibrary(ctypes.util.find_library("c"))
    RES_INIT = LIBC.__res_init
except (ImportError, OSError, AttributeError, TypeError):
    pass


class Interfaces:
    __slots__ = ("interfaces",)

    def __init__(self, interfaces=None):
        if interfaces is None:
            interfaces = {}
        self.interfaces = interfaces

    def __call__(self, *args, **kwargs):
        if not self.interfaces:
            self.interfaces = interfaces()
        return self.interfaces

    def clear(self):
        self.interfaces = {}


_get_interfaces = Interfaces()
_clear_interfaces = _get_interfaces.clear


def sanitize_host(host):
    """
    Sanitize host string.
    https://tools.ietf.org/html/rfc1123#section-2.1
    """
    RFC952_characters = ascii_letters + digits + ".-_"
    return "".join([c for c in host[0:255] if c in RFC952_characters])


def isportopen(host, port):
    """
    Return status of a port
    """

    if not 1 <= int(port) <= 65535:
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    out = sock.connect_ex((sanitize_host(host), int(port)))

    return out


def host_to_ips(host):
    """
    Returns a list of IP addresses of a given hostname or None if not found.
    """
    ips = []
    try:
        for family, socktype, proto, canonname, sockaddr in socket.getaddrinfo(
            host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM
        ):
            if family == socket.AF_INET:
                ip, port = sockaddr
            elif family == socket.AF_INET6:
                ip, port, flow_info, scope_id = sockaddr
            ips.append(ip)
        if not ips:
            ips = None
    except Exception:  # pylint: disable=broad-except
        ips = None
    return ips


def _generate_minion_id():
    """
    Get list of possible host names and convention names.

    :return:
    """
    # There are three types of hostnames:
    # 1. Network names. How host is accessed from the network.
    # 2. Host aliases. They might be not available in all the network or only locally (/etc/hosts)
    # 3. Convention names, an internal nodename.

    class DistinctList(list):
        """
        List, which allows one to append only distinct objects.
        Needs to work on Python 2.6, because of collections.OrderedDict only since 2.7 version.
        Override 'filter()' for custom filtering.
        """

        localhost_matchers = [
            r"localhost.*",
            r"ip6-.*",
            r"127[.]\d",
            r"0\.0\.0\.0",
            r"::1.*",
            r"ipv6-.*",
            r"fe00::.*",
            r"fe02::.*",
            r"1.0.0.*.ip6.arpa",
        ]

        def append(self, p_object):
            if p_object and p_object not in self and not self.filter(p_object):
                super().append(p_object)
            return self

        def extend(self, iterable):
            for obj in iterable:
                self.append(obj)
            return self

        def filter(self, element):
            "Returns True if element needs to be filtered"
            for rgx in self.localhost_matchers:
                if re.match(rgx, element):
                    return True

        def first(self):
            return self and self[0] or None

    hostname = socket.gethostname()

    hosts = (
        DistinctList()
        .append(
            salt.utils.stringutils.to_unicode(
                socket.getfqdn(salt.utils.stringutils.to_bytes(hostname))
            )
        )
        .append(platform.node())
        .append(hostname)
    )
    if not hosts:
        try:
            for a_nfo in socket.getaddrinfo(
                hosts.first() or "localhost",
                None,
                socket.AF_INET,
                socket.SOCK_RAW,
                socket.IPPROTO_IP,
                socket.AI_CANONNAME,
            ):
                if len(a_nfo) > 3:
                    hosts.append(a_nfo[3])
        except socket.gaierror:
            log.warning(
                "Cannot resolve address %s info via socket: %s",
                hosts.first() or "localhost (N/A)",
                socket.gaierror,
            )
    # Universal method for everywhere (Linux, Slowlaris, Windows etc)
    for f_name in (
        "/etc/hostname",
        "/etc/nodename",
        "/etc/hosts",
        r"{win}\system32\drivers\etc\hosts".format(win=os.getenv("WINDIR")),
    ):
        try:
            with salt.utils.files.fopen(f_name) as f_hdl:
                for line in f_hdl:
                    line = salt.utils.stringutils.to_unicode(line)
                    hst = line.strip().split("#")[0].strip().split()
                    if hst:
                        if hst[0][:4] in ("127.", "::1") or len(hst) == 1:
                            hosts.extend(hst)
        except OSError:
            pass

    # include public and private ipaddresses
    return hosts.extend(
        [addr for addr in ip_addrs() if not ipaddress.ip_address(addr).is_loopback]
    )


def generate_minion_id():
    """
    Return only first element of the hostname from all possible list.

    :return:
    """
    try:
        ret = salt.utils.stringutils.to_unicode(_generate_minion_id().first())
    except TypeError:
        ret = None
    return ret or "localhost"


def get_socket(addr, type=socket.SOCK_STREAM, proto=0):
    """
    Return a socket object for the addr
    IP-version agnostic
    """

    version = ipaddress.ip_address(addr).version
    if version == 4:
        family = socket.AF_INET
    elif version == 6:
        family = socket.AF_INET6
    return socket.socket(family, type, proto)


def get_fqhostname():
    """
    Returns the fully qualified hostname
    """
    l = [socket.getfqdn()]

    # try socket.getaddrinfo
    try:
        addrinfo = socket.getaddrinfo(
            socket.gethostname(),
            0,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
            socket.SOL_TCP,
            socket.AI_CANONNAME,
        )
        for info in addrinfo:
            # info struct [family, socktype, proto, canonname, sockaddr]
            # On Windows `canonname` can be an empty string
            # This can cause the function to return `None`
            if len(info) >= 4 and info[3]:
                l = [info[3]]
    except socket.gaierror:
        pass

    return l and l[0] or None


def ip_to_host(ip):
    """
    Returns the hostname of a given IP
    """
    try:
        hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ip)
    except Exception as exc:  # pylint: disable=broad-except
        log.debug("salt.utils.network.ip_to_host(%r) failed: %s", ip, exc)
        hostname = None
    return hostname


def is_reachable_host(entity_name):
    """
    Returns a bool telling if the entity name is a reachable host (IPv4/IPv6/FQDN/etc).
    :param hostname:
    :return:
    """
    try:
        assert type(socket.getaddrinfo(entity_name, 0, 0, 0, 0)) == list
        ret = True
    except socket.gaierror:
        ret = False

    return ret


def is_ip(ip_addr):
    """
    Returns a bool telling if the passed IP is a valid IPv4 or IPv6 address.
    """
    return is_ipv4(ip_addr) or is_ipv6(ip_addr)


def is_ipv4(ip_addr):
    """
    Returns a bool telling if the value passed to it was a valid IPv4 address
    """
    try:
        return ipaddress.ip_address(ip_addr).version == 4
    except ValueError:
        return False


def is_ipv6(ip_addr):
    """
    Returns a bool telling if the value passed to it was a valid IPv6 address
    """
    try:
        return ipaddress.ip_address(ip_addr).version == 6
    except ValueError:
        return False


def is_subnet(cidr):
    """
    Returns a bool telling if the passed string is an IPv4 or IPv6 subnet
    """
    return is_ipv4_subnet(cidr) or is_ipv6_subnet(cidr)


def is_ipv4_subnet(cidr):
    """
    Returns a bool telling if the passed string is an IPv4 subnet
    """
    try:
        return "/" in cidr and bool(ipaddress.IPv4Network(cidr))
    except Exception:  # pylint: disable=broad-except
        return False


def is_ipv6_subnet(cidr):
    """
    Returns a bool telling if the passed string is an IPv6 subnet
    """
    try:
        return "/" in cidr and bool(ipaddress.IPv6Network(cidr))
    except Exception:  # pylint: disable=broad-except
        return False


@jinja_filter("is_ip")
def is_ip_filter(ip_addr, options=None):
    """
    Returns a bool telling if the passed IP is a valid IPv4 or IPv6 address.
    """
    return is_ipv4_filter(ip_addr, options=options) or is_ipv6_filter(
        ip_addr, options=options
    )


def _ip_options_global(ip_obj, version):
    return not ip_obj.is_private


def _ip_options_multicast(ip_obj, version):
    return ip_obj.is_multicast


def _ip_options_loopback(ip_obj, version):
    return ip_obj.is_loopback


def _ip_options_link_local(ip_obj, version):
    return ip_obj.is_link_local


def _ip_options_private(ip_obj, version):
    return ip_obj.is_private


def _ip_options_reserved(ip_obj, version):
    return ip_obj.is_reserved


def _ip_options_site_local(ip_obj, version):
    if version == 6:
        return ip_obj.is_site_local
    return False


def _ip_options_unspecified(ip_obj, version):
    return ip_obj.is_unspecified


def _ip_options(ip_obj, version, options=None):

    # will process and IP options
    options_fun_map = {
        "global": _ip_options_global,
        "link-local": _ip_options_link_local,
        "linklocal": _ip_options_link_local,
        "ll": _ip_options_link_local,
        "link_local": _ip_options_link_local,
        "loopback": _ip_options_loopback,
        "lo": _ip_options_loopback,
        "multicast": _ip_options_multicast,
        "private": _ip_options_private,
        "public": _ip_options_global,
        "reserved": _ip_options_reserved,
        "site-local": _ip_options_site_local,
        "sl": _ip_options_site_local,
        "site_local": _ip_options_site_local,
        "unspecified": _ip_options_unspecified,
    }

    if not options:
        return str(ip_obj)  # IP version already checked

    options_list = [option.strip() for option in options.split(",")]

    for option, fun in options_fun_map.items():
        if option in options_list:
            fun_res = fun(ip_obj, version)
            if not fun_res:
                return None
                # stop at first failed test
            # else continue
    return str(ip_obj)


def _is_ipv(ip_addr, version, options=None):

    if not version:
        version = 4

    if version not in (4, 6):
        return None

    try:
        ip_obj = ipaddress.ip_address(ip_addr)
    except ValueError:
        # maybe it is an IP network
        try:
            ip_obj = ipaddress.ip_interface(ip_addr)
        except ValueError:
            # nope, still not :(
            return None

    if not ip_obj.version == version:
        return None

    # has the right version, let's move on
    return _ip_options(ip_obj, version, options=options)


@jinja_filter("is_ipv4")
def is_ipv4_filter(ip_addr, options=None):
    """
    Returns a bool telling if the value passed to it was a valid IPv4 address.

    ip
        The IP address.

    net: False
        Consider IP addresses followed by netmask.

    options
        CSV of options regarding the nature of the IP address. E.g.: loopback, multicast, private etc.
    """
    _is_ipv4 = _is_ipv(ip_addr, 4, options=options)
    return isinstance(_is_ipv4, str)


@jinja_filter("is_ipv6")
def is_ipv6_filter(ip_addr, options=None):
    """
    Returns a bool telling if the value passed to it was a valid IPv6 address.

    ip
        The IP address.

    net: False
        Consider IP addresses followed by netmask.

    options
        CSV of options regarding the nature of the IP address. E.g.: loopback, multicast, private etc.
    """
    _is_ipv6 = _is_ipv(ip_addr, 6, options=options)
    return isinstance(_is_ipv6, str)


def _ipv_filter(value, version, options=None):

    if version not in (4, 6):
        return

    if isinstance(value, (str, bytes)):
        return _is_ipv(
            value, version, options=options
        )  # calls is_ipv4 or is_ipv6 for `value`
    elif isinstance(value, (list, tuple, types.GeneratorType)):
        # calls is_ipv4 or is_ipv6 for each element in the list
        # os it filters and returns only those elements having the desired IP version
        return [
            _is_ipv(addr, version, options=options)
            for addr in value
            if _is_ipv(addr, version, options=options) is not None
        ]
    return None


@jinja_filter("ipv4")
def ipv4(value, options=None):
    """
    Filters a list and returns IPv4 values only.
    """
    return _ipv_filter(value, 4, options=options)


@jinja_filter("ipv6")
def ipv6(value, options=None):
    """
    Filters a list and returns IPv6 values only.
    """
    return _ipv_filter(value, 6, options=options)


@jinja_filter("ipaddr")
def ipaddr(value, options=None):
    """
    Filters and returns only valid IP objects.
    """
    ipv4_obj = ipv4(value, options=options)
    ipv6_obj = ipv6(value, options=options)
    if ipv4_obj is None or ipv6_obj is None:
        # an IP address can be either IPv4 either IPv6
        # therefofe if the value passed as arg is not a list, at least one of the calls above will return None
        # if one of them is none, means that we should return only one of them
        return ipv4_obj or ipv6_obj  # one of them
    else:
        return ipv4_obj + ipv6_obj  # extend lists


def _filter_ipaddr(value, options, version=None):
    ipaddr_filter_out = None
    if version:
        if version == 4:
            ipaddr_filter_out = ipv4(value, options)
        elif version == 6:
            ipaddr_filter_out = ipv6(value, options)
    else:
        ipaddr_filter_out = ipaddr(value, options)
    if not ipaddr_filter_out:
        return
    if not isinstance(ipaddr_filter_out, (list, tuple, types.GeneratorType)):
        ipaddr_filter_out = [ipaddr_filter_out]
    return ipaddr_filter_out


@jinja_filter("ip_host")
def ip_host(value, options=None, version=None):
    """
    Returns the interfaces IP address, e.g.: 192.168.0.1/28.
    """
    ipaddr_filter_out = _filter_ipaddr(value, options=options, version=version)
    if not ipaddr_filter_out:
        return
    if not isinstance(value, (list, tuple, types.GeneratorType)):
        return str(ipaddress.ip_interface(ipaddr_filter_out[0]))
    return [str(ipaddress.ip_interface(ip_a)) for ip_a in ipaddr_filter_out]


def _network_hosts(ip_addr_entry):
    return [
        str(host) for host in ipaddress.ip_network(ip_addr_entry, strict=False).hosts()
    ]


@jinja_filter("network_hosts")
def network_hosts(value, options=None, version=None):
    """
    Return the list of hosts within a network.

    .. note::

        When running this command with a large IPv6 network, the command will
        take a long time to gather all of the hosts.
    """
    ipaddr_filter_out = _filter_ipaddr(value, options=options, version=version)
    if not ipaddr_filter_out:
        return
    if not isinstance(value, (list, tuple, types.GeneratorType)):
        return _network_hosts(ipaddr_filter_out[0])
    return [_network_hosts(ip_a) for ip_a in ipaddr_filter_out]


def _network_size(ip_addr_entry):
    return ipaddress.ip_network(ip_addr_entry, strict=False).num_addresses


@jinja_filter("network_size")
def network_size(value, options=None, version=None):
    """
    Get the size of a network.
    """
    ipaddr_filter_out = _filter_ipaddr(value, options=options, version=version)
    if not ipaddr_filter_out:
        return
    if not isinstance(value, (list, tuple, types.GeneratorType)):
        return _network_size(ipaddr_filter_out[0])
    return [_network_size(ip_a) for ip_a in ipaddr_filter_out]


def natural_ipv4_netmask(ip_addr, fmt="prefixlen"):
    """
    Returns the "natural" mask of an IPv4 address
    """
    bits = _ipv4_to_bits(ip_addr)

    if bits.startswith("11"):
        mask = "24"
    elif bits.startswith("1"):
        mask = "16"
    else:
        mask = "8"

    if fmt == "netmask":
        return cidr_to_ipv4_netmask(mask)
    else:
        return "/" + mask


def rpad_ipv4_network(ip_addr):
    """
    Returns an IP network address padded with zeros.

    Ex: '192.168.3' -> '192.168.3.0'
        '10.209' -> '10.209.0.0'
    """
    return ".".join(itertools.islice(itertools.chain(ip_addr.split("."), "0000"), 0, 4))


def cidr_to_ipv4_netmask(cidr_bits):
    """
    Returns an IPv4 netmask
    """
    try:
        cidr_bits = int(cidr_bits)
        if not 1 <= cidr_bits <= 32:
            return ""
    except ValueError:
        return ""

    netmask = ""
    for idx in range(4):
        if idx:
            netmask += "."
        if cidr_bits >= 8:
            netmask += "255"
            cidr_bits -= 8
        else:
            netmask += "{:d}".format(256 - (2 ** (8 - cidr_bits)))
            cidr_bits = 0
    return netmask


def _number_of_set_bits_to_ipv4_netmask(set_bits):
    """
    Returns an IPv4 netmask from the integer representation of that mask.

    Ex. 0xffffff00 -> '255.255.255.0'
    """
    return cidr_to_ipv4_netmask(_number_of_set_bits(set_bits))


def _number_of_set_bits(x):
    """
    Returns the number of bits that are set in a 32bit int
    """
    # Taken from http://stackoverflow.com/a/4912729. Many thanks!
    x -= (x >> 1) & 0x55555555
    x = ((x >> 2) & 0x33333333) + (x & 0x33333333)
    x = ((x >> 4) + x) & 0x0F0F0F0F
    x += x >> 8
    x += x >> 16
    return x & 0x0000003F


def _interfaces_ip(out):
    """
    Uses ip to return a dictionary of interfaces with various information about
    each (up/down state, ip address, netmask, and hwaddr)
    """
    ret = dict()

    def parse_network(value, cols):
        """
        Return a tuple of ip, netmask, broadcast
        based on the current set of cols
        """
        brd = None
        scope = None
        if "/" in value:  # we have a CIDR in this address
            ip, cidr = value.split("/")
        else:
            ip = value
            cidr = 32

        if type_ == "inet":
            mask = cidr_to_ipv4_netmask(int(cidr))
            if "brd" in cols:
                brd = cols[cols.index("brd") + 1]
        elif type_ == "inet6":
            mask = cidr
            if "scope" in cols:
                scope = cols[cols.index("scope") + 1]
        return (ip, mask, brd, scope)

    groups = re.compile("\r?\n\\d").split(out)
    for group in groups:
        iface = None
        data = dict()

        for line in group.splitlines():
            if " " not in line:
                continue
            match = re.match(r"^\d*:\s+([\w.\-]+)(?:@)?([\w.\-]+)?:\s+<(.+)>", line)
            if match:
                iface, parent, attrs = match.groups()
                if "UP" in attrs.split(","):
                    data["up"] = True
                else:
                    data["up"] = False
                if parent:
                    data["parent"] = parent
                continue

            cols = line.split()
            if len(cols) >= 2:
                type_, value = tuple(cols[0:2])
                iflabel = cols[-1:][0]
                if type_ in ("inet", "inet6"):
                    if "secondary" not in cols:
                        ipaddr, netmask, broadcast, scope = parse_network(value, cols)
                        if type_ == "inet":
                            if "inet" not in data:
                                data["inet"] = list()
                            addr_obj = dict()
                            addr_obj["address"] = ipaddr
                            addr_obj["netmask"] = netmask
                            addr_obj["broadcast"] = broadcast
                            addr_obj["label"] = iflabel
                            data["inet"].append(addr_obj)
                        elif type_ == "inet6":
                            if "inet6" not in data:
                                data["inet6"] = list()
                            addr_obj = dict()
                            addr_obj["address"] = ipaddr
                            addr_obj["prefixlen"] = netmask
                            addr_obj["scope"] = scope
                            data["inet6"].append(addr_obj)
                    else:
                        if "secondary" not in data:
                            data["secondary"] = list()
                        ip_, mask, brd, scp = parse_network(value, cols)
                        data["secondary"].append(
                            {
                                "type": type_,
                                "address": ip_,
                                "netmask": mask,
                                "broadcast": brd,
                                "label": iflabel,
                            }
                        )
                        del ip_, mask, brd, scp
                elif type_.startswith("link"):
                    data["hwaddr"] = value
        if iface:
            ret[iface] = data
            del iface, data
    return ret


def _interfaces_ifconfig(out):
    """
    Uses ifconfig to return a dictionary of interfaces with various information
    about each (up/down state, ip address, netmask, and hwaddr)
    """
    ret = dict()

    piface = re.compile(r"^([^\s:]+)")
    pmac = re.compile(".*?(?:HWaddr|ether|address:|lladdr) ([0-9a-fA-F:]+)")
    if salt.utils.platform.is_sunos():
        pip = re.compile(r".*?(?:inet\s+)([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)(.*)")
        pip6 = re.compile(".*?(?:inet6 )([0-9a-fA-F:]+)")
        pmask6 = re.compile(r".*?(?:inet6 [0-9a-fA-F:]+/(\d+)).*")
    else:
        pip = re.compile(r".*?(?:inet addr:|inet [^\d]*)(.*?)\s")
        pip6 = re.compile(".*?(?:inet6 addr: (.*?)/|inet6 )([0-9a-fA-F:]+)")
        pmask6 = re.compile(
            r".*?(?:inet6 addr: [0-9a-fA-F:]+/(\d+)|prefixlen (\d+))(?:"
            r" Scope:([a-zA-Z]+)| scopeid (0x[0-9a-fA-F]))?"
        )
    pmask = re.compile(r".*?(?:Mask:|netmask )(?:((?:0x)?[0-9a-fA-F]{8})|([\d\.]+))")
    pupdown = re.compile("UP")
    pbcast = re.compile(r".*?(?:Bcast:|broadcast )([\d\.]+)")

    groups = re.compile("\r?\n(?=\\S)").split(out)
    for group in groups:
        data = dict()
        iface = ""
        updown = False
        for line in group.splitlines():
            miface = piface.match(line)
            mmac = pmac.match(line)
            mip = pip.match(line)
            mip6 = pip6.match(line)
            mupdown = pupdown.search(line)
            if miface:
                iface = miface.group(1)
            if mmac:
                data["hwaddr"] = mmac.group(1)
                if salt.utils.platform.is_sunos():
                    expand_mac = []
                    for chunk in data["hwaddr"].split(":"):
                        expand_mac.append(
                            "0{}".format(chunk)
                            if len(chunk) < 2
                            else "{}".format(chunk)
                        )
                    data["hwaddr"] = ":".join(expand_mac)
            if mip:
                if "inet" not in data:
                    data["inet"] = list()
                addr_obj = dict()
                addr_obj["address"] = mip.group(1)
                mmask = pmask.match(line)
                if mmask:
                    if mmask.group(1):
                        mmask = _number_of_set_bits_to_ipv4_netmask(
                            int(mmask.group(1), 16)
                        )
                    else:
                        mmask = mmask.group(2)
                    addr_obj["netmask"] = mmask
                mbcast = pbcast.match(line)
                if mbcast:
                    addr_obj["broadcast"] = mbcast.group(1)
                data["inet"].append(addr_obj)
            if mupdown:
                updown = True
            if mip6:
                if "inet6" not in data:
                    data["inet6"] = list()
                addr_obj = dict()
                addr_obj["address"] = mip6.group(1) or mip6.group(2)
                mmask6 = pmask6.match(line)
                if mmask6:
                    addr_obj["prefixlen"] = mmask6.group(1) or mmask6.group(2)
                    if not salt.utils.platform.is_sunos():
                        ipv6scope = mmask6.group(3) or mmask6.group(4)
                        addr_obj["scope"] = (
                            ipv6scope.lower() if ipv6scope is not None else ipv6scope
                        )
                # SunOS sometimes has ::/0 as inet6 addr when using addrconf
                if (
                    not salt.utils.platform.is_sunos()
                    or addr_obj["address"] != "::"
                    and addr_obj["prefixlen"] != 0
                ):
                    data["inet6"].append(addr_obj)
        data["up"] = updown
        if iface in ret:
            # SunOS optimization, where interfaces occur twice in 'ifconfig -a'
            # output with the same name: for ipv4 and then for ipv6 addr family.
            # Every instance has its own 'UP' status and we assume that ipv4
            # status determines global interface status.
            #
            # merge items with higher priority for older values
            # after that merge the inet and inet6 sub items for both
            ret[iface] = dict(list(data.items()) + list(ret[iface].items()))
            if "inet" in data:
                ret[iface]["inet"].extend(
                    x for x in data["inet"] if x not in ret[iface]["inet"]
                )
            if "inet6" in data:
                ret[iface]["inet6"].extend(
                    x for x in data["inet6"] if x not in ret[iface]["inet6"]
                )
        else:
            ret[iface] = data
        del data
    return ret


def linux_interfaces():
    """
    Obtain interface information for *NIX/BSD variants
    """
    ifaces = dict()
    ip_path = salt.utils.path.which("ip")
    ifconfig_path = None if ip_path else salt.utils.path.which("ifconfig")
    if ip_path:
        cmd1 = subprocess.Popen(
            [ip_path, "link", "show"],
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).communicate()[0]
        cmd2 = subprocess.Popen(
            [ip_path, "addr", "show"],
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).communicate()[0]
        ifaces = _interfaces_ip(
            "{}\n{}".format(
                salt.utils.stringutils.to_str(cmd1), salt.utils.stringutils.to_str(cmd2)
            )
        )
    elif ifconfig_path:
        cmd = subprocess.Popen(
            [ifconfig_path, "-a"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).communicate()[0]
        ifaces = _interfaces_ifconfig(salt.utils.stringutils.to_str(cmd))
    return ifaces


def _netbsd_interfaces_ifconfig(out):
    """
    Uses ifconfig to return a dictionary of interfaces with various information
    about each (up/down state, ip address, netmask, and hwaddr)
    """
    ret = dict()

    piface = re.compile(r"^([^\s:]+)")
    pmac = re.compile(".*?address: ([0-9a-f:]+)")

    pip = re.compile(r".*?inet [^\d]*(.*?)/([\d]*)\s")
    pip6 = re.compile(r".*?inet6 ([0-9a-f:]+)%([a-zA-Z0-9]*)/([\d]*)\s")

    pupdown = re.compile("UP")
    pbcast = re.compile(r".*?broadcast ([\d\.]+)")

    groups = re.compile("\r?\n(?=\\S)").split(out)
    for group in groups:
        data = dict()
        iface = ""
        updown = False
        for line in group.splitlines():
            miface = piface.match(line)
            mmac = pmac.match(line)
            mip = pip.match(line)
            mip6 = pip6.match(line)
            mupdown = pupdown.search(line)
            if miface:
                iface = miface.group(1)
            if mmac:
                data["hwaddr"] = mmac.group(1)
            if mip:
                if "inet" not in data:
                    data["inet"] = list()
                addr_obj = dict()
                addr_obj["address"] = mip.group(1)
                mmask = mip.group(2)
                if mip.group(2):
                    addr_obj["netmask"] = cidr_to_ipv4_netmask(mip.group(2))
                mbcast = pbcast.match(line)
                if mbcast:
                    addr_obj["broadcast"] = mbcast.group(1)
                data["inet"].append(addr_obj)
            if mupdown:
                updown = True
            if mip6:
                if "inet6" not in data:
                    data["inet6"] = list()
                addr_obj = dict()
                addr_obj["address"] = mip6.group(1)
                mmask6 = mip6.group(3)
                addr_obj["scope"] = mip6.group(2)
                addr_obj["prefixlen"] = mip6.group(3)
                data["inet6"].append(addr_obj)
        data["up"] = updown
        ret[iface] = data
        del data
    return ret


def _junos_interfaces_ifconfig(out):
    """
    Uses ifconfig to return a dictionary of interfaces with various information
    about each (up/down state, ip address, netmask, and hwaddr)
    """
    ret = dict()

    piface = re.compile(r"^([^\s:]+)")
    pmac = re.compile("curr media .*? ([0-9a-f:]+)")

    pip = re.compile(
        r".*?inet\s*(primary)*\s+mtu"
        r" (\d+)\s+local=[^\d]*(.*?)\s+dest=[^\d]*(.*?)\/([\d]*)\s+bcast=((?:[0-9]{1,3}\.){3}[0-9]{1,3})"
    )
    pip6 = re.compile(
        r".*?inet6 mtu [^\d]+\s+local=([0-9a-f:]+)%([a-zA-Z0-9]*)/([\d]*)\s"
    )

    pupdown = re.compile("UP")
    pbcast = re.compile(r".*?broadcast ([\d\.]+)")

    groups = re.compile("\r?\n(?=\\S)").split(out)
    for group in groups:
        data = dict()
        iface = ""
        updown = False
        primary = False
        for line in group.splitlines():
            miface = piface.match(line)
            mmac = pmac.match(line)
            mip = pip.match(line)
            mip6 = pip6.match(line)
            mupdown = pupdown.search(line)
            if miface:
                iface = miface.group(1)
            if mmac:
                data["hwaddr"] = mmac.group(1)
            if mip:
                if "primary" in data:
                    primary = True
                if "inet" not in data:
                    data["inet"] = list()
                if mip.group(2):
                    data["mtu"] = int(mip.group(2))
                addr_obj = dict()
                addr_obj["address"] = mip.group(3)
                mmask = mip.group(5)
                if mip.group(5):
                    addr_obj["netmask"] = cidr_to_ipv4_netmask(mip.group(5))
                mbcast = pbcast.match(line)
                if mbcast:
                    addr_obj["broadcast"] = mbcast.group(1)
                data["inet"].append(addr_obj)
            if mupdown:
                updown = True
            if mip6:
                if "inet6" not in data:
                    data["inet6"] = list()
                addr_obj = dict()
                addr_obj["address"] = mip6.group(1)
                mmask6 = mip6.group(3)
                addr_obj["scope"] = mip6.group(2)
                addr_obj["prefixlen"] = mip6.group(3)
                data["inet6"].append(addr_obj)
        data["up"] = updown
        ret[iface] = data
        del data
    return ret


def junos_interfaces():
    """
    Obtain interface information for Junos; ifconfig
    output diverged from other BSD variants (Netmask is now part of the
    address)
    """
    ifconfig_path = salt.utils.path.which("ifconfig")
    cmd = subprocess.Popen(
        [ifconfig_path, "-a"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).communicate()[0]
    return _junos_interfaces_ifconfig(salt.utils.stringutils.to_str(cmd))


def netbsd_interfaces():
    """
    Obtain interface information for NetBSD >= 8 where the ifconfig
    output diverged from other BSD variants (Netmask is now part of the
    address)
    """
    # NetBSD versions prior to 8.0 can still use linux_interfaces()
    if LooseVersion(os.uname()[2]) < LooseVersion("8.0"):
        return linux_interfaces()

    ifconfig_path = salt.utils.path.which("ifconfig")
    cmd = subprocess.Popen(
        [ifconfig_path, "-a"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).communicate()[0]
    return _netbsd_interfaces_ifconfig(salt.utils.stringutils.to_str(cmd))


def _interfaces_ipconfig(out):
    """
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)

    NOTE: This is not used by any function and may be able to be removed in the
    future.
    """
    ifaces = dict()
    iface = None
    addr = None
    adapter_iface_regex = re.compile(r"adapter (\S.+):$")

    for line in out.splitlines():
        if not line:
            continue
        # TODO what does Windows call Infiniband and 10/40gige adapters
        if line.startswith("Ethernet"):
            iface = ifaces[adapter_iface_regex.search(line).group(1)]
            iface["up"] = True
            addr = {}
            continue
        if iface:
            key, val = line.split(",", 1)
            key = key.strip(" .")
            val = val.strip()
            if addr and key == "Subnet Mask":
                addr["netmask"] = val
            elif key in ("IP Address", "IPv4 Address"):
                if "inet" not in iface:
                    iface["inet"] = list()
                addr = {
                    "address": val.rstrip("(Preferred)"),
                    "netmask": None,
                    "broadcast": None,
                }  # TODO find the broadcast
                iface["inet"].append(addr)
            elif "IPv6 Address" in key:
                if "inet6" not in iface:
                    iface["inet"] = list()
                # XXX What is the prefixlen!?
                addr = {"address": val.rstrip("(Preferred)"), "prefixlen": None}
                iface["inet6"].append(addr)
            elif key == "Physical Address":
                iface["hwaddr"] = val
            elif key == "Media State":
                # XXX seen used for tunnel adaptors
                # might be useful
                iface["up"] = val != "Media disconnected"


def win_interfaces():
    """
    Obtain interface information for Windows systems
    """
    if WIN_NETWORK_LOADED is False:
        # Let's throw the ImportException again
        import salt.utils.win_network as _
    return salt.utils.win_network.get_interface_info()


def interfaces():
    """
    Return a dictionary of information about all the interfaces on the minion
    """
    if salt.utils.platform.is_windows():
        return win_interfaces()
    elif salt.utils.platform.is_junos():
        return junos_interfaces()
    elif salt.utils.platform.is_netbsd():
        return netbsd_interfaces()
    else:
        return linux_interfaces()


def get_net_start(ipaddr, netmask):
    """
    Return the address of the network
    """
    net = ipaddress.ip_network("{}/{}".format(ipaddr, netmask), strict=False)
    return str(net.network_address)


def get_net_size(mask):
    """
    Turns an IPv4 netmask into its corresponding prefix length
    (255.255.255.0 -> 24 as in 192.168.1.10/24).
    """
    binary_str = ""
    for octet in mask.split("."):
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip("0"))


def calc_net(ipaddr, netmask=None):
    """
    Takes IP (CIDR notation supported) and optionally netmask
    and returns the network in CIDR-notation.
    (The IP can be any IP inside the subnet)
    """
    if netmask is not None:
        ipaddr = "{}/{}".format(ipaddr, netmask)

    return str(ipaddress.ip_network(ipaddr, strict=False))


def _ipv4_to_bits(ipaddr):
    """
    Accepts an IPv4 dotted quad and returns a string representing its binary
    counterpart
    """
    return "".join([bin(int(x))[2:].rjust(8, "0") for x in ipaddr.split(".")])


def _get_iface_info(iface):
    """
    If `iface` is available, return interface info and no error, otherwise
    return no info and log and return an error
    """
    iface_info = interfaces()

    if iface in iface_info.keys():
        return iface_info, False
    else:
        error_msg = 'Interface "{}" not in available interfaces: "{}"'.format(
            iface, '", "'.join(iface_info.keys())
        )
        log.error(error_msg)
        return None, error_msg


def _hw_addr_aix(iface):
    """
    Return the hardware address (a.k.a. MAC address) for a given interface on AIX
    MAC address not available in through interfaces
    """
    cmd = subprocess.Popen(
        ["grep", "Hardware Address"],
        stdin=subprocess.Popen(
            ["entstat", "-d", iface],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).communicate()[0]

    if cmd:
        comps = cmd.split(" ")
        if len(comps) == 3:
            mac_addr = comps[2].strip("'").strip()
            return mac_addr

    error_msg = 'Interface "{}" either not available or does not contain a hardware address'.format(
        iface
    )
    log.error(error_msg)
    return error_msg


def hw_addr(iface):
    """
    Return the hardware address (a.k.a. MAC address) for a given interface

    .. versionchanged:: 2016.11.4
        Added support for AIX

    """
    if salt.utils.platform.is_aix():
        return _hw_addr_aix

    iface_info, error = _get_iface_info(iface)

    if error is False:
        return iface_info.get(iface, {}).get("hwaddr", "")
    else:
        return error


def interface(iface):
    """
    Return the details of `iface` or an error if it does not exist
    """
    iface_info, error = _get_iface_info(iface)

    if error is False:
        return iface_info.get(iface, {}).get("inet", "")
    else:
        return error


def interface_ip(iface):
    """
    Return `iface` IPv4 addr or an error if `iface` does not exist
    """
    iface_info, error = _get_iface_info(iface)

    if error is False:
        inet = iface_info.get(iface, {}).get("inet", None)
        return inet[0].get("address", "") if inet else ""
    else:
        return error


def _subnets(proto="inet", interfaces_=None):
    """
    Returns a list of subnets to which the host belongs
    """
    if interfaces_ is None:
        ifaces = interfaces()
    elif isinstance(interfaces_, list):
        ifaces = {}
        for key, value in interfaces().items():
            if key in interfaces_:
                ifaces[key] = value
    else:
        ifaces = {interfaces_: interfaces().get(interfaces_, {})}

    ret = set()

    if proto == "inet":
        subnet = "netmask"
        dflt_cidr = 32
    elif proto == "inet6":
        subnet = "prefixlen"
        dflt_cidr = 128
    else:
        log.error("Invalid proto %s calling subnets()", proto)
        return

    for ip_info in ifaces.values():
        addrs = ip_info.get(proto, [])
        addrs.extend(
            [addr for addr in ip_info.get("secondary", []) if addr.get("type") == proto]
        )

        for intf in addrs:
            if subnet in intf:
                intf = ipaddress.ip_interface(
                    "{}/{}".format(intf["address"], intf[subnet])
                )
            else:
                intf = ipaddress.ip_interface(
                    "{}/{}".format(intf["address"], dflt_cidr)
                )
            if not intf.is_loopback:
                ret.add(intf.network)
    return [str(net) for net in sorted(ret)]


def subnets(interfaces=None):
    """
    Returns a list of IPv4 subnets to which the host belongs
    """
    return _subnets("inet", interfaces_=interfaces)


def subnets6():
    """
    Returns a list of IPv6 subnets to which the host belongs
    """
    return _subnets("inet6")


def in_subnet(cidr, addr=None):
    """
    Returns True if host or (any of) addrs is within specified subnet, otherwise False
    """
    try:
        cidr = ipaddress.ip_network(cidr)
    except ValueError:
        log.error("Invalid CIDR '%s'", cidr)
        return False

    if addr is None:
        addr = ip_addrs()
        addr.extend(ip_addrs6())
    elif not isinstance(addr, (list, tuple)):
        addr = (addr,)

    return any(ipaddress.ip_address(item) in cidr for item in addr)


def _get_ips(ifaces, proto="inet"):
    """
    Accepts a dict of interface data and returns a list of dictionaries
    """
    ret = []
    for ip_info in ifaces.values():
        ret.extend(ip_info.get(proto, []))
        ret.extend(
            [addr for addr in ip_info.get("secondary", []) if addr.get("type") == proto]
        )
    return ret


def _filter_interfaces(interface=None, interface_data=None):
    """
    Gather interface data if not passed in, and optionally filter by the
    specified interface name.
    """
    ifaces = interface_data if isinstance(interface_data, dict) else interfaces()
    if interface is None:
        ret = ifaces
    else:
        interface = salt.utils.args.split_input(interface)
        # pylint: disable=not-an-iterable
        ret = {
            k: v
            for k, v in ifaces.items()
            if any(fnmatch.fnmatch(k, pat) for pat in interface)
        }
        # pylint: enable=not-an-iterable
    return ret


def _ip_addrs(
    interface=None, include_loopback=False, interface_data=None, proto="inet"
):
    """
    Return the full list of IP adresses matching the criteria

    proto = inet|inet6
    """
    addrs = _get_ips(_filter_interfaces(interface, interface_data), proto=proto)

    ret = set()
    for addr in addrs:
        addr = ipaddress.ip_address(addr.get("address"))
        if not addr.is_loopback or include_loopback:
            ret.add(addr)

    return [str(addr) for addr in sorted(ret)]


def ip_addrs(interface=None, include_loopback=False, interface_data=None):
    """
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.
    """
    return _ip_addrs(interface, include_loopback, interface_data, "inet")


def ip_addrs6(interface=None, include_loopback=False, interface_data=None):
    """
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.
    """
    return _ip_addrs(interface, include_loopback, interface_data, "inet6")


def _ip_networks(
    interface=None,
    include_loopback=False,
    verbose=False,
    interface_data=None,
    proto="inet",
):
    """
    Returns a list of networks to which the minion belongs. The results can be
    restricted to a single interface using the ``interface`` argument.
    """
    addrs = _get_ips(_filter_interfaces(interface, interface_data), proto=proto)

    ret = set()
    for addr in addrs:
        _ip = addr.get("address")
        _net = addr.get("netmask" if proto == "inet" else "prefixlen")
        if _ip and _net:
            try:
                ip_net = ipaddress.ip_network("{}/{}".format(_ip, _net), strict=False)
            except Exception:  # pylint: disable=broad-except
                continue
            if not ip_net.is_loopback or include_loopback:
                ret.add(ip_net)

    if not verbose:
        return [str(addr) for addr in sorted(ret)]

    verbose_ret = {
        str(x): {
            "address": str(x.network_address),
            "netmask": str(x.netmask),
            "num_addresses": x.num_addresses,
            "prefixlen": x.prefixlen,
        }
        for x in ret
    }
    return verbose_ret


def ip_networks(
    interface=None, include_loopback=False, verbose=False, interface_data=None
):
    """
    Returns the IPv4 networks to which the minion belongs. Networks will be
    returned as a list of network/prefixlen. To get more information about a
    each network, use verbose=True and a dictionary with more information will
    be returned.
    """
    return _ip_networks(
        interface=interface,
        include_loopback=include_loopback,
        verbose=verbose,
        interface_data=interface_data,
        proto="inet",
    )


def ip_networks6(
    interface=None, include_loopback=False, verbose=False, interface_data=None
):
    """
    Returns the IPv6 networks to which the minion belongs. Networks will be
    returned as a list of network/prefixlen. To get more information about a
    each network, use verbose=True and a dictionary with more information will
    be returned.
    """
    return _ip_networks(
        interface=interface,
        include_loopback=include_loopback,
        verbose=verbose,
        interface_data=interface_data,
        proto="inet6",
    )


def hex2ip(hex_ip, invert=False):
    """
    Convert a hex string to an ip, if a failure occurs the original hex is
    returned. If 'invert=True' assume that ip from /proc/net/<proto>
    """
    if len(hex_ip) == 32:  # ipv6
        ip_addr = []
        for i in range(0, 32, 8):
            ip_part = hex_ip[i : i + 8]
            ip_part = [ip_part[x : x + 2] for x in range(0, 8, 2)]
            if invert:
                ip_addr.append("{0[3]}{0[2]}:{0[1]}{0[0]}".format(ip_part))
            else:
                ip_addr.append("{0[0]}{0[1]}:{0[2]}{0[3]}".format(ip_part))
        try:
            address = ipaddress.IPv6Address(":".join(ip_addr))
            if address.ipv4_mapped:
                return str(address.ipv4_mapped)
            else:
                return address.compressed
        except ipaddress.AddressValueError as ex:
            log.error("hex2ip - ipv6 address error: %s", ex)
            return hex_ip

    try:
        hip = int(hex_ip, 16)
    except ValueError:
        return hex_ip
    if invert:
        return "{3}.{2}.{1}.{0}".format(
            hip >> 24 & 255, hip >> 16 & 255, hip >> 8 & 255, hip & 255
        )
    return "{}.{}.{}.{}".format(
        hip >> 24 & 255, hip >> 16 & 255, hip >> 8 & 255, hip & 255
    )


def mac2eui64(mac, prefix=None):
    """
    Convert a MAC address to a EUI64 identifier
    or, with prefix provided, a full IPv6 address
    """
    # http://tools.ietf.org/html/rfc4291#section-2.5.1
    eui64 = re.sub(r"[.:-]", "", mac).lower()
    eui64 = eui64[0:6] + "fffe" + eui64[6:]
    eui64 = hex(int(eui64[0:2], 16) | 2)[2:].zfill(2) + eui64[2:]

    if prefix is None:
        return ":".join(re.findall(r".{4}", eui64))
    else:
        try:
            net = ipaddress.ip_network(prefix, strict=False)
            euil = int("0x{}".format(eui64), 16)
            return "{}/{}".format(net[euil], net.prefixlen)
        except Exception:  # pylint: disable=broad-except
            return


def active_tcp():
    """
    Return a dict describing all active tcp connections as quickly as possible
    """
    ret = {}
    for statf in ["/proc/net/tcp", "/proc/net/tcp6"]:
        if not os.path.isfile(statf):
            continue
        with salt.utils.files.fopen(statf, "rb") as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                if line.strip().startswith("sl"):
                    continue
                iret = _parse_tcp_line(line)
                slot = next(iter(iret))
                if iret[slot]["state"] == 1:  # 1 is ESTABLISHED
                    del iret[slot]["state"]
                    ret[len(ret)] = iret[slot]
    return ret


def local_port_tcp(port):
    """
    Return a set of remote ip addrs attached to the specified local port
    """
    ret = _remotes_on(port, "local_port")
    return ret


def remote_port_tcp(port):
    """
    Return a set of ip addrs the current host is connected to on given port
    """
    ret = _remotes_on(port, "remote_port")
    return ret


def _remotes_on(port, which_end):
    """
    Return a set of ip addrs active tcp connections
    """
    port = int(port)

    ret = _netlink_tool_remote_on(port, which_end)
    if ret is not None:
        return ret

    ret = set()
    proc_available = False
    for statf in ["/proc/net/tcp", "/proc/net/tcp6"]:
        if not os.path.isfile(statf):
            continue
        proc_available = True
        with salt.utils.files.fopen(statf, "r") as fp_:
            for line in fp_:
                line = salt.utils.stringutils.to_unicode(line)
                if line.strip().startswith("sl"):
                    continue
                iret = _parse_tcp_line(line)
                slot = next(iter(iret))
                if (
                    iret[slot][which_end] == port and iret[slot]["state"] == 1
                ):  # 1 is ESTABLISHED
                    ret.add(iret[slot]["remote_addr"])

    if not proc_available:  # Fallback to use OS specific tools
        if salt.utils.platform.is_sunos():
            return _sunos_remotes_on(port, which_end)
        if salt.utils.platform.is_freebsd():
            return _freebsd_remotes_on(port, which_end)
        if salt.utils.platform.is_netbsd():
            return _netbsd_remotes_on(port, which_end)
        if salt.utils.platform.is_openbsd():
            return _openbsd_remotes_on(port, which_end)
        if salt.utils.platform.is_windows():
            return _windows_remotes_on(port, which_end)
        if salt.utils.platform.is_aix():
            return _aix_remotes_on(port, which_end)

        return _linux_remotes_on(port, which_end)

    return ret


def _parse_tcp_line(line):
    """
    Parse a single line from the contents of /proc/net/tcp or /proc/net/tcp6
    """
    ret = {}
    comps = line.strip().split()
    slot = comps[0].rstrip(":")
    ret[slot] = {}
    l_addr, l_port = comps[1].split(":")
    r_addr, r_port = comps[2].split(":")
    ret[slot]["local_addr"] = hex2ip(l_addr, True)
    ret[slot]["local_port"] = int(l_port, 16)
    ret[slot]["remote_addr"] = hex2ip(r_addr, True)
    ret[slot]["remote_port"] = int(r_port, 16)
    ret[slot]["state"] = int(comps[3], 16)
    return ret


def _netlink_tool_remote_on(port, which_end):
    """
    Returns set of IPv4/IPv6 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'ss' to get connections

    [root@salt-master ~]# ss -ant
    State      Recv-Q Send-Q               Local Address:Port                 Peer Address:Port
    LISTEN     0      511                              *:80                              *:*
    LISTEN     0      128                              *:22                              *:*
    ESTAB      0      0                      127.0.0.1:56726                  127.0.0.1:4505
    ESTAB      0      0             [::ffff:127.0.0.1]:41323         [::ffff:127.0.0.1]:4505
    """
    remotes = set()
    valid = False
    tcp_end = "dst" if which_end == "remote_port" else "src"
    try:
        data = subprocess.check_output(
            ["ss", "-ant", tcp_end, ":{}".format(port)]
        )  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error("Failed ss")
        raise
    except OSError:  # not command "No such file or directory"
        return None

    lines = salt.utils.stringutils.to_str(data).split("\n")
    for line in lines:
        if "Address:Port" in line:  # ss tools may not be valid
            valid = True
            continue
        elif "ESTAB" not in line:
            continue
        chunks = line.split()
        remote_host, remote_port = chunks[4].rsplit(":", 1)

        remotes.add(remote_host.strip("[]"))

    if valid is False:
        remotes = None
    return remotes


def _sunos_remotes_on(port, which_end):
    """
    SunOS specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    [root@salt-master ~]# netstat -f inet -n
    TCP: IPv4
       Local Address        Remote Address    Swind Send-Q Rwind Recv-Q    State
       -------------------- -------------------- ----- ------ ----- ------ -----------
       10.0.0.101.4505      10.0.0.1.45329       1064800      0 1055864      0 ESTABLISHED
       10.0.0.101.4505      10.0.0.100.50798     1064800      0 1055864      0 ESTABLISHED
    """
    remotes = set()
    try:
        data = subprocess.check_output(
            ["netstat", "-f", "inet", "-n"]
        )  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error("Failed netstat")
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")
    for line in lines:
        if "ESTABLISHED" not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[0].rsplit(".", 1)
        remote_host, remote_port = chunks[1].rsplit(".", 1)

        if which_end == "remote_port" and int(remote_port) != port:
            continue
        if which_end == "local_port" and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _freebsd_remotes_on(port, which_end):
    """
    Returns set of ipv4 host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'sockstat' (FreeBSD)
    to get connections

    $ sudo sockstat -4
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1456    29  tcp4   *:4505           *:*
    root    python2.7   1445    17  tcp4   *:4506           *:*
    root    python2.7   1294    14  tcp4   127.0.0.1:11813  127.0.0.1:4505
    root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506

    $ sudo sockstat -4 -c -p 4506
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506
    """

    port = int(port)
    remotes = set()

    try:
        cmd = salt.utils.args.shlex_split("sockstat -4 -c -p {}".format(port))
        data = subprocess.check_output(cmd)  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError as ex:
        log.error('Failed "sockstat" with returncode = %s', ex.returncode)
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")

    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['root', 'python2.7', '1456', '37', 'tcp4',
        #  '127.0.0.1:4505-', '127.0.0.1:55703']
        # print chunks
        if "COMMAND" in chunks[1]:
            continue  # ignore header
        if len(chunks) < 2:
            continue
        # sockstat -4 -c -p 4506 does this with high PIDs:
        # USER     COMMAND    PID   FD PROTO  LOCAL ADDRESS         FOREIGN ADDRESS
        # salt-master python2.781106 35 tcp4  192.168.12.34:4506    192.168.12.45:60143
        local = chunks[-2]
        remote = chunks[-1]
        lhost, lport = local.split(":")
        rhost, rport = remote.split(":")
        if which_end == "local" and int(lport) != port:  # ignore if local port not port
            continue
        if (
            which_end == "remote" and int(rport) != port
        ):  # ignore if remote port not port
            continue

        remotes.add(rhost)

    return remotes


def _netbsd_remotes_on(port, which_end):
    """
    Returns set of ipv4 host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'sockstat' (NetBSD)
    to get connections

    $ sudo sockstat -4 -n
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1456    29  tcp    *.4505           *.*
    root    python2.7   1445    17  tcp    *.4506           *.*
    root    python2.7   1294    14  tcp    127.0.0.1.11813  127.0.0.1.4505
    root    python2.7   1294    41  tcp    127.0.0.1.61115  127.0.0.1.4506

    $ sudo sockstat -4 -c -n -p 4506
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1294    41  tcp    127.0.0.1.61115  127.0.0.1.4506
    """

    port = int(port)
    remotes = set()

    try:
        cmd = salt.utils.args.shlex_split("sockstat -4 -c -n -p {}".format(port))
        data = subprocess.check_output(cmd)  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError as ex:
        log.error('Failed "sockstat" with returncode = %s', ex.returncode)
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")

    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['root', 'python2.7', '1456', '37', 'tcp',
        #  '127.0.0.1.4505-', '127.0.0.1.55703']
        # print chunks
        if "COMMAND" in chunks[1]:
            continue  # ignore header
        if len(chunks) < 2:
            continue
        local = chunks[5].split(".")
        lport = local.pop()
        lhost = ".".join(local)
        remote = chunks[6].split(".")
        rport = remote.pop()
        rhost = ".".join(remote)
        if which_end == "local" and int(lport) != port:  # ignore if local port not port
            continue
        if (
            which_end == "remote" and int(rport) != port
        ):  # ignore if remote port not port
            continue

        remotes.add(rhost)

    return remotes


def _openbsd_remotes_on(port, which_end):
    """
    OpenBSD specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    $ netstat -nf inet
    Active Internet connections
    Proto   Recv-Q Send-Q  Local Address          Foreign Address        (state)
    tcp          0      0  10.0.0.101.4505        10.0.0.1.45329         ESTABLISHED
    tcp          0      0  10.0.0.101.4505        10.0.0.100.50798       ESTABLISHED
    """
    remotes = set()
    try:
        data = subprocess.check_output(
            ["netstat", "-nf", "inet"]
        )  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error("Failed netstat")
        raise

    lines = data.split("\n")
    for line in lines:
        if "ESTABLISHED" not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[3].rsplit(".", 1)
        remote_host, remote_port = chunks[4].rsplit(".", 1)

        if which_end == "remote_port" and int(remote_port) != port:
            continue
        if which_end == "local_port" and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _windows_remotes_on(port, which_end):
    r"""
    Windows specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    C:\>netstat -n

    Active Connections

       Proto  Local Address          Foreign Address        State
       TCP    10.2.33.17:3007        130.164.12.233:10123   ESTABLISHED
       TCP    10.2.33.17:3389        130.164.30.5:10378     ESTABLISHED
    """
    remotes = set()
    try:
        data = subprocess.check_output(
            ["netstat", "-n"]
        )  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error("Failed netstat")
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")
    for line in lines:
        if "ESTABLISHED" not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[1].rsplit(":", 1)
        remote_host, remote_port = chunks[2].rsplit(":", 1)
        if which_end == "remote_port" and int(remote_port) != port:
            continue
        if which_end == "local_port" and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _linux_remotes_on(port, which_end):
    """
    Linux specific helper function.
    Returns set of ip host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'lsof'
    to get connections

    $ sudo lsof -iTCP:4505 -n
    COMMAND   PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
    Python   9971 root   35u  IPv4 0x18a8464a29ca329d      0t0  TCP *:4505 (LISTEN)
    Python   9971 root   37u  IPv4 0x18a8464a29b2b29d      0t0  TCP 127.0.0.1:4505->127.0.0.1:55703 (ESTABLISHED)
    Python  10152 root   22u  IPv4 0x18a8464a29c8cab5      0t0  TCP 127.0.0.1:55703->127.0.0.1:4505 (ESTABLISHED)
    Python  10153 root   22u  IPv4 0x18a8464a29c8cab5      0t0  TCP [fe80::249a]:4505->[fe80::150]:59367 (ESTABLISHED)

    """
    remotes = set()

    try:
        data = subprocess.check_output(
            [
                "lsof",
                "-iTCP:{:d}".format(port),
                "-n",
                "-P",
            ]  # pylint: disable=minimum-python-version
        )
    except subprocess.CalledProcessError as ex:
        if ex.returncode == 1:
            # Lsof return 1 if any error was detected, including the failure
            # to locate Internet addresses, and it is not an error in this case.
            log.warning('"lsof" returncode = 1, likely no active TCP sessions.')
            return remotes
        log.error('Failed "lsof" with returncode = %s', ex.returncode)
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")
    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['Python', '9971', 'root', '37u', 'IPv4', '0x18a8464a29b2b29d', '0t0',
        # 'TCP', '127.0.0.1:4505->127.0.0.1:55703', '(ESTABLISHED)']
        # print chunks
        if "COMMAND" in chunks[0]:
            continue  # ignore header
        if "ESTABLISHED" not in chunks[-1]:
            continue  # ignore if not ESTABLISHED
        # '127.0.0.1:4505->127.0.0.1:55703'
        local, remote = chunks[8].split("->")
        _, lport = local.rsplit(":", 1)
        rhost, rport = remote.rsplit(":", 1)
        if which_end == "remote_port" and int(rport) != port:
            continue
        if which_end == "local_port" and int(lport) != port:
            continue
        remotes.add(rhost.strip("[]"))

    return remotes


def _aix_remotes_on(port, which_end):
    """
    AIX specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    root@la68pp002_pub:/opt/salt/lib/python2.7/site-packages/salt/modules# netstat -f inet -n
    Active Internet connections
    Proto Recv-Q Send-Q  Local Address          Foreign Address        (state)
    tcp4       0      0  172.29.149.95.50093    209.41.78.13.4505      ESTABLISHED
    tcp4       0      0  127.0.0.1.9514         *.*                    LISTEN
    tcp4       0      0  127.0.0.1.9515         *.*                    LISTEN
    tcp4       0      0  127.0.0.1.199          127.0.0.1.32779        ESTABLISHED
    tcp4       0      0  127.0.0.1.32779        127.0.0.1.199          ESTABLISHED
    tcp4       0     40  172.29.149.95.22       172.29.96.83.41022     ESTABLISHED
    tcp4       0      0  172.29.149.95.22       172.29.96.83.41032     ESTABLISHED
    tcp4       0      0  127.0.0.1.32771        127.0.0.1.32775        ESTABLISHED
    tcp        0      0  127.0.0.1.32775        127.0.0.1.32771        ESTABLISHED
    tcp4       0      0  127.0.0.1.32771        127.0.0.1.32776        ESTABLISHED
    tcp        0      0  127.0.0.1.32776        127.0.0.1.32771        ESTABLISHED
    tcp4       0      0  127.0.0.1.32771        127.0.0.1.32777        ESTABLISHED
    tcp        0      0  127.0.0.1.32777        127.0.0.1.32771        ESTABLISHED
    tcp4       0      0  127.0.0.1.32771        127.0.0.1.32778        ESTABLISHED
    tcp        0      0  127.0.0.1.32778        127.0.0.1.32771        ESTABLISHED
    """
    remotes = set()
    try:
        data = subprocess.check_output(
            ["netstat", "-f", "inet", "-n"]
        )  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error("Failed netstat")
        raise

    lines = salt.utils.stringutils.to_str(data).split("\n")
    for line in lines:
        if "ESTABLISHED" not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[3].rsplit(".", 1)
        remote_host, remote_port = chunks[4].rsplit(".", 1)

        if which_end == "remote_port" and int(remote_port) != port:
            continue
        if which_end == "local_port" and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


@jinja_filter("gen_mac")
def gen_mac(prefix="AC:DE:48"):
    """
    Generates a MAC address with the defined OUI prefix.

    Common prefixes:

     - ``00:16:3E`` -- Xen
     - ``00:18:51`` -- OpenVZ
     - ``00:50:56`` -- VMware (manually generated)
     - ``52:54:00`` -- QEMU/KVM
     - ``AC:DE:48`` -- PRIVATE

    References:

     - http://standards.ieee.org/develop/regauth/oui/oui.txt
     - https://www.wireshark.org/tools/oui-lookup.html
     - https://en.wikipedia.org/wiki/MAC_address
    """
    return "{}:{:02X}:{:02X}:{:02X}".format(
        prefix,
        random.randint(0, 0xFF),
        random.randint(0, 0xFF),
        random.randint(0, 0xFF),
    )


@jinja_filter("mac_str_to_bytes")
def mac_str_to_bytes(mac_str):
    """
    Convert a MAC address string into bytes. Works with or without separators:

    b1 = mac_str_to_bytes('08:00:27:13:69:77')
    b2 = mac_str_to_bytes('080027136977')
    assert b1 == b2
    assert isinstance(b1, bytes)
    """
    if len(mac_str) == 12:
        pass
    elif len(mac_str) == 17:
        sep = mac_str[2]
        mac_str = mac_str.replace(sep, "")
    else:
        raise ValueError("Invalid MAC address")
    chars = (int(mac_str[s : s + 2], 16) for s in range(0, 12, 2))
    return bytes(chars)


def refresh_dns():
    """
    issue #21397: force glibc to re-read resolv.conf
    """
    try:
        RES_INIT()
    except NameError:
        # Exception raised loading the library, thus RES_INIT is not defined
        pass


@jinja_filter("dns_check")
def dns_check(addr, port, safe=False, ipv6=None):
    """
    Return an ip address resolved by dns in a format usable in URLs (ipv6 in brackets).
    Obeys system preference for IPv4/6 address resolution - this can be overridden by
    the ipv6 flag. Tries to connect to the address before considering it useful. If no
    address can be reached, the first one resolved is used as a fallback.
    Does not exit on failure, raises an exception.
    """
    ip_addrs = []
    family = (
        socket.AF_INET6
        if ipv6
        else socket.AF_INET
        if ipv6 is False
        else socket.AF_UNSPEC
    )
    try:
        refresh_dns()
        addrinfo = socket.getaddrinfo(addr, port, family, socket.SOCK_STREAM)
        ip_addrs = _test_addrs(addrinfo, port)
    except TypeError:
        raise SaltSystemExit(
            code=42,
            msg=(
                "Attempt to resolve address '{}' failed. Invalid or unresolveable"
                " address".format(addr)
            ),
        )
    except OSError:
        pass

    if not ip_addrs:
        err = "DNS lookup or connection check of '{}' failed.".format(addr)
        if safe:
            if salt.log.is_console_configured():
                # If logging is not configured it also means that either
                # the master or minion instance calling this hasn't even
                # started running
                log.error(err)
            raise SaltClientError()
        raise SaltSystemExit(code=42, msg=err)

    return salt.utils.zeromq.ip_bracket(ip_addrs[0])


def _test_addrs(addrinfo, port):
    """
    Attempt to connect to all addresses, return one if it succeeds.
    Otherwise, return all addrs.
    """
    ip_addrs = []
    # test for connectivity, short circuit on success
    for a in addrinfo:
        ip_family = a[0]
        ip_addr = a[4][0]
        if ip_addr in ip_addrs:
            continue
        ip_addrs.append(ip_addr)

        try:
            s = socket.socket(ip_family, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip_addr, port))
            s.close()

            ip_addrs = [ip_addr]
            break
        except OSError:
            pass
    return ip_addrs


def parse_host_port(host_port):
    """
    Takes a string argument specifying host or host:port.

    Returns a (hostname, port) or (ip_address, port) tuple. If no port is given,
    the second (port) element of the returned tuple will be None.

    host:port argument, for example, is accepted in the forms of:
      - hostname
      - hostname:1234
      - hostname.domain.tld
      - hostname.domain.tld:5678
      - [1234::5]:5678
      - 1234::5
      - 10.11.12.13:4567
      - 10.11.12.13
    """
    host, port = None, None  # default

    _s_ = host_port[:]
    if _s_[0] == "[":
        if "]" in host_port:
            host, _s_ = _s_.lstrip("[").rsplit("]", 1)
            host = ipaddress.IPv6Address(host).compressed
            if _s_[0] == ":":
                port = int(_s_.lstrip(":"))
            else:
                if len(_s_) > 1:
                    raise ValueError(
                        'found ambiguous "{}" port in "{}"'.format(_s_, host_port)
                    )
    else:
        if _s_.count(":") == 1:
            host, _hostport_separator_, port = _s_.partition(":")
            try:
                port = int(port)
            except ValueError as _e_:
                errmsg = 'host_port "{}" port value "{}" is not an integer.'.format(
                    host_port, port
                )
                log.error(errmsg)
                raise ValueError(errmsg)
        else:
            host = _s_
    try:
        if not isinstance(host, ipaddress._BaseAddress):
            host_ip = ipaddress.ip_address(host).compressed
            host = host_ip
    except ValueError:
        log.debug('"%s" Not an IP address? Assuming it is a hostname.', host)
        if host != sanitize_host(host):
            log.error('bad hostname: "%s"', host)
            raise ValueError('bad hostname: "{}"'.format(host))

    return host, port


@jinja_filter("filter_by_networks")
def filter_by_networks(values, networks):
    """
    Returns the list of IPs filtered by the network list.
    If the network list is an empty sequence, no IPs are returned.
    If the network list is None, all IPs are returned.

    {% set networks = ['192.168.0.0/24', 'fe80::/64'] %}
    {{ grains['ip_interfaces'] | filter_by_networks(networks) }}
    {{ grains['ipv6'] | filter_by_networks(networks) }}
    {{ grains['ipv4'] | filter_by_networks(networks) }}
    """

    _filter = lambda ips, networks: [
        ip for ip in ips for net in networks if ipaddress.ip_address(ip) in net
    ]

    if networks is not None:
        networks = [ipaddress.ip_network(network) for network in networks]
        if isinstance(values, Mapping):
            return {
                interface: _filter(values[interface], networks) for interface in values
            }
        elif isinstance(values, Sequence):
            return _filter(values, networks)
        else:
            raise ValueError("Do not know how to filter a {}".format(type(values)))
    else:
        return values
