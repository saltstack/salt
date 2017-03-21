# -*- coding: utf-8 -*-
'''
Module for gathering and managing network information
'''

# Import python libs
from __future__ import absolute_import
import datetime
import hashlib
import logging
import re
import os
import socket

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
import salt.utils.network
import salt.utils.validate.net
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    # Disable on Windows, a specific file module exists:
    if salt.utils.is_windows():
        return (False, 'The network execution module cannot be loaded on Windows: use win_network instead.')
    return True


def wol(mac, bcast='255.255.255.255', destport=9):
    '''
    Send Wake On Lan packet to a host

    CLI Example:

    .. code-block:: bash

        salt '*' network.wol 08-00-27-13-69-77
        salt '*' network.wol 080027136977 255.255.255.255 7
        salt '*' network.wol 08:00:27:13:69:77 255.255.255.255 7
    '''
    dest = salt.utils.mac_str_to_bytes(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b'\xff' * 6 + dest * 16, (bcast, int(destport)))
    return True


def ping(host, timeout=False, return_boolean=False):
    '''
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
    '''
    if timeout:
        if __grains__['kernel'] == 'SunOS':
            cmd = 'ping -c 4 {1} {0}'.format(timeout, salt.utils.network.sanitize_host(host))
        else:
            cmd = 'ping -W {0} -c 4 {1}'.format(timeout, salt.utils.network.sanitize_host(host))
    else:
        cmd = 'ping -c 4 {0}'.format(salt.utils.network.sanitize_host(host))
    if return_boolean:
        ret = __salt__['cmd.run_all'](cmd)
        if ret['retcode'] != 0:
            return False
        else:
            return True
    else:
        return __salt__['cmd.run'](cmd)


# FIXME: Does not work with: netstat 1.42 (2001-04-15) from net-tools
# 1.6.0 (Ubuntu 10.10)
def _netstat_linux():
    '''
    Return netstat information for Linux distros
    '''
    ret = []
    cmd = 'netstat -tulpnea'
    out = __salt__['cmd.run'](cmd)
    for line in out.splitlines():
        comps = line.split()
        if line.startswith('tcp'):
            ret.append({
                'proto': comps[0],
                'recv-q': comps[1],
                'send-q': comps[2],
                'local-address': comps[3],
                'remote-address': comps[4],
                'state': comps[5],
                'user': comps[6],
                'inode': comps[7],
                'program': comps[8]})
        if line.startswith('udp'):
            ret.append({
                'proto': comps[0],
                'recv-q': comps[1],
                'send-q': comps[2],
                'local-address': comps[3],
                'remote-address': comps[4],
                'user': comps[5],
                'inode': comps[6],
                'program': comps[7]})
    return ret


def _netinfo_openbsd():
    '''
    Get process information for network connections using fstat
    '''
    ret = {}
    _fstat_re = re.compile(
        r'internet(6)? (?:stream tcp 0x\S+ (\S+)|dgram udp (\S+))'
        r'(?: [<>=-]+ (\S+))?$'
    )
    out = __salt__['cmd.run']('fstat')
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
            proto = 'tcp{0}'.format('' if ipv6 is None else ipv6)
        else:
            local_addr = udp
            proto = 'udp{0}'.format('' if ipv6 is None else ipv6)
        if ipv6:
            # IPv6 addresses have the address part enclosed in brackets (if the
            # address part is not a wildcard) to distinguish the address from
            # the port number. Remove them.
            local_addr = ''.join(x for x in local_addr if x not in '[]')

        # Normalize to match netstat output
        local_addr = '.'.join(local_addr.rsplit(':', 1))
        if remote_addr is None:
            remote_addr = '*.*'
        else:
            remote_addr = '.'.join(remote_addr.rsplit(':', 1))

        ret.setdefault(
            local_addr, {}).setdefault(
                remote_addr, {}).setdefault(
                    proto, {}).setdefault(
                        pid, {})['user'] = user
        ret[local_addr][remote_addr][proto][pid]['cmd'] = cmd
    return ret


def _netinfo_freebsd_netbsd():
    '''
    Get process information for network connections using sockstat
    '''
    ret = {}
    # NetBSD requires '-n' to disable port-to-service resolution
    out = __salt__['cmd.run'](
        'sockstat -46 {0} | tail -n+2'.format(
            '-n' if __grains__['kernel'] == 'NetBSD' else ''
        ), python_shell=True
    )
    for line in out.splitlines():
        user, cmd, pid, _, proto, local_addr, remote_addr = line.split()
        local_addr = '.'.join(local_addr.rsplit(':', 1))
        remote_addr = '.'.join(remote_addr.rsplit(':', 1))
        ret.setdefault(
            local_addr, {}).setdefault(
                remote_addr, {}).setdefault(
                    proto, {}).setdefault(
                        pid, {})['user'] = user
        ret[local_addr][remote_addr][proto][pid]['cmd'] = cmd
    return ret


def _ppid():
    '''
    Return a dict of pid to ppid mappings
    '''
    ret = {}
    if __grains__['kernel'] == 'SunOS':
        cmd = 'ps -a -o pid,ppid | tail +2'
    else:
        cmd = 'ps -ax -o pid,ppid | tail -n+2'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        pid, ppid = line.split()
        ret[pid] = ppid
    return ret


def _netstat_bsd():
    '''
    Return netstat information for BSD flavors
    '''
    ret = []
    if __grains__['kernel'] == 'NetBSD':
        for addr_family in ('inet', 'inet6'):
            cmd = 'netstat -f {0} -an | tail -n+3'.format(addr_family)
            out = __salt__['cmd.run'](cmd, python_shell=True)
            for line in out.splitlines():
                comps = line.split()
                entry = {
                    'proto': comps[0],
                    'recv-q': comps[1],
                    'send-q': comps[2],
                    'local-address': comps[3],
                    'remote-address': comps[4]
                }
                if entry['proto'].startswith('tcp'):
                    entry['state'] = comps[5]
                ret.append(entry)
    else:
        # Lookup TCP connections
        cmd = 'netstat -p tcp -an | tail -n+3'
        out = __salt__['cmd.run'](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append({
                'proto': comps[0],
                'recv-q': comps[1],
                'send-q': comps[2],
                'local-address': comps[3],
                'remote-address': comps[4],
                'state': comps[5]})
        # Lookup UDP connections
        cmd = 'netstat -p udp -an | tail -n+3'
        out = __salt__['cmd.run'](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append({
                'proto': comps[0],
                'recv-q': comps[1],
                'send-q': comps[2],
                'local-address': comps[3],
                'remote-address': comps[4]})

    # Add in user and program info
    ppid = _ppid()
    if __grains__['kernel'] == 'OpenBSD':
        netinfo = _netinfo_openbsd()
    elif __grains__['kernel'] in ('FreeBSD', 'NetBSD'):
        netinfo = _netinfo_freebsd_netbsd()
    for idx in range(len(ret)):
        local = ret[idx]['local-address']
        remote = ret[idx]['remote-address']
        proto = ret[idx]['proto']
        try:
            # Make a pointer to the info for this connection for easier
            # reference below
            ptr = netinfo[local][remote][proto]
        except KeyError:
            continue
        # Get the pid-to-ppid mappings for this connection
        conn_ppid = dict((x, y) for x, y in six.iteritems(ppid) if x in ptr)
        try:
            # Master pid for this connection will be the pid whose ppid isn't
            # in the subset dict we created above
            master_pid = next(iter(
                x for x, y in six.iteritems(conn_ppid) if y not in ptr
            ))
        except StopIteration:
            continue
        ret[idx]['user'] = ptr[master_pid]['user']
        ret[idx]['program'] = '/'.join((master_pid, ptr[master_pid]['cmd']))
    return ret


def _netstat_sunos():
    '''
    Return netstat information for SunOS flavors
    '''
    log.warning('User and program not (yet) supported on SunOS')

    ret = []
    for addr_family in ('inet', 'inet6'):
        # Lookup TCP connections
        cmd = 'netstat -f {0} -P tcp -an | tail +5'.format(addr_family)
        out = __salt__['cmd.run'](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append({
                'proto': 'tcp6' if addr_family == 'inet6' else 'tcp',
                'recv-q': comps[5],
                'send-q': comps[4],
                'local-address': comps[0],
                'remote-address': comps[1],
                'state': comps[6]})
        # Lookup UDP connections
        cmd = 'netstat -f {0} -P udp -an | tail +5'.format(addr_family)
        out = __salt__['cmd.run'](cmd, python_shell=True)
        for line in out.splitlines():
            comps = line.split()
            ret.append({
                'proto': 'udp6' if addr_family == 'inet6' else 'udp',
                'local-address': comps[0],
                'remote-address': comps[1] if len(comps) > 2 else ''})

    return ret


def _netstat_route_linux():
    '''
    Return netstat routing information for Linux distros
    '''
    ret = []
    cmd = 'netstat -A inet -rn | tail -n+3'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': comps[2],
            'flags': comps[3],
            'interface': comps[7]})
    cmd = 'netstat -A inet6 -rn | tail -n+3'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        if len(comps) == 6:
            ret.append({
                'addr_family': 'inet6',
                'destination': comps[0],
                'gateway': comps[1],
                'netmask': '',
                'flags': comps[3],
                'interface': comps[5]})
        elif len(comps) == 7:
            ret.append({
                'addr_family': 'inet6',
                'destination': comps[0],
                'gateway': comps[1],
                'netmask': '',
                'flags': comps[3],
                'interface': comps[6]})
        else:
            continue
    return ret


def _netstat_route_freebsd():
    '''
    Return netstat routing information for FreeBSD and macOS
    '''
    ret = []
    cmd = 'netstat -f inet -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        if __grains__['os'] == 'FreeBSD' and int(__grains__.get('osmajorrelease', 0)) < 10:
            ret.append({
                'addr_family': 'inet',
                'destination': comps[0],
                'gateway': comps[1],
                'netmask': comps[2],
                'flags': comps[3],
                'interface': comps[5]})
        else:
            ret.append({
                'addr_family': 'inet',
                'destination': comps[0],
                'gateway': comps[1],
                'netmask': '',
                'flags': comps[2],
                'interface': comps[3]})
    cmd = 'netstat -f inet6 -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet6',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[2],
            'interface': comps[3]})
    return ret


def _netstat_route_netbsd():
    '''
    Return netstat routing information for NetBSD
    '''
    ret = []
    cmd = 'netstat -f inet -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[3],
            'interface': comps[6]})
    cmd = 'netstat -f inet6 -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet6',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[3],
            'interface': comps[6]})
    return ret


def _netstat_route_openbsd():
    '''
    Return netstat routing information for OpenBSD
    '''
    ret = []
    cmd = 'netstat -f inet -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[2],
            'interface': comps[7]})
    cmd = 'netstat -f inet6 -rn | tail -n+5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet6',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[2],
            'interface': comps[7]})
    return ret


def _netstat_route_sunos():
    '''
    Return netstat routing information for SunOS
    '''
    ret = []
    cmd = 'netstat -f inet -rn | tail +5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[2],
            'interface': comps[5] if len(comps) >= 6 else ''})
    cmd = 'netstat -f inet6 -rn | tail +5'
    out = __salt__['cmd.run'](cmd, python_shell=True)
    for line in out.splitlines():
        comps = line.split()
        ret.append({
            'addr_family': 'inet6',
            'destination': comps[0],
            'gateway': comps[1],
            'netmask': '',
            'flags': comps[2],
            'interface': comps[5] if len(comps) >= 6 else ''})
    return ret


def netstat():
    '''
    Return information on open ports and states

    .. note::
        On BSD minions, the output contains PID info (where available) for each
        netstat entry, fetched from sockstat/fstat output.

    .. versionchanged:: 2014.1.4
        Added support for OpenBSD, FreeBSD, and NetBSD

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.netstat
    '''
    if __grains__['kernel'] == 'Linux':
        return _netstat_linux()
    elif __grains__['kernel'] in ('OpenBSD', 'FreeBSD', 'NetBSD'):
        return _netstat_bsd()
    elif __grains__['kernel'] == 'SunOS':
        return _netstat_sunos()
    raise CommandExecutionError('Not yet supported on this platform')


def active_tcp():
    '''
    Return a dict containing information on all of the running TCP connections (currently linux and solaris only)

    .. versionchanged:: 2015.8.4

        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.active_tcp
    '''
    if __grains__['kernel'] == 'Linux':
        return salt.utils.network.active_tcp()
    elif __grains__['kernel'] == 'SunOS':
        # lets use netstat to mimic linux as close as possible
        ret = {}
        for connection in _netstat_sunos():
            if not connection['proto'].startswith('tcp'):
                continue
            if connection['state'] != 'ESTABLISHED':
                continue
            ret[len(ret)+1] = {
                'local_addr': '.'.join(connection['local-address'].split('.')[:-1]),
                'local_port': '.'.join(connection['local-address'].split('.')[-1:]),
                'remote_addr': '.'.join(connection['remote-address'].split('.')[:-1]),
                'remote_port': '.'.join(connection['remote-address'].split('.')[-1:])
            }
        return ret
    else:
        return {}


def traceroute(host):
    '''
    Performs a traceroute to a 3rd party host

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.traceroute archlinux.org
    '''
    ret = []
    if not salt.utils.which('traceroute'):
        log.info('This minion does not have traceroute installed')
        return ret

    cmd = 'traceroute {0}'.format(salt.utils.network.sanitize_host(host))

    out = __salt__['cmd.run'](cmd)

    # Parse version of traceroute
    if salt.utils.is_sunos():
        traceroute_version = [0, 0, 0]
    else:
        cmd2 = 'traceroute --version'
        out2 = __salt__['cmd.run'](cmd2)
        try:
            # Linux traceroute version looks like:
            #   Modern traceroute for Linux, version 2.0.19, Dec 10 2012
            # Darwin and FreeBSD traceroute version looks like: Version 1.4a12+[FreeBSD|Darwin]

            traceroute_version_raw = re.findall(r'.*[Vv]ersion (\d+)\.([\w\+]+)\.*(\w*)', out2)[0]
            log.debug('traceroute_version_raw: {0}'.format(traceroute_version_raw))
            traceroute_version = []
            for t in traceroute_version_raw:
                try:
                    traceroute_version.append(int(t))
                except ValueError:
                    traceroute_version.append(t)

            if len(traceroute_version) < 3:
                traceroute_version.append(0)

            log.debug('traceroute_version: {0}'.format(traceroute_version))

        except IndexError:
            traceroute_version = [0, 0, 0]

    for line in out.splitlines():
        if ' ' not in line:
            continue
        if line.startswith('traceroute'):
            continue

        if 'Darwin' in str(traceroute_version[1]) or 'FreeBSD' in str(traceroute_version[1]) or \
            __grains__['kernel'] == 'SunOS':
            try:
                traceline = re.findall(r'\s*(\d*)\s+(.*)\s+\((.*)\)\s+(.*)$', line)[0]
            except IndexError:
                traceline = re.findall(r'\s*(\d*)\s+(\*\s+\*\s+\*)', line)[0]

            log.debug('traceline: {0}'.format(traceline))
            delays = re.findall(r'(\d+\.\d+)\s*ms', str(traceline))

            try:
                if traceline[1] == '* * *':
                    result = {
                        'count': traceline[0],
                        'hostname': '*'
                    }
                else:
                    result = {
                        'count': traceline[0],
                        'hostname': traceline[1],
                        'ip': traceline[2],
                    }
                    for idx in range(0, len(delays)):
                        result['ms{0}'.format(idx + 1)] = delays[idx]
            except IndexError:
                result = {}

        elif (traceroute_version[0] >= 2 and traceroute_version[2] >= 14
                or traceroute_version[0] >= 2 and traceroute_version[1] > 0):
            comps = line.split('  ')
            if comps[1] == '* * *':
                result = {
                    'count': int(comps[0]),
                    'hostname': '*'}
            else:
                result = {
                    'count': int(comps[0]),
                    'hostname': comps[1].split()[0],
                    'ip': comps[1].split()[1].strip('()'),
                    'ms1': float(comps[2].split()[0]),
                    'ms2': float(comps[3].split()[0]),
                    'ms3': float(comps[4].split()[0])}
        else:
            comps = line.split()
            result = {
                'count': comps[0],
                'hostname': comps[1],
                'ip': comps[2],
                'ms1': comps[4],
                'ms2': comps[6],
                'ms3': comps[8],
                'ping1': comps[3],
                'ping2': comps[5],
                'ping3': comps[7]}

        ret.append(result)

    return ret


@decorators.which('dig')
def dig(host):
    '''
    Performs a DNS lookup with dig

    CLI Example:

    .. code-block:: bash

        salt '*' network.dig archlinux.org
    '''
    cmd = 'dig {0}'.format(salt.utils.network.sanitize_host(host))
    return __salt__['cmd.run'](cmd)


@decorators.which('arp')
def arp():
    '''
    Return the arp table from the minion

    .. versionchanged:: 2015.8.0
        Added support for SunOS

    CLI Example:

    .. code-block:: bash

        salt '*' network.arp
    '''
    ret = {}
    out = __salt__['cmd.run']('arp -an')
    for line in out.splitlines():
        comps = line.split()
        if len(comps) < 4:
            continue
        if __grains__['kernel'] == 'SunOS':
            if ':' not in comps[-1]:
                continue
            ret[comps[-1]] = comps[1]
        elif __grains__['kernel'] == 'OpenBSD':
            if comps[0] == 'Host' or comps[1] == '(incomplete)':
                continue
            ret[comps[1]] = comps[0]
        else:
            ret[comps[3]] = comps[1].strip('(').strip(')')
    return ret


def interfaces():
    '''
    Return a dictionary of information about all the interfaces on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' network.interfaces
    '''
    return salt.utils.network.interfaces()


def hw_addr(iface):
    '''
    Return the hardware address (a.k.a. MAC address) for a given interface

    CLI Example:

    .. code-block:: bash

        salt '*' network.hw_addr eth0
    '''
    return salt.utils.network.hw_addr(iface)

# Alias hwaddr to preserve backward compat
hwaddr = salt.utils.alias_function(hw_addr, 'hwaddr')


def interface(iface):
    '''
    Return the inet address for a given interface

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.interface eth0
    '''
    return salt.utils.network.interface(iface)


def interface_ip(iface):
    '''
    Return the inet address for a given interface

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.interface_ip eth0
    '''
    return salt.utils.network.interface_ip(iface)


def subnets(interfaces=None):
    '''
    Returns a list of IPv4 subnets to which the host belongs

    CLI Example:

    .. code-block:: bash

        salt '*' network.subnets
        salt '*' network.subnets interfaces=eth1
    '''
    return salt.utils.network.subnets(interfaces)


def subnets6():
    '''
    Returns a list of IPv6 subnets to which the host belongs

    CLI Example:

    .. code-block:: bash

        salt '*' network.subnets
    '''
    return salt.utils.network.subnets6()


def in_subnet(cidr):
    '''
    Returns True if host is within specified subnet, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' network.in_subnet 10.0.0.0/16
    '''
    return salt.utils.network.in_subnet(cidr)


def ip_in_subnet(ip_addr, cidr):
    '''
    Returns True if given IP is within specified subnet, otherwise False.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_in_subnet 172.17.0.4 172.16.0.0/12
    '''
    return salt.utils.network.in_subnet(cidr, ip_addr)


def convert_cidr(cidr):
    '''
    returns the network and subnet mask of a cidr addr

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.convert_cidr 172.31.0.0/16
    '''
    ret = {'network': None,
           'netmask': None}
    cidr = calc_net(cidr)
    network_info = salt.ext.ipaddress.ip_network(cidr)
    ret['network'] = str(network_info.network_address)
    ret['netmask'] = str(network_info.netmask)
    return ret


def calc_net(ip_addr, netmask=None):
    '''
    Returns the CIDR of a subnet based on
    an IP address (CIDR notation supported)
    and optional netmask.

    CLI Example:

    .. code-block:: bash

        salt '*' network.calc_net 172.17.0.5 255.255.255.240
        salt '*' network.calc_net 2a02:f6e:a000:80:84d8:8332:7866:4e07/64

    .. versionadded:: 2015.8.0
    '''
    return salt.utils.network.calc_net(ip_addr, netmask)


def ip_addrs(interface=None, include_loopback=False, cidr=None, type=None):
    '''
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.
    Providing a CIDR via 'cidr="10.0.0.0/8"' will return only the addresses
    which are within that subnet. If 'type' is 'public', then only public
    addresses will be returned. Ditto for 'type'='private'.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs
    '''
    addrs = salt.utils.network.ip_addrs(interface=interface,
                                        include_loopback=include_loopback)
    if cidr:
        return [i for i in addrs if salt.utils.network.in_subnet(cidr, [i])]
    else:
        if type == 'public':
            return [i for i in addrs if not is_private(i)]
        elif type == 'private':
            return [i for i in addrs if is_private(i)]
        else:
            return addrs


ipaddrs = salt.utils.alias_function(ip_addrs, 'ipaddrs')


def ip_addrs6(interface=None, include_loopback=False, cidr=None):
    '''
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.
    Providing a CIDR via 'cidr="2000::/3"' will return only the addresses
    which are within that subnet.

    CLI Example:

    .. code-block:: bash

        salt '*' network.ip_addrs6
    '''
    addrs = salt.utils.network.ip_addrs6(interface=interface,
                                        include_loopback=include_loopback)
    if cidr:
        return [i for i in addrs if salt.utils.network.in_subnet(cidr, [i])]
    else:
        return addrs

ipaddrs6 = salt.utils.alias_function(ip_addrs6, 'ipaddrs6')


def get_hostname():
    '''
    Get hostname

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_hostname
    '''

    from socket import gethostname
    return gethostname()


def mod_hostname(hostname):
    '''
    Modify hostname

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    CLI Example:

    .. code-block:: bash

        salt '*' network.mod_hostname master.saltstack.com
    '''
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

    hostname_cmd = salt.utils.which('hostnamectl') or salt.utils.which('hostname')
    if salt.utils.is_sunos():
        uname_cmd = '/usr/bin/uname' if salt.utils.is_smartos() else salt.utils.which('uname')
        check_hostname_cmd = salt.utils.which('check-hostname')

    # Grab the old hostname so we know which hostname to change and then
    # change the hostname using the hostname command
    if hostname_cmd.endswith('hostnamectl'):
        out = __salt__['cmd.run']('{0} status'.format(hostname_cmd))
        for line in out.splitlines():
            line = line.split(':')
            if 'Static hostname' in line[0]:
                o_hostname = line[1].strip()
    elif not salt.utils.is_sunos():
        # don't run hostname -f because -f is not supported on all platforms
        o_hostname = socket.getfqdn()
    else:
        # output: Hostname core OK: fully qualified as core.acheron.be
        o_hostname = __salt__['cmd.run'](check_hostname_cmd).split(' ')[-1]

    if hostname_cmd.endswith('hostnamectl'):
        __salt__['cmd.run']('{0} set-hostname {1}'.format(hostname_cmd, hostname))
    elif not salt.utils.is_sunos():
        __salt__['cmd.run']('{0} {1}'.format(hostname_cmd, hostname))
    else:
        __salt__['cmd.run']('{0} -S {1}'.format(uname_cmd, hostname.split('.')[0]))

    # Modify the /etc/hosts file to replace the old hostname with the
    # new hostname
    with salt.utils.fopen('/etc/hosts', 'r') as fp_:
        host_c = fp_.readlines()

    with salt.utils.fopen('/etc/hosts', 'w') as fh_:
        for host in host_c:
            host = host.split()

            try:
                host[host.index(o_hostname)] = hostname
                if salt.utils.is_sunos():
                    # also set a copy of the hostname
                    host[host.index(o_hostname.split('.')[0])] = hostname.split('.')[0]
            except ValueError:
                pass

            fh_.write('\t'.join(host) + '\n')

    # Modify the /etc/sysconfig/network configuration file to set the
    # new hostname
    if __grains__['os_family'] == 'RedHat':
        with salt.utils.fopen('/etc/sysconfig/network', 'r') as fp_:
            network_c = fp_.readlines()

        with salt.utils.fopen('/etc/sysconfig/network', 'w') as fh_:
            for net in network_c:
                if net.startswith('HOSTNAME'):
                    fh_.write('HOSTNAME={0}\n'.format(hostname))
                else:
                    fh_.write(net)
    elif __grains__['os_family'] in ('Debian', 'NILinuxRT'):
        with salt.utils.fopen('/etc/hostname', 'w') as fh_:
            fh_.write(hostname + '\n')
    elif __grains__['os_family'] == 'OpenBSD':
        with salt.utils.fopen('/etc/myname', 'w') as fh_:
            fh_.write(hostname + '\n')

    # Update /etc/nodename and /etc/defaultdomain on SunOS
    if salt.utils.is_sunos():
        with salt.utils.fopen('/etc/nodename', 'w') as fh_:
            fh_.write(hostname.split('.')[0] + '\n')
        with salt.utils.fopen('/etc/defaultdomain', 'w') as fh_:
            fh_.write(".".join(hostname.split('.')[1:]) + '\n')

    return True


def connect(host, port=None, **kwargs):
    '''
    Test connectivity to a host using a particular
    port from the minion.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.connect archlinux.org 80

        salt '*' network.connect archlinux.org 80 timeout=3

        salt '*' network.connect archlinux.org 80 timeout=3 family=ipv4

        salt '*' network.connect google-public-dns-a.google.com port=53 proto=udp timeout=3
    '''

    ret = {'result': None,
           'comment': ''}

    if not host:
        ret['result'] = False
        ret['comment'] = 'Required argument, host, is missing.'
        return ret

    if not port:
        ret['result'] = False
        ret['comment'] = 'Required argument, port, is missing.'
        return ret

    proto = kwargs.get('proto', 'tcp')
    timeout = kwargs.get('timeout', 5)
    family = kwargs.get('family', None)

    if salt.utils.validate.net.ipv4_addr(host) or salt.utils.validate.net.ipv6_addr(host):
        address = host
    else:
        address = '{0}'.format(salt.utils.network.sanitize_host(host))

    try:
        if proto == 'udp':
            __proto = socket.SOL_UDP
        else:
            __proto = socket.SOL_TCP
            proto = 'tcp'

        if family:
            if family == 'ipv4':
                __family = socket.AF_INET
            elif family == 'ipv6':
                __family = socket.AF_INET6
            else:
                __family = 0
        else:
            __family = 0

        (family,
         socktype,
         _proto,
         garbage,
         _address) = socket.getaddrinfo(address, port, __family, 0, __proto)[0]
    except socket.gaierror:
        ret['result'] = False
        ret['comment'] = 'Unable to resolve host {0} on {1} port {2}'.format(host, proto, port)
        return ret

    try:
        skt = socket.socket(family, socktype, _proto)
        skt.settimeout(timeout)

        if proto == 'udp':
            # Generate a random string of a
            # decent size to test UDP connection
            md5h = hashlib.md5()
            md5h.update(datetime.datetime.now().strftime('%s'))
            msg = md5h.hexdigest()
            skt.sendto(msg, _address)
            recv, svr = skt.recvfrom(255)
            skt.close()
        else:
            skt.connect(_address)
            skt.shutdown(2)
    except Exception as exc:
        ret['result'] = False
        ret['comment'] = 'Unable to connect to {0} ({1}) on {2} port {3}'.format(host, _address[0], proto, port)
        return ret

    ret['result'] = True
    ret['comment'] = 'Successfully connected to {0} ({1}) on {2} port {3}'.format(host, _address[0], proto, port)
    return ret


def is_private(ip_addr):
    '''
    Check if the given IP address is a private address

    .. versionadded:: 2014.7.0
    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.is_private 10.0.0.3
    '''
    return ipaddress.ip_address(ip_addr).is_private


def is_loopback(ip_addr):
    '''
    Check if the given IP address is a loopback address

    .. versionadded:: 2014.7.0
    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.is_loopback 127.0.0.1
    '''
    return ipaddress.ip_address(ip_addr).is_loopback


def reverse_ip(ip_addr):
    '''
    Returns the reversed IP address

    .. versionchanged:: 2015.8.0
        IPv6 support

    CLI Example:

    .. code-block:: bash

        salt '*' network.reverse_ip 172.17.0.4
    '''
    return ipaddress.ip_address(ip_addr).reverse_pointer


def _get_bufsize_linux(iface):
    '''
    Return network interface buffer information using ethtool
    '''
    ret = {'result': False}

    cmd = '/sbin/ethtool -g {0}'.format(iface)
    out = __salt__['cmd.run'](cmd)
    pat = re.compile(r'^(.+):\s+(\d+)$')
    suffix = 'max-'
    for line in out.splitlines():
        res = pat.match(line)
        if res:
            ret[res.group(1).lower().replace(' ', '-') + suffix] = int(res.group(2))
            ret['result'] = True
        elif line.endswith('maximums:'):
            suffix = '-max'
        elif line.endswith('settings:'):
            suffix = ''
    if not ret['result']:
        parts = out.split()
        # remove shell cmd prefix from msg
        if parts[0].endswith('sh:'):
            out = ' '.join(parts[1:])
        ret['comment'] = out
    return ret


def get_bufsize(iface):
    '''
    Return network buffer sizes as a dict (currently linux only)

    CLI Example:

    .. code-block:: bash

        salt '*' network.get_bufsize eth0
    '''
    if __grains__['kernel'] == 'Linux':
        if os.path.exists('/sbin/ethtool'):
            return _get_bufsize_linux(iface)

    return {}


def _mod_bufsize_linux(iface, *args, **kwargs):
    '''
    Modify network interface buffer sizes using ethtool
    '''
    ret = {'result': False,
           'comment': 'Requires rx=<val> tx==<val> rx-mini=<val> and/or rx-jumbo=<val>'}
    cmd = '/sbin/ethtool -G ' + iface
    if not kwargs:
        return ret
    if args:
        ret['comment'] = 'Unknown arguments: ' + ' '.join([str(item) for item in args])
        return ret
    eargs = ''
    for kw in ['rx', 'tx', 'rx-mini', 'rx-jumbo']:
        value = kwargs.get(kw)
        if value is not None:
            eargs += ' ' + kw + ' ' + str(value)
    if not eargs:
        return ret
    cmd += eargs
    out = __salt__['cmd.run'](cmd)
    if out:
        ret['comment'] = out
    else:
        ret['comment'] = eargs.strip()
        ret['result'] = True
    return ret


def mod_bufsize(iface, *args, **kwargs):
    '''
    Modify network interface buffers (currently linux only)

    CLI Example:

    .. code-block:: bash

        salt '*' network.mod_bufsize tx=<val> rx=<val> rx-mini=<val> rx-jumbo=<val>
    '''
    if __grains__['kernel'] == 'Linux':
        if os.path.exists('/sbin/ethtool'):
            return _mod_bufsize_linux(iface, *args, **kwargs)

    return False


def routes(family=None):
    '''
    Return currently configured routes from routing table

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    CLI Example:

    .. code-block:: bash

        salt '*' network.routes
    '''
    if family != 'inet' and family != 'inet6' and family is not None:
        raise CommandExecutionError('Invalid address family {0}'.format(family))

    if __grains__['kernel'] == 'Linux':
        routes_ = _netstat_route_linux()
    elif __grains__['kernel'] == 'SunOS':
        routes_ = _netstat_route_sunos()
    elif __grains__['os'] in ['FreeBSD', 'MacOS', 'Darwin']:
        routes_ = _netstat_route_freebsd()
    elif __grains__['os'] in ['NetBSD']:
        routes_ = _netstat_route_netbsd()
    elif __grains__['os'] in ['OpenBSD']:
        routes_ = _netstat_route_openbsd()
    else:
        raise CommandExecutionError('Not yet supported on this platform')

    if not family:
        return routes_
    else:
        ret = [route for route in routes_ if route['addr_family'] == family]
        return ret


def default_route(family=None):
    '''
    Return default route(s) from routing table

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)

    CLI Example:

    .. code-block:: bash

        salt '*' network.default_route
    '''

    if family != 'inet' and family != 'inet6' and family is not None:
        raise CommandExecutionError('Invalid address family {0}'.format(family))

    _routes = routes()
    default_route = {}
    if __grains__['kernel'] == 'Linux':
        default_route['inet'] = ['0.0.0.0', 'default']
        default_route['inet6'] = ['::/0', 'default']
    elif __grains__['os'] in ['FreeBSD', 'NetBSD', 'OpenBSD', 'MacOS', 'Darwin'] or \
        __grains__['kernel'] == 'SunOS':
        default_route['inet'] = ['default']
        default_route['inet6'] = ['default']
    else:
        raise CommandExecutionError('Not yet supported on this platform')

    ret = []
    for route in _routes:
        if family:
            if route['destination'] in default_route[family]:
                if __grains__['kernel'] == 'SunOS' and route['addr_family'] != family:
                    continue
                ret.append(route)
        else:
            if route['destination'] in default_route['inet'] or \
               route['destination'] in default_route['inet6']:
                ret.append(route)

    return ret


def get_route(ip):
    '''
    Return routing information for given destination ip

    .. versionadded:: 2015.5.3

    .. versionchanged:: 2015.8.0
        Added support for SunOS (Solaris 10, Illumos, SmartOS)
        Added support for OpenBSD

    CLI Example::

        salt '*' network.get_route 10.10.10.10
    '''

    if __grains__['kernel'] == 'Linux':
        cmd = 'ip route get {0}'.format(ip)
        out = __salt__['cmd.run'](cmd, python_shell=True)
        regexp = re.compile(r'(via\s+(?P<gateway>[\w\.:]+))?\s+dev\s+(?P<interface>[\w\.\:]+)\s+.*src\s+(?P<source>[\w\.:]+)')
        m = regexp.search(out.splitlines()[0])
        ret = {
            'destination': ip,
            'gateway': m.group('gateway'),
            'interface': m.group('interface'),
            'source': m.group('source')
        }

        return ret

    if __grains__['kernel'] == 'SunOS':
        # [root@nacl ~]# route -n get 172.16.10.123
        #   route to: 172.16.10.123
        #destination: 172.16.10.0
        #       mask: 255.255.255.0
        #  interface: net0
        #      flags: <UP,DONE,KERNEL>
        # recvpipe  sendpipe  ssthresh    rtt,ms rttvar,ms  hopcount      mtu     expire
        #       0         0         0         0         0         0      1500         0
        cmd = '/usr/sbin/route -n get {0}'.format(ip)
        out = __salt__['cmd.run'](cmd, python_shell=False)

        ret = {
            'destination': ip,
            'gateway': None,
            'interface': None,
            'source': None
        }

        for line in out.splitlines():
            line = line.split(':')
            if 'route to' in line[0]:
                ret['destination'] = line[1].strip()
            if 'gateway' in line[0]:
                ret['gateway'] = line[1].strip()
            if 'interface' in line[0]:
                ret['interface'] = line[1].strip()
                ret['source'] = salt.utils.network.interface_ip(line[1].strip())

        return ret

    if __grains__['kernel'] == 'OpenBSD':
        # [root@exosphere] route -n get blackdot.be
        #   route to: 5.135.127.100
        #destination: default
        #       mask: default
        #    gateway: 192.168.0.1
        #  interface: vio0
        # if address: 192.168.0.2
        #   priority: 8 (static)
        #      flags: <UP,GATEWAY,DONE,STATIC>
        #     use       mtu    expire
        # 8352657         0         0
        cmd = 'route -n get {0}'.format(ip)
        out = __salt__['cmd.run'](cmd, python_shell=False)

        ret = {
            'destination': ip,
            'gateway': None,
            'interface': None,
            'source': None
        }

        for line in out.splitlines():
            line = line.split(':')
            if 'route to' in line[0]:
                ret['destination'] = line[1].strip()
            if 'gateway' in line[0]:
                ret['gateway'] = line[1].strip()
            if 'interface' in line[0]:
                ret['interface'] = line[1].strip()
            if 'if address' in line[0]:
                ret['source'] = line[1].strip()

        return ret

    else:
        raise CommandExecutionError('Not yet supported on this platform')


def ifacestartswith(cidr):
    '''
    Retrieve the interface name from a specific CIDR

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.ifacestartswith 10.0
    '''
    net_list = interfaces()
    intfnames = []
    pattern = str(cidr)
    size = len(pattern)
    for ifname, ifval in six.iteritems(net_list):
        if 'inet' in ifval:
            for inet in ifval['inet']:
                if inet['address'][0:size] == pattern:
                    if 'label' in inet:
                        intfnames.append(inet['label'])
                    else:
                        intfnames.append(ifname)
    return intfnames


def iphexval(ip):
    '''
    Retrieve the interface name from a specific CIDR

    .. versionadded:: 2016.11.0

    CLI Example:

    .. code-block:: bash

        salt '*' network.iphexval 10.0.0.1
    '''
    a = ip.split('.')
    hexval = ""
    for val in a:
        hexval = hexval.join(hex(int(val))[2:])
    return hexval.upper()
