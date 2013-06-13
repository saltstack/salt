'''
Module for gathering and managing network information
'''

# Import python libs
import re

# Import salt libs
import salt.utils

try:
    import salt.utils.winapi
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import 3rd party libraries
try:
    import wmi
except ImportError:
    HAS_DEPENDENCIES = False


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES is True:
        return 'network'
    return False


def ping(host):
    '''
    Performs a ping to a host

    CLI Example::

        salt '*' network.ping archlinux.org
    '''
    cmd = 'ping -n 4 {0}'.format(salt.utils.network.sanitize_host(host))
    return __salt__['cmd.run'](cmd)


def netstat():
    '''
    Return information on open ports and states

    CLI Example::

        salt '*' network.netstat
    '''
    ret = []
    cmd = 'netstat -na'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if line.startswith('  TCP'):
            ret.append({
                'local-address': comps[1],
                'proto': comps[0],
                'remote-address': comps[2],
                'state': comps[3]})
        if line.startswith('  UDP'):
            ret.append({
                'local-address': comps[1],
                'proto': comps[0],
                'remote-address': comps[2],
                'state': None})
    return ret


def traceroute(host):
    '''
    Performs a traceroute to a 3rd party host

    CLI Example::

        salt '*' network.traceroute archlinux.org
    '''
    ret = []
    cmd = 'tracert {0}'.format(salt.utils.network.sanitize_host(host))
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if not ' ' in line:
            continue
        if line.startswith('Trac'):
            continue
        if line.startswith('over'):
            continue
        comps = line.split()
        complength = len(comps)
        # This method still needs to better catch rows of other lengths
        # For example if some of the ms returns are '*'
        if complength == 9:
            result = {
                'count': comps[0],
                'hostname': comps[7],
                'ip': comps[8],
                'ms1': comps[1],
                'ms2': comps[3],
                'ms3': comps[5]}
            ret.append(result)
        elif complength == 8:
            result = {
                'count': comps[0],
                'hostname': None,
                'ip': comps[7],
                'ms1': comps[1],
                'ms2': comps[3],
                'ms3': comps[5]}
            ret.append(result)
        else:
            result = {
                'count': comps[0],
                'hostname': None,
                'ip': None,
                'ms1': None,
                'ms2': None,
                'ms3': None}
            ret.append(result)
    return ret


def nslookup(host):
    '''
    Query DNS for information about a domain or ip address

    CLI Example::

        salt '*' network.nslookup archlinux.org
    '''
    ret = []
    cmd = 'nslookup {0}'.format(salt.utils.network.sanitize_host(host))
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if line.startswith('Non-authoritative'):
            continue
        if ":" in line:
            comps = line.split(":")
            ret.append({comps[0].strip(): comps[1].strip()})
    return ret


def dig(host):
    '''
    Performs a DNS lookup with dig

    Note: dig must be installed on the Windows minion

    CLI Example::

        salt '*' network.dig archlinux.org
    '''
    cmd = 'dig {0}'.format(salt.utils.network.sanitize_host(host))
    return __salt__['cmd.run'](cmd)


def interfaces():
    '''
    Return a dictionary of information about all the interfaces on the minion

    CLI Example::

        salt '*' network.interfaces
    '''
    return salt.utils.network.interfaces()


def hwaddr(iface):
    '''
    Return the hardware address (a.k.a. MAC address) for a given interface

    CLI Example::

        salt '*' network.hwaddr eth0
    '''
    return salt.utils.network.hwaddr(iface)


def subnets():
    '''
    Returns a list of subnets to which the host belongs

    CLI Example::

        salt '*' network.subnets
    '''
    return salt.utils.network.subnets()


def in_subnet(cidr):
    '''
    Returns True if host is within specified subnet, otherwise False

    CLI Example::

        salt '*' network.in_subnet 10.0.0.0/16
    '''
    return salt.utils.network.in_subnet(cidr)


def ip_addrs(interface=None, include_loopback=False):
    '''
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.

    CLI Example::

        salt '*' network.ip_addrs
    '''
    return salt.utils.network.ip_addrs(interface=interface,
                                       include_loopback=include_loopback)


def ip_addrs6(interface=None, include_loopback=False):
    '''
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.

    CLI Example::

        salt '*' network.ip_addrs6
    '''
    return salt.utils.network.ip_addrs6(interface=interface,
                                        include_loopback=include_loopback)
