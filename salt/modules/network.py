'''
Module for gathering and managing network information
'''

from string import ascii_letters, digits
import socket
import re
import salt.utils

__outputter__ = {
    'dig':     'txt',
    'ping':    'txt',
    'netstat': 'txt',
}

def __virtual__():
    '''
    Only work on posix-like systems
    '''

    # Disable on Windows, a specific file module exists:
    if __grains__['os'] == 'Windows':
        return False
    return 'network'


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
    cmd = 'ping -c 4 %s' % _sanitize_host(host)
    return __salt__['cmd.run'](cmd)


# FIXME: Does not work with: netstat 1.42 (2001-04-15) from net-tools 1.6.0 (Ubuntu 10.10)
def netstat():
    '''
    Return information on open ports and states

    CLI Example::

        salt '*' network.netstat
    '''
    ret = []
    cmd = 'netstat -tulpnea'
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        comps = line.split()
        if line.startswith('tcp'):
            ret.append({
                'inode': comps[7],
                'local-address': comps[3],
                'program': comps[8],
                'proto': comps[0],
                'recv-q': comps[1],
                'remote-address': comps[4],
                'send-q': comps[2],
                'state': comps[5],
                'user': comps[6]})
        if line.startswith('udp'):
            ret.append({
                'inode': comps[6],
                'local-address': comps[3],
                'program': comps[7],
                'proto': comps[0],
                'recv-q': comps[1],
                'remote-address': comps[4],
                'send-q': comps[2],
                'user': comps[5]})
    return ret


# FIXME: This is broken on: Modern traceroute for Linux, version 2.0.14, May 10 2010 (Ubuntu 10.10)
# FIXME: traceroute is deprecated, make this fall back to tracepath
def traceroute(host):
    '''
    Performs a traceroute to a 3rd party host

    CLI Example::

        salt '*' network.traceroute archlinux.org
    '''
    ret = []
    cmd = 'traceroute %s' % _sanitize_host(host)
    out = __salt__['cmd.run'](cmd)

    for line in out:
        if not ' ' in line:
            continue
        if line.startswith('traceroute'):
            continue
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


def dig(host):
    '''
    Performs a DNS lookup with dig

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

    out = __salt__['cmd.run']('ip addr show')
    groups = re.compile('\r?\n\d').split(out)

    for group in groups:
        iface = None
        data = {}
        for line in group.split('\n'):
            if not ' ' in line:
                continue
            m = re.match('^\d*:\s+(\w+)(?:@)?(\w+)?:\s+<(.+)>', line)
            if m:
                iface,parent,attrs = m.groups()
                if 'UP' in attrs.split(','):
                    data['up'] = True
                if parent:
                    data['parent'] = parent
            else:
                cols = line.split()
                if len(cols) >= 2:
                    type,value = tuple(cols[0:2])
                    if type in ('inet', 'inet6'):
                        def parse_network():
                            """
                            Return a tuple of ip, netmask, broadcast
                            based on the current set of cols
                            """
                            brd = None
                            ip,cidr = tuple(value.split('/'))
                            if type == 'inet':
                                mask = _cidr_to_ipv4_netmask(int(cidr))
                                if 'brd' in cols:
                                    brd = cols[cols.index('brd')+1]
                            elif type == 'inet6':
                                mask = cidr
                            return (ip, mask, brd)

                        if 'secondary' not in cols:
                            ipaddr, netmask, broadcast = parse_network()
                            if type == 'inet':
                                data['ipaddr'] = ipaddr
                                data['netmask'] = netmask
                                data['broadcast'] = broadcast
                            elif type == 'inet6':
                                data['ipaddr6'] = ipaddr
                                data['netmask6'] = netmask
                        else:
                            if 'secondary' not in data:
                                data['secondary'] = []
                            ip, mask, brd = parse_network()
                            data['secondary'].append({
                                'type': type,
                                'ipaddr': ip,
                                'netmask': mask,
                                'broadcast': brd
                                })
                            del ip, mask, brd
                    elif type.startswith('link'):
                        data['hwaddr'] = value
        if iface:
            ret[iface] = data
            del iface, data
    return ret


def up(interface):
    '''
    Returns True if interface is up, otherwise returns False

    CLI Example::

        salt '*' network.up eth0
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

        salt '*' network.ipaddr eth0
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

        salt '*' network.netmask eth0
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

        salt '*' network.hwaddr eth0
    '''
    data = interfaces().get(interface)
    if data:
        return data['hwaddr']
    else:
        return None

def host_to_ip(host):
    '''
    Returns the IP address of a given hostname
    
    CLI Example::
        
        salt '*' network.host_to_ip example.com
    '''
    try:
        ip = socket.gethostbyname( host )
    except:
        ip = None        
    return ip
        
def ip_to_host(ip):
    '''
    Returns the hostname of a given IP
    
    CLI Example::
        
        salt '*' network.ip_to_host example.com
    '''
    try:
        hostname, aliaslist, ipaddrlist = socket.gethostbyaddr( ip )
    except:
        hostname = None        
    return hostname
