"""
Module for gathering and managing network information
"""

import concurrent.futures
import datetime
import hashlib
import logging
import os
import random
import re
import socket
import time

import salt.utils.decorators.path
import salt.utils.functools
import salt.utils.network
import salt.utils.platform
import salt.utils.validate.net
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    # Disable on Windows, a specific file module exists:
    if salt.utils.platform.is_windows():
        return (
            False,
            "The network execution module cannot be loaded on Windows: use win_network"
            " instead.",
        )
    return True


def wol(mac, bcast="255.255.255.255", destport=9):
    """
    Send Wake On Lan packet to a host

    CLI Example:

    .. code-block:: bash

        salt '*' network.wol 08-00-27-13-69-77
        salt '*' network.wol 080027136977 255.255.255.255 7
        salt '*' network.wol 08:00:27:13:69:77 255.255.255.255 7
    """
    dest = __utils__["network.mac_str_to_bytes"](mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b"\xff" * 6 + dest * 16, (bcast, int(destport)))
    return True


def ping(host, timeout=False, return_boolean=False):
    """
    Performs an ICMP ping to a host

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.ping archlinux.org

    .. versionadded:: 2015.5.0

    Return a True or False instead of ping output.

    .. code-block:: bash

        salt '*' network.ping archlinux.org return_boolean=True

    Set the time to wait for a response in seconds.

    .. code-block:: bash

        salt '*' network.ping archlinux.org timeout=3
    """
    if timeout:
        if __grains__["kernel"] == "SunOS":
            cmd = "ping -c 4 {} {}".format(
                __utils__["network.sanitize_host"](host), timeout
            )
        else:
            cmd = "ping -W {} -c 4 {}".format(
                timeout, __utils__["network.sanitize_host"](host)
            )
    else:
        cmd = "ping -c 4 {}".format(__utils__["network.sanitize_host"](host))
    if return_boolean:
        ret = __salt__["cmd.run_all"](cmd)
        if ret["retcode"] != 0:
            return False
        else:
            return True
    else:
        return __salt__["cmd.run"](cmd)


# FIXME: Does not work with: netstat 1.42 (2001-04-15) from net-tools
# 1.6.0 (Ubuntu 10.10)
def _netstat_linux():
    """
    Return netstat information for Linux distros
    """
    ret = []
    cmd = "netstat -tulpnea"
    out = __salt__["cmd.run"](cmd)
    for line in out.splitlines():
        comps = line.split()
        if line.startswith("tcp"):
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[1],
                    "send-q": comps[2],
                    "local-address": comps[3],
                    "remote-address": comps[4],
                    "state": comps[5],
                    "user": comps[6],
                    "inode": comps[7],
                    "program": comps[8],
                }
            )
        if line.startswith("udp"):
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[1],
                    "send-q": comps[2],
                    "local-address": comps[3],
                    "remote-address": comps[4],
                    "user": comps[5],
                    "inode": comps[6],
                    "program": comps[7],
                }
            )
    return ret


def _ss_linux():
    """
    Return ss information for Linux distros
    (netstat is deprecated and may not be available)
    """
    ret = []
    cmd = "ss -tulpnea"
    out = __salt__["cmd.run"](cmd)
    for line in out.splitlines():
        comps = line.split()
        ss_user = 0
        ss_inode = 0
        ss_program = ""
        length = len(comps)
        if line.startswith("tcp") or line.startswith("udp"):
            i = 6
            while i < (length - 1):
                fields = comps[i].split(":")
                if fields[0] == "users":
                    users = fields[1].split(",")
                    ss_program = users[0].split('"')[1]

                if fields[0] == "uid":
                    ss_user = fields[1]

                if fields[0] == "ino":
                    ss_inode = fields[1]

                i += 1

        if line.startswith("tcp"):
            ss_state = comps[1]
            if ss_state == "ESTAB":
                ss_state = "ESTABLISHED"
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[2],
                    "send-q": comps[3],
                    "local-address": comps[4],
                    "remote-address": comps[5],
                    "state": ss_state,
                    "user": ss_user,
                    "inode": ss_inode,
                    "program": ss_program,
                }
            )
        if line.startswith("udp"):
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[2],
                    "send-q": comps[3],
                    "local-address": comps[4],
                    "remote-address": comps[5],
                    "user": ss_user,
                    "inode": ss_inode,
                    "program": ss_program,
                }
            )
    return ret


def _netinfo_openbsd():
    """
    Get process information for network connections using fstat
    """
    ret = {}
    _fstat_re = re.compile(
        r"internet(6)? (?:stream tcp 0x\S+ (\S+)|dgram udp (\S+))"
        r"(?: [<>=-]+ (\S+))?$"
    )
    out = __salt__["cmd.run"]("fstat")
    for line in out.splitlines():
        try:
            user, cmd, pid, _, details = line.split(None, 4)
            ipv6, tcp, udp, remote_addr = _fstat_re.match(details).groups()
        except (ValueError, AttributeError):
            # Line either doesn't have the right number of columns, or the
            # regex which looks for address information did not match. Either
            # way, ignore this line and continue on to the next one.
            continue
        if tcp:
            local_addr = tcp
            proto = "tcp{}".format("" if ipv6 is None else ipv6)
        else:
            local_addr = udp
            proto = "udp{}".format("" if ipv6 is None else ipv6)
        if ipv6:
            # IPv6 addresses have the address part enclosed in brackets (if the
            # address part is not a wildcard) to distinguish the address from
            # the port number. Remove them.
            local_addr = "".join(x for x in local_addr if x not in "[]")

        # Normalize to match netstat output
        local_addr = ".".join(local_addr.rsplit(":", 1))
        if remote_addr is None:
            remote_addr = "*.*"
        else:
            remote_addr = ".".join(remote_addr.rsplit(":", 1))

        ret.setdefault(local_addr, {}).setdefault(remote_addr, {}).setdefault(
            proto, {}
        ).setdefault(pid, {})["user"] = user
        ret[local_addr][remote_addr][proto][pid]["cmd"] = cmd
    return ret


def _netinfo_freebsd_netbsd():
    """
    Get process information for network connections using sockstat
    """
    ret = {}
    # NetBSD requires '-n' to disable port-to-service resolution
    out = __salt__["cmd.run"](
        "sockstat -46 {} | tail -n+2".format(
            "-n" if __grains__["kernel"] == "NetBSD" else ""
        ),
        python_shell=True,
    )
    for line in out.splitlines():
        user, cmd, pid, _, proto, local_addr, remote_addr = line.split()
        local_addr = ".".join(local_addr.rsplit(":", 1))
        remote_addr = ".".join(remote_addr.rsplit(":", 1))
        ret.setdefault(local_addr, {}).setdefault(remote_addr, {}).setdefault(
            proto, {}
        ).setdefault(pid, {})["user"] = user
        ret[local_addr][remote_addr][proto][pid]["cmd"] = cmd
    return ret


def _ppid():
    """
    Return a dict of pid to ppid mappings
    """
    ret = {}
    if __grains__["kernel"] == "SunOS":
        cmd = "ps -a -o pid,ppid | tail +2"
    else:
        cmd = "ps -ax -o pid,ppid | tail -n+2"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        pid, ppid = line.split()
        ret[pid] = ppid
    return ret


def _netstat_bsd():
    """
    Return netstat information for BSD flavors
    """
    ret = []
    if __grains__["kernel"] == "NetBSD":
        for addr_family in ("inet", "inet6"):
            cmd = f"netstat -f {addr_family} -an | tail -n+3"
            out = __salt__["cmd.run"](cmd, python_shell=True)
            for line in out.splitlines():
                comps = line.split()
                entry = {
                    "proto": comps[0],
                    "recv-q": comps[1],
                    "send-q": comps[2],
                    "local-address": comps[3],
                    "remote-address": comps[4],
                }
                if entry["proto"].startswith("tcp"):
                    entry["state"] = comps[5]
                ret.append(entry)
    else:
        # Lookup TCP connections
        cmd = "netstat -p tcp -an | tail -n+3"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[1],
                    "send-q": comps[2],
                    "local-address": comps[3],
                    "remote-address": comps[4],
                    "state": comps[5],
                }
            )
        # Lookup UDP connections
        cmd = "netstat -p udp -an | tail -n+3"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append(
                {
                    "proto": comps[0],
                    "recv-q": comps[1],
                    "send-q": comps[2],
                    "local-address": comps[3],
                    "remote-address": comps[4],
                }
            )

    # Add in user and program info
    ppid = _ppid()
    if __grains__["kernel"] == "OpenBSD":
        netinfo = _netinfo_openbsd()
    elif __grains__["kernel"] in ("FreeBSD", "NetBSD"):
        netinfo = _netinfo_freebsd_netbsd()
    for idx, _ in enumerate(ret):
        local = ret[idx]["local-address"]
        remote = ret[idx]["remote-address"]
        proto = ret[idx]["proto"]
        try:
            # Make a pointer to the info for this connection for easier
            # reference below
            ptr = netinfo[local][remote][proto]
        except KeyError:
            continue
        # Get the pid-to-ppid mappings for this connection
        conn_ppid = {x: y for x, y in ppid.items() if x in ptr}
        try:
            # Master pid for this connection will be the pid whose ppid isn't
            # in the subset dict we created above
            master_pid = next(iter(x for x, y in conn_ppid.items() if y not in ptr))
        except StopIteration:
            continue
        ret[idx]["user"] = ptr[master_pid]["user"]
        ret[idx]["program"] = "/".join((master_pid, ptr[master_pid]["cmd"]))
    return ret


def _netstat_sunos():
    """
    Return netstat information for SunOS flavors
    """
    log.warning("User and program not (yet) supported on SunOS")

    ret = []
    for addr_family in ("inet", "inet6"):
        # Lookup TCP connections
        cmd = f"netstat -f {addr_family} -P tcp -an | tail +5"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append(
                {
                    "proto": "tcp6" if addr_family == "inet6" else "tcp",
                    "recv-q": comps[5],
                    "send-q": comps[4],
                    "local-address": comps[0],
                    "remote-address": comps[1],
                    "state": comps[6],
                }
            )
        # Lookup UDP connections
        cmd = f"netstat -f {addr_family} -P udp -an | tail +5"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append(
                {
                    "proto": "udp6" if addr_family == "inet6" else "udp",
                    "local-address": comps[0],
                    "remote-address": comps[1] if len(comps) > 2 else "",
                }
            )

    return ret


def _netstat_aix():
    """
    Return netstat information for SunOS flavors
    """
    ret = []
    ## AIX 6.1 - 7.2, appears to ignore addr_family field contents
    ## for addr_family in ('inet', 'inet6'):
    for addr_family in ("inet",):
        # Lookup connections
        cmd = f"netstat -n -a -f {addr_family} | tail -n +3"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            if len(comps) < 5:
                continue

            proto_seen = None
            tcp_flag = True
            if "tcp" == comps[0] or "tcp4" == comps[0]:
                proto_seen = "tcp"
            elif "tcp6" == comps[0]:
                proto_seen = "tcp6"
            elif "udp" == comps[0] or "udp4" == comps[0]:
                proto_seen = "udp"
                tcp_flag = False
            elif "udp6" == comps[0]:
                proto_seen = "udp6"
                tcp_flag = False

            if tcp_flag:
                if len(comps) >= 6:
                    ret.append(
                        {
                            "proto": proto_seen,
                            "recv-q": comps[1],
                            "send-q": comps[2],
                            "local-address": comps[3],
                            "remote-address": comps[4],
                            "state": comps[5],
                        }
                    )
            else:
                if len(comps) >= 5:
                    ret.append(
                        {
                            "proto": proto_seen,
                            "local-address": comps[3],
                            "remote-address": comps[4],
                        }
                    )
    return ret


def _netstat_route_linux():
    """
    Return netstat routing information for Linux distros
    """
    ret = []
    cmd = "netstat -A inet -rn | tail -n+3"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": comps[2],
                "flags": comps[3],
                "interface": comps[7],
            }
        )
    cmd = "netstat -A inet6 -rn | tail -n+3"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        if len(comps) == 6:
            ret.append(
                {
                    "addr_family": "inet6",
                    "destination": comps[0],
                    "gateway": comps[1],
                    "netmask": "",
                    "flags": comps[2],
                    "interface": comps[5],
                }
            )
        elif len(comps) == 7:
            ret.append(
                {
                    "addr_family": "inet6",
                    "destination": comps[0],
                    "gateway": comps[1],
                    "netmask": "",
                    "flags": comps[2],
                    "interface": comps[6],
                }
            )
        else:
            continue
    return ret


def _ip_route_linux():
    """
    Return ip routing information for Linux distros
    (netstat is deprecated and may not be available)
    """
    # table main closest to old netstat inet output
    ret = []
    cmd = "ip -4 route show table main"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()

        # need to fake similar output to that provided by netstat
        # to maintain output format
        if comps[0] == "unreachable":
            continue

        if comps[0] == "default":
            ip_interface = ""
            if comps[3] == "dev":
                ip_interface = comps[4]

            ret.append(
                {
                    "addr_family": "inet",
                    "destination": "0.0.0.0",
                    "gateway": comps[2],
                    "netmask": "0.0.0.0",
                    "flags": "UG",
                    "interface": ip_interface,
                }
            )
        else:
            address_mask = convert_cidr(comps[0])
            ip_interface = ""
            if comps[1] == "dev":
                ip_interface = comps[2]

            ret.append(
                {
                    "addr_family": "inet",
                    "destination": address_mask["network"],
                    "gateway": "0.0.0.0",
                    "netmask": address_mask["netmask"],
                    "flags": "U",
                    "interface": ip_interface,
                }
            )

    # table all closest to old netstat inet6 output
    cmd = "ip -6 route show table all"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()

        # need to fake similar output to that provided by netstat
        # to maintain output format
        if comps[0] in (
            "unicast",
            "broadcast",
            "throw",
            "unreachable",
            "prohibit",
            "blackhole",
            "nat",
            "anycast",
            "multicast",
        ):
            continue

        if comps[0] == "default":
            ip_interface = ""
            if comps[3] == "dev":
                ip_interface = comps[4]

            ret.append(
                {
                    "addr_family": "inet6",
                    "destination": "::/0",
                    "gateway": comps[2],
                    "netmask": "",
                    "flags": "UG",
                    "interface": ip_interface,
                }
            )

        elif comps[0] == "local":
            ip_interface = ""
            if comps[2] == "dev":
                ip_interface = comps[3]

            local_address = comps[1] + "/128"
            ret.append(
                {
                    "addr_family": "inet6",
                    "destination": local_address,
                    "gateway": "::",
                    "netmask": "",
                    "flags": "U",
                    "interface": ip_interface,
                }
            )
        else:
            address_mask = convert_cidr(comps[0])
            ip_interface = ""
            if comps[1] == "dev":
                ip_interface = comps[2]

            ret.append(
                {
                    "addr_family": "inet6",
                    "destination": comps[0],
                    "gateway": "::",
                    "netmask": "",
                    "flags": "U",
                    "interface": ip_interface,
                }
            )
    return ret


def _netstat_route_freebsd():
    """
    Return netstat routing information for FreeBSD and macOS
    """
    ret = []
    cmd = "netstat -f inet -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        if (
            __grains__["os"] == "FreeBSD"
            and int(__grains__.get("osmajorrelease", 0)) < 10
        ):
            ret.append(
                {
                    "addr_family": "inet",
                    "destination": comps[0],
                    "gateway": comps[1],
                    "netmask": comps[2],
                    "flags": comps[3],
                    "interface": comps[5],
                }
            )
        else:
            ret.append(
                {
                    "addr_family": "inet",
                    "destination": comps[0],
                    "gateway": comps[1],
                    "netmask": "",
                    "flags": comps[2],
                    "interface": comps[3],
                }
            )
    cmd = "netstat -f inet6 -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet6",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[3],
            }
        )
    return ret


def _netstat_route_netbsd():
    """
    Return netstat routing information for NetBSD
    """
    ret = []
    cmd = "netstat -f inet -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[3],
                "interface": comps[6],
            }
        )
    cmd = "netstat -f inet6 -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet6",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[3],
                "interface": comps[6],
            }
        )
    return ret


def _netstat_route_openbsd():
    """
    Return netstat routing information for OpenBSD
    """
    ret = []
    cmd = "netstat -f inet -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[7],
            }
        )
    cmd = "netstat -f inet6 -rn | tail -n+5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet6",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[7],
            }
        )
    return ret


def _netstat_route_sunos():
    """
    Return netstat routing information for SunOS
    """
    ret = []
    cmd = "netstat -f inet -rn | tail +5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[5] if len(comps) >= 6 else "",
            }
        )
    cmd = "netstat -f inet6 -rn | tail +5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet6",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[5] if len(comps) >= 6 else "",
            }
        )
    return ret


def _netstat_route_aix():
    """
    Return netstat routing information for AIX
    """
    ret = []
    cmd = "netstat -f inet -rn | tail -n +5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[5] if len(comps) >= 6 else "",
            }
        )
    cmd = "netstat -f inet6 -rn | tail -n +5"
    out = __salt__["cmd.run"](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append(
            {
                "addr_family": "inet6",
                "destination": comps[0],
                "gateway": comps[1],
                "netmask": "",
                "flags": comps[2],
                "interface": comps[5] if len(comps) >= 6 else "",
            }
        )
    return ret


def netstat():
    """
    Return information on open ports and states

    .. note::
        On BSD minions, the output contains PID info (where available) for each
        netstat entry, fetched from sockstat/fstat output.

    .. versionchanged:: 2014.1.4
        Added support for OpenBSD, FreeBSD, and NetBSD

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' network.netstat
    """
    if __grains__["kernel"] == "Linux":
        if not __utils__["path.which"]("netstat"):
            return _ss_linux()
        else:
            return _netstat_linux()
    elif __grains__["kernel"] in ("OpenBSD", "FreeBSD", "NetBSD"):
        return _netstat_bsd()
    elif __grains__["kernel"] == "SunOS":
        return _netstat_sunos()
    elif __grains__["kernel"] == "AIX":
        return _netstat_aix()
    raise CommandExecutionError("Not yet supported on this platform")


def active_tcp():
    """
    Return a dict containing information on all of the running TCP connections (currently linux and solaris only)

    .. versionchanged:: 2015.8.4

        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.active_tcp
    """
    if __grains__["kernel"] == "Linux":
        return __utils__["network.active_tcp"]()
    elif __grains__["kernel"] == "SunOS":
        # lets use netstat to mimic linux as close as possible
        ret = {}
        for connection in _netstat_sunos():
            if not connection["proto"].startswith("tcp"):
                continue
            if connection["state"] != "ESTABLISHED":
                continue
            ret[len(ret) + 1] = {
                "local_addr": ".".join(connection["local-address"].split(".")[:-1]),
                "local_port": ".".join(connection["local-address"].split(".")[-1:]),
                "remote_addr": ".".join(connection["remote-address"].split(".")[:-1]),
                "remote_port": ".".join(connection["remote-address"].split(".")[-1:]),
            }
        return ret
    elif __grains__["kernel"] == "AIX":
        # lets use netstat to mimic linux as close as possible
        ret = {}
        for connection in _netstat_aix():
            if not connection["proto"].startswith("tcp"):
                continue
            if connection["state"] != "ESTABLISHED":
                continue
            ret[len(ret) + 1] = {
                "local_addr": ".".join(connection["local-address"].split(".")[:-1]),
                "local_port": ".".join(connection["local-address"].split(".")[-1:]),
                "remote_addr": ".".join(connection["remote-address"].split(".")[:-1]),
                "remote_port": ".".join(connection["remote-address"].split(".")[-1:]),
            }
        return ret
    else:
        return {}


@salt.utils.decorators.path.which("traceroute")
def traceroute(host):
    """
    Performs a traceroute to a 3rd party host

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' network.traceroute archlinux.org
    """
    ret = []
    cmd = "traceroute {}".format(__utils__["network.sanitize_host"](host))
    out = __salt__["cmd.run"](cmd)

    # Parse version of traceroute
    if __utils__["platform.is_sunos"]() or __utils__["platform.is_aix"]():
        traceroute_version = [0, 0, 0]
    else:
        version_out = __salt__["cmd.run"]("traceroute --version")
        try:
            # Linux traceroute version looks like:
            #   Modern traceroute for Linux, version 2.0.19, Dec 10 2012
            # Darwin and FreeBSD traceroute version looks like: Version 1.4a12+[FreeBSD|Darwin]

            version_raw = re.findall(
                r".*[Vv]ersion (\d+)\.([\w\+]+)\.*(\w*)", version_out
            )[0]
            log.debug("traceroute_version_raw: %s", version_raw)
            traceroute_version = []
            for t in version_raw:
                try:
                    traceroute_version.append(int(t))
                except ValueError:
                    traceroute_version.append(t)

            if len(traceroute_version) < 3:
                traceroute_version.append(0)

            log.debug("traceroute_version: %s", traceroute_version)

        except IndexError:
            traceroute_version = [0, 0, 0]

    for line in out.splitlines():
        # Pre requirements for line parsing
        skip_line = False
        if " " not in line:
            skip_line = True
        if line.startswith("traceroute"):
            skip_line = True
        if __utils__["platform.is_aix"]():
            if line.startswith("trying to get source for"):
                skip_line = True
            if line.startswith("source should be"):
                skip_line = True
            if line.startswith("outgoing MTU"):
                skip_line = True
            if line.startswith("fragmentation required"):
                skip_line = True
        if skip_line:
            log.debug("Skipping traceroute output line: %s", line)
            continue

        # Parse output from unix variants
        if (
            "Darwin" in str(traceroute_version[1])
            or "FreeBSD" in str(traceroute_version[1])
            or __grains__["kernel"] in ("SunOS", "AIX")
        ):
            try:
                traceline = re.findall(r"\s*(\d*)\s+(.*)\s+\((.*)\)\s+(.*)$", line)[0]
            except IndexError:
                traceline = re.findall(r"\s*(\d*)\s+(\*\s+\*\s+\*)", line)[0]

            log.debug("traceline: %s", traceline)
            delays = re.findall(r"(\d+\.\d+)\s*ms", str(traceline))

            try:
                if traceline[1] == "* * *":
                    result = {"count": traceline[0], "hostname": "*"}
                else:
                    result = {
                        "count": traceline[0],
                        "hostname": traceline[1],
                        "ip": traceline[2],
                    }
                    for idx, delay in enumerate(delays):
                        result[f"ms{idx + 1}"] = delay
            except IndexError:
                result = {}

        # Parse output from specific version ranges
        elif (
            traceroute_version[0] >= 2
            and traceroute_version[2] >= 14
            or traceroute_version[0] >= 2
            and traceroute_version[1] > 0
        ):
            comps = line.split("  ")
            if len(comps) >= 2 and comps[1] == "* * *":
                result = {"count": int(comps[0]), "hostname": "*"}
            elif len(comps) >= 5:
                result = {
                    "count": int(comps[0]),
                    "hostname": comps[1].split()[0],
                    "ip": comps[1].split()[1].strip("()"),
                    "ms1": float(comps[2].split()[0]),
                    "ms2": float(comps[3].split()[0]),
                    "ms3": float(comps[4].split()[0]),
                }
            else:
                result = {}

        # Parse anything else
        else:
            comps = line.split()
            if len(comps) >= 8:
                result = {
                    "count": comps[0],
                    "hostname": comps[1],
                    "ip": comps[2],
                    "ms1": comps[4],
                    "ms2": comps[6],
                    "ms3": comps[8],
                    "ping1": comps[3],
                    "ping2": comps[5],
                    "ping3": comps[7],
                }
            else:
                result = {}

        ret.append(result)
        if not result:
            log.warning("Cannot parse traceroute output line: %s", line)
    return ret


@salt.utils.decorators.path.which("dig")
def dig(host):
    """
    Performs a DNS lookup with dig

    CLI Example:

    .. code-block:: bash

        salt '*' network.dig archlinux.org
    """
    cmd = "dig {}".format(__utils__["network.sanitize_host"](host))
    return __salt__["cmd.run"](cmd)


@salt.utils.decorators.path.which("arp")
def arp():
    """
    Return the arp table from the minion

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.arp
    """
    ret = {}
    out = __salt__["cmd.run"]("arp -an")
    for line in out.splitlines():
        comps = line.split()
        if len(comps) < 4:
            continue
        if __grains__["kernel"] == "SunOS":
            if ":" not in comps[-1]:
                continue
            ret[comps[-1]] = comps[1]
        elif __grains__["kernel"] == "OpenBSD":
            if comps[0] == "Host" or comps[1] == "(incomplete)":
                continue
            ret[comps[1]] = comps[0]
        elif __grains__["kernel"] == "AIX":
            if comps[0] in ("bucket", "There"):
                continue
            ret[comps[3]] = comps[1].strip("(").strip(")")
        else:
            ret[comps[3]] = comps[1].strip("(").strip(")")

    return ret


def interfaces():
    """
    Return a dictionary of information about all the interfaces on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' network.interfaces
    """
    return __utils__["network.interfaces"]()


def hw_addr(iface):
    """
    Return the hardware address (a.k.a. MAC address) for a given interface

    CLI Example:

    .. code-block:: bash

        salt '*' network.hw_addr eth0
    """
    return __utils__["network.hw_addr"](iface)


# Alias hwaddr to preserve backward compat
hwaddr = salt.utils.functools.alias_function(hw_addr, "hwaddr")


def interface(iface):
    """
    Return the inet address for a given interface

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.interface eth0
    """
    return __utils__["network.interface"](iface)


def interface_ip(iface):
    """
    Return the inet address for a given interface

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.interface_ip eth0
    """
    return __utils__["network.interface_ip"](iface)


def subnets(interfaces=None):
    """
    Returns a list of IPv4 subnets to which the host belongs

    CLI Example:

    .. code-block:: bash

        salt '*' network.subnets
        salt '*' network.subnets interfaces=eth1
    """
    return __utils__["network.subnets"](interfaces)


def subnets6():
    """
    Returns a list of IPv6 subnets to which the host belongs

    CLI Example:

    .. code-block:: bash

        salt '*' network.subnets
    """
    return __utils__["network.subnets6"]()


def in_subnet(cidr):
    """
    Returns True if host is within specified subnet, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' network.in_subnet 10.0.0.0/16
    """
    return __utils__["network.in_subnet"](cidr)


def ip_in_subnet(ip_addr, cidr):
    """
    Returns True if given IP is within specified subnet, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_in_subnet 172.17.0.4 172.16.0.0/12
    """
    return __utils__["network.in_subnet"](cidr, ip_addr)


def convert_cidr(cidr):
    """
    returns the network address, subnet mask and broadcast address of a cidr address

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.convert_cidr 172.31.0.0/16
    """
    ret = {"network": None, "netmask": None, "broadcast": None}
    cidr = calc_net(cidr)
    network_info = ipaddress.ip_network(cidr)
    ret["network"] = str(network_info.network_address)
    ret["netmask"] = str(network_info.netmask)
    ret["broadcast"] = str(network_info.broadcast_address)
    return ret


def calc_net(ip_addr, netmask=None):
    """
    Returns the CIDR of a subnet based on
    an IP address (CIDR notation supported)
    and optional netmask.

    CLI Example:

    .. code-block:: bash

        salt '*' network.calc_net 172.17.0.5 255.255.255.240
        salt '*' network.calc_net 2a02:f6e:a000:80:84d8:8332:7866:4e07/64

    .. versionadded:: 2015.8.0
    """
    return __utils__["network.calc_net"](ip_addr, netmask)


def ip_addrs(interface=None, include_loopback=False, cidr=None, type=None):
    """
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.
    Providing a CIDR via 'cidr="10.0.0.0/8"' will return only the addresses
    which are within that subnet. If 'type' is 'public', then only public
    addresses will be returned. Ditto for 'type'='private'.

    .. versionchanged:: 3001
        ``interface`` can now be a single interface name or a list of
        interfaces. Globbing is also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs
    """
    addrs = __utils__["network.ip_addrs"](
        interface=interface, include_loopback=include_loopback
    )
    if cidr:
        return [i for i in addrs if __utils__["network.in_subnet"](cidr, [i])]
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
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.
    Providing a CIDR via 'cidr="2000::/3"' will return only the addresses
    which are within that subnet.

    .. versionchanged:: 3001
        ``interface`` can now be a single interface name or a list of
        interfaces. Globbing is also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs6
    """
    addrs = __utils__["network.ip_addrs6"](
        interface=interface, include_loopback=include_loopback
    )
    if cidr:
        return [i for i in addrs if __utils__["network.in_subnet"](cidr, [i])]
    else:
        return addrs


ipaddrs6 = salt.utils.functools.alias_function(ip_addrs6, "ipaddrs6")


def get_hostname():
    """
    Get hostname

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_hostname
    """

    return socket.gethostname()


def get_fqdn():
    """
    Get fully qualified domain name

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_fqdn
    """

    return socket.getfqdn()


def mod_hostname(hostname):
    """
    Modify hostname

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    CLI Example:

    .. code-block:: bash

        salt '*' network.mod_hostname master.saltstack.com
    """
    #
    # SunOS tested on SmartOS and OmniOS (Solaris 10 compatible)
    # Oracle Solaris 11 uses smf, currently not supported
    #
    # /etc/nodename is the hostname only, not fqdn
    # /etc/defaultdomain is the domain
    # /etc/hosts should have both fqdn and hostname entries
    #

    if hostname is None:
        return False

    hostname_cmd = __utils__["path.which"]("hostnamectl") or __utils__["path.which"](
        "hostname"
    )
    if __utils__["platform.is_sunos"]():
        uname_cmd = (
            "/usr/bin/uname"
            if __utils__["platform.is_smartos"]()
            else __utils__["path.which"]("uname")
        )
        check_hostname_cmd = __utils__["path.which"]("check-hostname")

    # Grab the old hostname so we know which hostname to change and then
    # change the hostname using the hostname command
    if hostname_cmd.endswith("hostnamectl"):
        result = __salt__["cmd.run_all"](f"{hostname_cmd} status")
        if 0 == result["retcode"]:
            out = result["stdout"]
            for line in out.splitlines():
                line = line.split(":")
                if "Static hostname" in line[0]:
                    o_hostname = line[1].strip()
        else:
            log.debug("%s was unable to get hostname", hostname_cmd)
            o_hostname = __salt__["network.get_hostname"]()
    elif not __utils__["platform.is_sunos"]():
        # don't run hostname -f because -f is not supported on all platforms
        o_hostname = socket.getfqdn()
    else:
        # output: Hostname core OK: fully qualified as core.acheron.be
        o_hostname = __salt__["cmd.run"](check_hostname_cmd).split(" ")[-1]

    if hostname_cmd.endswith("hostnamectl"):
        result = __salt__["cmd.run_all"](
            "{} set-hostname {}".format(
                hostname_cmd,
                hostname,
            )
        )
        if result["retcode"] != 0:
            log.debug(
                "%s was unable to set hostname. Error: %s",
                hostname_cmd,
                result["stderr"],
            )
            return False
    elif not __utils__["platform.is_sunos"]():
        __salt__["cmd.run"](f"{hostname_cmd} {hostname}")
    else:
        __salt__["cmd.run"]("{} -S {}".format(uname_cmd, hostname.split(".")[0]))

    # Modify the /etc/hosts file to replace the old hostname with the
    # new hostname
    with __utils__["files.fopen"]("/etc/hosts", "r") as fp_:
        host_c = [__utils__["stringutils.to_unicode"](_l) for _l in fp_.readlines()]

    with __utils__["files.fopen"]("/etc/hosts", "w") as fh_:
        for host in host_c:
            host = host.split()

            try:
                host[host.index(o_hostname)] = hostname
                if __utils__["platform.is_sunos"]():
                    # also set a copy of the hostname
                    host[host.index(o_hostname.split(".")[0])] = hostname.split(".")[0]
            except ValueError:
                pass

            fh_.write(__utils__["stringutils.to_str"]("\t".join(host) + "\n"))

    # Modify the /etc/sysconfig/network configuration file to set the
    # new hostname
    if __grains__["os_family"] == "RedHat":
        with __utils__["files.fopen"]("/etc/sysconfig/network", "r") as fp_:
            network_c = [
                __utils__["stringutils.to_unicode"](_l) for _l in fp_.readlines()
            ]

        with __utils__["files.fopen"]("/etc/sysconfig/network", "w") as fh_:
            for net in network_c:
                if net.startswith("HOSTNAME"):
                    old_hostname = net.split("=", 1)[1].rstrip()
                    quote_type = __utils__["stringutils.is_quoted"](old_hostname)
                    fh_.write(
                        __utils__["stringutils.to_str"](
                            "HOSTNAME={1}{0}{1}\n".format(
                                __utils__["stringutils.dequote"](hostname), quote_type
                            )
                        )
                    )
                else:
                    fh_.write(__utils__["stringutils.to_str"](net))
    elif __grains__["os_family"] in ("Debian", "NILinuxRT"):
        with __utils__["files.fopen"]("/etc/hostname", "w") as fh_:
            fh_.write(__utils__["stringutils.to_str"](hostname + "\n"))
        if __grains__["lsb_distrib_id"] == "nilrt":
            str_hostname = __utils__["stringutils.to_str"](hostname)
            nirtcfg_cmd = "/usr/local/natinst/bin/nirtcfg"
            nirtcfg_cmd += (
                " --set section=SystemSettings,token='Host_Name',value='{}'".format(
                    str_hostname
                )
            )
            if __salt__["cmd.run_all"](nirtcfg_cmd)["retcode"] != 0:
                raise CommandExecutionError(
                    f"Couldn't set hostname to: {str_hostname}\n"
                )
    elif __grains__["os_family"] == "OpenBSD":
        with __utils__["files.fopen"]("/etc/myname", "w") as fh_:
            fh_.write(__utils__["stringutils.to_str"](hostname + "\n"))

    # Update /etc/nodename and /etc/defaultdomain on SunOS
    if __utils__["platform.is_sunos"]():
        with __utils__["files.fopen"]("/etc/nodename", "w") as fh_:
            fh_.write(__utils__["stringutils.to_str"](hostname.split(".")[0] + "\n"))
        with __utils__["files.fopen"]("/etc/defaultdomain", "w") as fh_:
            fh_.write(
                __utils__["stringutils.to_str"](
                    ".".join(hostname.split(".")[1:]) + "\n"
                )
            )

    return True


def connect(host, port=None, **kwargs):
    """
    Test connectivity to a host using a particular
    port from the minion.

    .. versionadded:: 2014.7.0

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
        address = "{}".format(__utils__["network.sanitize_host"](host))

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
    except socket.gaierror:
        ret["result"] = False
        ret["comment"] = "Unable to resolve host {} on {} port {}".format(
            host, proto, port
        )
        return ret

    try:
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

    .. versionadded:: 2014.7.0
    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.is_private 10.0.0.3
    """
    return ipaddress.ip_address(ip_addr).is_private


def is_loopback(ip_addr):
    """
    Check if the given IP address is a loopback address

    .. versionadded:: 2014.7.0
    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.is_loopback 127.0.0.1
    """
    return ipaddress.ip_address(ip_addr).is_loopback


def reverse_ip(ip_addr):
    """
    Returns the reversed IP address

    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.reverse_ip 172.17.0.4
    """
    return ipaddress.ip_address(ip_addr).reverse_pointer


def _get_bufsize_linux(iface):
    """
    Return network interface buffer information using ethtool
    """
    ret = {"result": False}

    cmd = f"/sbin/ethtool -g {iface}"
    out = __salt__["cmd.run"](cmd)
    pat = re.compile(r"^(.+):\s+(\d+)$")
    suffix = "max-"
    for line in out.splitlines():
        res = pat.match(line)
        if res:
            ret[res.group(1).lower().replace(" ", "-") + suffix] = int(res.group(2))
            ret["result"] = True
        elif line.endswith("maximums:"):
            suffix = "-max"
        elif line.endswith("settings:"):
            suffix = ""
    if not ret["result"]:
        parts = out.split()
        # remove shell cmd prefix from msg
        if parts[0].endswith("sh:"):
            out = " ".join(parts[1:])
        ret["comment"] = out
    return ret


def get_bufsize(iface):
    """
    Return network buffer sizes as a dict (currently linux only)

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_bufsize eth0
    """
    if __grains__["kernel"] == "Linux":
        if os.path.exists("/sbin/ethtool"):
            return _get_bufsize_linux(iface)

    return {}


def _mod_bufsize_linux(iface, *args, **kwargs):
    """
    Modify network interface buffer sizes using ethtool
    """
    ret = {
        "result": False,
        "comment": "Requires rx=<val> tx==<val> rx-mini=<val> and/or rx-jumbo=<val>",
    }
    cmd = "/sbin/ethtool -G " + iface
    if not kwargs:
        return ret
    if args:
        ret["comment"] = "Unknown arguments: " + " ".join([str(item) for item in args])
        return ret
    eargs = ""
    for kw in ["rx", "tx", "rx-mini", "rx-jumbo"]:
        value = kwargs.get(kw)
        if value is not None:
            eargs += " " + kw + " " + str(value)
    if not eargs:
        return ret
    cmd += eargs
    out = __salt__["cmd.run"](cmd)
    if out:
        ret["comment"] = out
    else:
        ret["comment"] = eargs.strip()
        ret["result"] = True
    return ret


def mod_bufsize(iface, *args, **kwargs):
    """
    Modify network interface buffers (currently linux only)

    CLI Example:

    .. code-block:: bash

        salt '*' network.mod_bufsize tx=<val> rx=<val> rx-mini=<val> rx-jumbo=<val>
    """
    if __grains__["kernel"] == "Linux":
        if os.path.exists("/sbin/ethtool"):
            return _mod_bufsize_linux(iface, *args, **kwargs)

    return False


def routes(family=None):
    """
    Return currently configured routes from routing table

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' network.routes
    """
    if family != "inet" and family != "inet6" and family is not None:
        raise CommandExecutionError(f"Invalid address family {family}")

    if __grains__["kernel"] == "Linux":
        if not __utils__["path.which"]("netstat"):
            routes_ = _ip_route_linux()
        else:
            routes_ = _netstat_route_linux()
    elif __grains__["kernel"] == "SunOS":
        routes_ = _netstat_route_sunos()
    elif __grains__["os"] in ["FreeBSD", "MacOS", "Darwin"]:
        routes_ = _netstat_route_freebsd()
    elif __grains__["os"] in ["NetBSD"]:
        routes_ = _netstat_route_netbsd()
    elif __grains__["os"] in ["OpenBSD"]:
        routes_ = _netstat_route_openbsd()
    elif __grains__["os"] in ["AIX"]:
        routes_ = _netstat_route_aix()
    else:
        raise CommandExecutionError("Not yet supported on this platform")

    if not family:
        return routes_
    else:
        ret = [route for route in routes_ if route["addr_family"] == family]
        return ret


def default_route(family=None):
    """
    Return default route(s) from routing table

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' network.default_route
    """
    if family != "inet" and family != "inet6" and family is not None:
        raise CommandExecutionError(f"Invalid address family {family}")

    _routes = routes(family)

    default_route = {}
    if __grains__["kernel"] == "Linux":
        default_route["inet"] = ["0.0.0.0", "default"]
        default_route["inet6"] = ["::/0", "default"]
    elif __grains__["os"] in [
        "FreeBSD",
        "NetBSD",
        "OpenBSD",
        "MacOS",
        "Darwin",
    ] or __grains__["kernel"] in ("SunOS", "AIX"):
        default_route["inet"] = ["default"]
        default_route["inet6"] = ["default"]
    else:
        raise CommandExecutionError("Not yet supported on this platform")

    ret = []
    for route in _routes:
        if family:
            if route["destination"] in default_route[family]:
                if __grains__["kernel"] == "SunOS" and route["addr_family"] != family:
                    continue
                ret.append(route)
        else:
            if (
                route["destination"] in default_route["inet"]
                or route["destination"] in default_route["inet6"]
            ):
                ret.append(route)

    return ret


def get_route(ip):
    """
    Return routing information for given destination ip

    .. versionadded:: 2015.5.3

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)
        Added support for OpenBSD

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_route 10.10.10.10
    """

    if __grains__["kernel"] == "Linux":
        cmd = f"ip route get {ip}"
        out = __salt__["cmd.run"](cmd, python_shell=True)
        regexp = re.compile(
            r"(via\s+(?P<gateway>[\w\.:]+))?\s+dev\s+(?P<interface>[\w\.\:\-]+)\s+.*src\s+(?P<source>[\w\.:]+)"
        )
        m = regexp.search(out.splitlines()[0])
        ret = {
            "destination": ip,
            "gateway": m.group("gateway"),
            "interface": m.group("interface"),
            "source": m.group("source"),
        }

        return ret

    if __grains__["kernel"] == "SunOS":
        # [root@nacl ~]# route -n get 172.16.10.123
        #   route to: 172.16.10.123
        # destination: 172.16.10.0
        #       mask: 255.255.255.0
        #  interface: net0
        #      flags: <UP,DONE,KERNEL>
        # recvpipe  sendpipe  ssthresh    rtt,ms rttvar,ms  hopcount      mtu     expire
        #       0         0         0         0         0         0      1500         0
        cmd = f"/usr/sbin/route -n get {ip}"
        out = __salt__["cmd.run"](cmd, python_shell=False)

        ret = {"destination": ip, "gateway": None, "interface": None, "source": None}

        for line in out.splitlines():
            line = line.split(":")
            if "route to" in line[0]:
                ret["destination"] = line[1].strip()
            if "gateway" in line[0]:
                ret["gateway"] = line[1].strip()
            if "interface" in line[0]:
                ret["interface"] = line[1].strip()
                ret["source"] = __utils__["network.interface_ip"](line[1].strip())

        return ret

    if __grains__["kernel"] == "OpenBSD":
        # [root@exosphere] route -n get blackdot.be
        #   route to: 5.135.127.100
        # destination: default
        #       mask: default
        #    gateway: 192.168.0.1
        #  interface: vio0
        # if address: 192.168.0.2
        #   priority: 8 (static)
        #      flags: <UP,GATEWAY,DONE,STATIC>
        #     use       mtu    expire
        # 8352657         0         0
        cmd = f"route -n get {ip}"
        out = __salt__["cmd.run"](cmd, python_shell=False)

        ret = {"destination": ip, "gateway": None, "interface": None, "source": None}

        for line in out.splitlines():
            line = line.split(":")
            if "route to" in line[0]:
                ret["destination"] = line[1].strip()
            if "gateway" in line[0]:
                ret["gateway"] = line[1].strip()
            if "interface" in line[0]:
                ret["interface"] = line[1].strip()
            if "if address" in line[0]:
                ret["source"] = line[1].strip()

        return ret

    if __grains__["kernel"] == "AIX":
        # root@la68pp002_pub:~# route -n get 172.29.149.95
        #   route to: 172.29.149.95
        # destination: 172.29.149.95
        #    gateway: 127.0.0.1
        #  interface: lo0
        # interf addr: 127.0.0.1
        #     flags: <UP,GATEWAY,HOST,DONE,STATIC>
        # recvpipe  sendpipe  ssthresh  rtt,msec    rttvar  hopcount      mtu     expire
        #      0         0         0         0         0         0         0    -68642
        cmd = f"route -n get {ip}"
        out = __salt__["cmd.run"](cmd, python_shell=False)

        ret = {"destination": ip, "gateway": None, "interface": None, "source": None}

        for line in out.splitlines():
            line = line.split(":")
            if "route to" in line[0]:
                ret["destination"] = line[1].strip()
            if "gateway" in line[0]:
                ret["gateway"] = line[1].strip()
            if "interface" in line[0]:
                ret["interface"] = line[1].strip()
            if "interf addr" in line[0]:
                ret["source"] = line[1].strip()

        return ret

    else:
        raise CommandExecutionError("Not yet supported on this platform")


def ifacestartswith(cidr):
    """
    Retrieve the interface name from a specific CIDR

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.ifacestartswith 10.0
    """
    net_list = interfaces()
    intfnames = []
    pattern = str(cidr)
    size = len(pattern)
    for ifname, ifval in net_list.items():
        if "inet" in ifval:
            for inet in ifval["inet"]:
                if inet["address"][0:size] == pattern:
                    if "label" in inet:
                        intfnames.append(inet["label"])
                    else:
                        intfnames.append(ifname)
    return intfnames


def iphexval(ip):
    """
    Retrieve the hexadecimal representation of an IP address

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.iphexval 10.0.0.1
    """
    a = ip.split(".")
    hexval = ["%02X" % int(x) for x in a]
    return "".join(hexval)


def ip_networks(interface=None, include_loopback=False, verbose=False):
    """
    .. versionadded:: 3001

    Returns a list of IPv4 networks to which the minion belongs.

    interface
        Restrict results to the specified interface(s). This value can be
        either a single interface name or a list of interfaces. Globbing is
        also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_networks
        salt '*' network.ip_networks interface=docker0
        salt '*' network.ip_networks interface=docker0,enp*
        salt '*' network.ip_networks interface=eth*
    """
    return __utils__["network.ip_networks"](
        interface=interface, include_loopback=include_loopback, verbose=verbose
    )


def ip_networks6(interface=None, include_loopback=False, verbose=False):
    """
    .. versionadded:: 3001

    Returns a list of IPv6 networks to which the minion belongs.

    interface
        Restrict results to the specified interface(s). This value can be
        either a single interface name or a list of interfaces. Globbing is
        also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_networks6
        salt '*' network.ip_networks6 interface=docker0
        salt '*' network.ip_networks6 interface=docker0,enp*
        salt '*' network.ip_networks6 interface=eth*
    """
    return __utils__["network.ip_networks6"](
        interface=interface, include_loopback=include_loopback, verbose=verbose
    )


def fqdns():
    """
    Return all known FQDNs for the system by enumerating all interfaces and
    then trying to reverse resolve them (excluding 'lo' interface).

    CLI Example:

    .. code-block:: bash

        salt '*' network.fqdns
    """
    # Provides:
    # fqdns

    # Possible value for h_errno defined in netdb.h
    HOST_NOT_FOUND = 1
    NO_DATA = 4

    fqdns = set()

    def _lookup_fqdn(ip):
        # Random sleep between 0.005 and 0.025 to avoid hitting
        # the GLIBC race condition.
        # For more info, see:
        #   https://sourceware.org/bugzilla/show_bug.cgi?id=19329
        time.sleep(random.randint(5, 25) / 1000)
        try:
            return [socket.getfqdn(socket.gethostbyaddr(ip)[0])]
        except socket.herror as err:
            if err.errno in (0, HOST_NOT_FOUND, NO_DATA):
                # No FQDN for this IP address, so we don't need to know this all the time.
                log.debug("Unable to resolve address %s: %s", ip, err)
            else:
                log.error("Failed to resolve address %s: %s", ip, err)
        except Exception as err:  # pylint: disable=broad-except
            log.error("Failed to resolve address %s: %s", ip, err)

    start = time.time()

    addresses = salt.utils.network.ip_addrs(
        include_loopback=False, interface_data=salt.utils.network._get_interfaces()
    )
    addresses.extend(
        salt.utils.network.ip_addrs6(
            include_loopback=False, interface_data=salt.utils.network._get_interfaces()
        )
    )

    # Create a ThreadPool to process the underlying calls to
    # 'socket.gethostbyaddr' in parallel.  This avoid blocking the execution
    # when the "fqdn" is not defined for certains IP addresses, which was
    # causing that "socket.timeout" was reached multiple times sequentially,
    # blocking execution for several seconds.
    try:
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            future_lookups = {
                pool.submit(_lookup_fqdn, address): address for address in addresses
            }
            for future in concurrent.futures.as_completed(future_lookups):
                try:
                    resolved_fqdn = future.result()
                    if resolved_fqdn:
                        fqdns.update(resolved_fqdn)
                except Exception as exc:  # pylint: disable=broad-except
                    address = future_lookups[future]
                    log.error("Failed to resolve address %s: %s", address, exc)
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Exception while creating a ThreadPoolExecutor for resolving FQDNs: %s", exc
        )

    elapsed = time.time() - start
    log.debug("Elapsed time getting FQDNs: %s seconds", elapsed)

    return {"fqdns": sorted(fqdns)}
