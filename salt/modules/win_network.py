'''
Module for gathering and managing network information
'''

# Import python libs
import re

# Import salt libs
import salt.utils
from salt.utils.socket_util import sanitize_host

__outputter__ = {
    'dig':     'txt',
    'ping':    'txt',
    'netstat': 'txt',
}


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return 'network'
    return False


def ping(host):
    '''
    Performs a ping to a host

    CLI Example::

        salt '*' network.ping archlinux.org
    '''
    cmd = 'ping -n 4 {0}'.format(sanitize_host(host))
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
    cmd = 'tracert {0}'.format(sanitize_host(host))
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
    cmd = 'nslookup {0}'.format(sanitize_host(host))
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
    cmd = 'dig {0}'.format(sanitize_host(host))
    return __salt__['cmd.run'](cmd)


def _cidr_to_ipv4_netmask(cidr_bits):
    '''
    Returns an IPv4 netmask
    '''
    netmask = ''
    for idx in range(4):
        if idx:
            netmask += '.'
        if cidr_bits >= 8:
            netmask += '255'
            cidr_bits -= 8
        else:
            netmask += '{0:d}'.format(256 - (2 ** (8 - cidr_bits)))
            cidr_bits = 0
    return netmask


def _interfaces_ipconfig(out):
    '''
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)
    '''
    ifaces = dict()
    iface = None

    for line in out.splitlines():
        if not line:
            continue
        # TODO what does Windows call Infiniband and 10/40gige adapters
        if line.startswith('Ethernet'):
            iface = ifaces[re.search('adapter (\S.+):$').group(1)]
            iface['up'] = True
            addr = None
            continue
        if iface:
            key, val = line.split(',', 1)
            key = key.strip(' .')
            val = val.strip()
            if addr and key in ('Subnet Mask'):
                addr['netmask'] = val
            elif key in ('IP Address', 'IPv4 Address'):
                if 'inet' not in iface:
                    iface['inet'] = list()
                addr = {'address': val.rstrip('(Preferred)'),
                        'netmask': None,
                        'broadcast': None}  # TODO find the broadcast
                iface['inet'].append(addr)
            elif 'IPv6 Address' in key:
                if 'inet6' not in iface:
                    iface['inet'] = list()
                # XXX What is the prefixlen!?
                addr = {'address': val.rstrip('(Preferred)'),
                        'prefixlen': None}
                iface['inet6'].append(addr)
            elif key in ('Physical Address'):
                iface['hwaddr'] = val
            elif key in ('Media State'):
                # XXX seen used for tunnel adaptors
                # might be useful
                iface['up'] = (val != 'Media disconnected')


def interfaces():
    cmd = __salt__['cmd.run']('ipconfig /all')
    ifaces = _interfaces_ipconfig(cmd)
    return ifaces
