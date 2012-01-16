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

        salt '*' network.ping archlinux.org -c 4
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
    out = __salt__['cmd.run'](cmd)
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


def _interfaces():
    '''
    Returns interface info
       
    '''
    ret = {}

    out = __salt__['cmd.run']('ip addr show')
    groups = re.compile('\r?\n\d').split(out)

    for group in groups:
        iface = None
        up = False
        for line in group.split('\n'):
            if not ' ' in line:
                continue
            m = re.match('^\d*:\s+(\w+):\s+<(.+)>', line)
            if m:
                iface,attrs = m.groups()
                if 'UP' in attrs.split(','):
                    up = True
                ipaddr = None
                netmask = None
                hwaddr = None
            else:
                cols = line.split()
                if len(cols) >= 2:
                    type,value = tuple(cols[0:2])
                    if type == 'inet':
                        ipaddr,cidr = tuple(value.split('/'))
                        netmask = _cidr_to_ipv4_netmask(int(cidr))
                    elif type.startswith('link'):
                        hwaddr = value

        if iface:
            ret[iface] = (up,ipaddr,netmask,hwaddr)
            del iface,up

    return ret


def up(interface):
    '''
    Returns True if interface is up, otherwise returns False

    CLI Example::

        salt '*' network.up eth0
    '''
    data = _interfaces().get(interface)
    if data:
        return data[0]
    else:
        return None

def ipaddr(interface):
    '''
    Returns the IP address for a given interface

    CLI Example::

        salt '*' network.ipaddr eth0
    '''
    data = _interfaces().get(interface)
    if data:
        return data[1]
    else:
        return None

def netmask(interface):
    '''
    Returns the netmask for a given interface

    CLI Example::

        salt '*' network.netmask eth0
    '''
    data = _interfaces().get(interface)
    if data:
        return data[2]
    else:
        return None

def hwaddr(interface):
    '''
    Returns the hwaddr for a given interface

    CLI Example::

        salt '*' network.hwaddr eth0
    '''
    data = _interfaces().get(interface)
    if data:
        return data[3]
    else:
        return None


