'''
Module for gathering and managing network information
'''

from string import ascii_letters, digits
import socket

__outputter__ = {
    'dig':     'txt',
    'ping':    'txt',
    'netstat': 'txt',
}

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        return 'network'
    return False


def _sanitize_host(host):
    '''
    Sanitize host string.
    '''
    return "".join([
        c for c in host[0:255] if c in (ascii_letters + digits + '.')
    ])


def ping(host):
    '''
    Performs a ping to a host

    CLI Example::

        salt '*' network.ping archlinux.org
    '''
    cmd = 'ping -n 4 %s' % _sanitize_host(host)
    return __salt__['cmd.run'](cmd)


def netstat():
    '''
    Return information on open ports and states

    CLI Example::

        salt '*' network.netstat
    '''
    ret = []
    cmd = 'netstat -na'
    lines = __salt__['cmd.run'](cmd).split('\n')
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
    cmd = 'tracert %s' % _sanitize_host(host)
    lines = __salt__['cmd.run'](cmd).split('\n')
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
    cmd = 'nslookup %s' % _sanitize_host(host)
    lines = __salt__['cmd.run'](cmd).split('\n')
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
    cmd = 'dig %s' % _sanitize_host(host)
    return __salt__['cmd.run'](cmd)


def isportopen(host, port):
    '''
    Return status of a port

    CLI Example::

        salt '*' network.isportopen 127.0.0.1 22
    '''

    if not (1 <= int(port) <= 65535):
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    out = sock.connect_ex((_sanitize_host(host), int(port)))

    return out


def _cidr_to_ipv4_netmask(cidr_bits):
    '''
    Returns an IPv4 netmask
    '''
    netmask = ''
    for n in range(4):
        if n:
            netmask += '.'
        if cidr_bits >= 8:
            netmask += '255'
            cidr_bits -= 8
        else:
            netmask += '%d' % (256-(2**(8-cidr_bits)))
            cidr_bits = 0
    return netmask


def interfaces():
    '''
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)

    CLI Example::

        salt '*' network.interfaces
    '''
    ret = {}
    ifaces = []
    lines = __salt__['cmd.run']('ipconfig /all').split('\r\n')
    configstart = 0
    configname = ''
    for line in lines:
        if configstart == 3:
            ifaces.append(config)
            configstart = 0
            continue
        if not line:
            configstart = configstart + 1
            continue
        if line.startswith('  '):
            comps = line.split(':', 1)
            config[configname][comps[0].rstrip(' .').strip()] =  comps[1].strip()
            continue
        if configstart == 1:
            configname = line.strip(' :')
            config = {configname: {}}
            configstart = configstart + 1
            continue
    for iface in ifaces:
        for key, val in iface.items():
            item = {}
            itemdict = {'Physical Address': 'hwaddr',
                        'IPv4 Address': 'ipaddr',
                        'Link-local IPv6 Address': 'ipaddr6',
                        'Subnet Mask': 'netmask',
                        }
            item['broadcast'] = None
            for k, v in itemdict.items():
                if k in val:
                    item[v] = val[k].rstrip('(Preferred)')
            if 'IPv4 Address' in val:
                item['up'] = True
            else:
                item['up'] = False
            ret[key] = item
    return ret


def up(interface):
    '''
    Returns True if interface is up, otherwise returns False

    CLI Example::

        salt '*' network.up 'Wireless LAN adapter Wireless Network Connection'
    '''
    data = interfaces().get(interface)
    if data:
        return data['up']
    else:
        return None


def ipaddr(interface):
    '''
    Returns the IP address for a given interface

    CLI Example::

        salt '*' network.ipaddr 'Wireless LAN adapter Wireless Network Connection'
    '''
    data = interfaces().get(interface)
    if data:
        return data['ipaddr']
    else:
        return None


def netmask(interface):
    '''
    Returns the netmask for a given interface

    CLI Example::

        salt '*' network.netmask 'Wireless LAN adapter Wireless Network Connection'
    '''
    data = interfaces().get(interface)
    if data:
        return data['netmask']
    else:
        return None


def hwaddr(interface):
    '''
    Returns the hwaddr for a given interface

    CLI Example::

        salt '*' network.hwaddr 'Wireless LAN adapter Wireless Network Connection'
    '''
    data = interfaces().get(interface)
    if data:
        return data['hwaddr']
    else:
        return None

