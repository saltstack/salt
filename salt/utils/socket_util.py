'''
Define some generic socket functions for network modules
'''

# Import python libs
import socket
import subprocess
import re
import logging
from string import ascii_letters, digits

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)

# pylint: disable-msg=C0103

def sanitize_host(host):
    '''
    Sanitize host string.
    '''
    return ''.join([
        c for c in host[0:255] if c in (ascii_letters + digits + '.-')
    ])


def isportopen(host, port):
    '''
    Return status of a port

    CLI Example::

        salt '*' network.isportopen 127.0.0.1 22
    '''

    if not (1 <= int(port) <= 65535):
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    out = sock.connect_ex((sanitize_host(host), int(port)))

    return out


def host_to_ip(host):
    '''
    Returns the IP address of a given hostname

    CLI Example::

        salt '*' network.host_to_ip example.com
    '''
    try:
        ip = socket.gethostbyname(host)
    except Exception:
        ip = None
    return ip


def ip_to_host(ip):
    '''
    Returns the hostname of a given IP

    CLI Example::

        salt '*' network.ip_to_host 8.8.8.8
    '''
    try:
        hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ip)
    except Exception:
        hostname = None
    return hostname

# pylint: enable-msg=C0103


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


def _number_of_set_bits_to_ipv4_netmask(set_bits):  # pylint: disable-msg=C0103
    '''
    Returns an IPv4 netmask from the integer representation of that mask.

    Ex. 0xffffff00 -> '255.255.255.0'
    '''
    return _cidr_to_ipv4_netmask(_number_of_set_bits(set_bits))


# pylint: disable-msg=C0103
def _number_of_set_bits(x):
    '''
    Returns the number of bits that are set in a 32bit int
    '''
    #Taken from http://stackoverflow.com/a/4912729. Many thanks!
    x -= (x >> 1) & 0x55555555
    x = ((x >> 2) & 0x33333333) + (x & 0x33333333)
    x = ((x >> 4) + x) & 0x0f0f0f0f
    x += x >> 8
    x += x >> 16
    return x & 0x0000003f

# pylint: enable-msg=C0103


def _interfaces_ip(out):
    '''
    Uses ip to return a dictionary of interfaces with various information about
    each (up/down state, ip address, netmask, and hwaddr)
    '''
    ret = dict()

    def parse_network(value, cols):
        '''
        Return a tuple of ip, netmask, broadcast
        based on the current set of cols
        '''
        brd = None
        if '/' in value:  # we have a CIDR in this address
            ip, cidr = value.split('/')  # pylint: disable-msg=C0103
        else:
            ip = value  # pylint: disable-msg=C0103
            cidr = 32

        if type == 'inet':
            mask = _cidr_to_ipv4_netmask(int(cidr))
            if 'brd' in cols:
                brd = cols[cols.index('brd') + 1]
        elif type == 'inet6':
            mask = cidr
        return (ip, mask, brd)

    groups = re.compile('\r?\n\d').split(out)
    for group in groups:
        iface = None
        data = dict()

        for line in group.splitlines():
            if not ' ' in line:
                continue
            match = re.match('^\d*:\s+([\w.]+)(?:@)?(\w+)?:\s+<(.+)>', line)
            if match:
                iface, parent, attrs = match.groups()
                if 'UP' in attrs.split(','):
                    data['up'] = True
                else:
                    data['up'] = False
                if parent:
                    data['parent'] = parent
                continue

            cols = line.split()
            if len(cols) >= 2:
                type, value = tuple(cols[0:2])
                iflabel = cols[-1:][0]
                if type in ('inet', 'inet6'):
                    if 'secondary' not in cols:
                        ipaddr, netmask, broadcast = parse_network(value, cols)
                        if type == 'inet':
                            if 'inet' not in data:
                                data['inet'] = list()
                            addr_obj = dict()
                            addr_obj['address'] = ipaddr
                            addr_obj['netmask'] = netmask
                            addr_obj['broadcast'] = broadcast
                            addr_obj['label'] = iflabel
                            data['inet'].append(addr_obj)
                        elif type == 'inet6':
                            if 'inet6' not in data:
                                data['inet6'] = list()
                            addr_obj = dict()
                            addr_obj['address'] = ipaddr
                            addr_obj['prefixlen'] = netmask
                            data['inet6'].append(addr_obj)
                    else:
                        if 'secondary' not in data:
                            data['secondary'] = list()
                        ip_, mask, brd = parse_network(value, cols)
                        data['secondary'].append({
                            'type': type,
                            'address': ip_,
                            'netmask': mask,
                            'broadcast': brd,
                            'label': iflabel,
                            })
                        del ip_, mask, brd
                elif type.startswith('link'):
                    data['hwaddr'] = value
        if iface:
            ret[iface] = data
            del iface, data
    return ret


def _interfaces_ifconfig(out):
    '''
    Uses ifconfig to return a dictionary of interfaces with various information
    about each (up/down state, ip address, netmask, and hwaddr)
    '''
    ret = dict()

    piface = re.compile('^([^\s:]+)')
    pmac = re.compile('.*?(?:HWaddr|ether) ([0-9a-fA-F:]+)')
    pip = re.compile('.*?(?:inet addr:|inet )(.*?)\s')
    pip6 = re.compile('.*?(?:inet6 addr: (.*?)/|inet6 )([0-9a-fA-F:]+)')
    pmask = re.compile('.*?(?:Mask:|netmask )(?:(0x[0-9a-fA-F]{8})|([\d\.]+))')
    pmask6 = re.compile('.*?(?:inet6 addr: [0-9a-fA-F:]+/(\d+)|prefixlen (\d+)).*')
    pupdown = re.compile('UP')
    pbcast = re.compile('.*?(?:Bcast:|broadcast )([\d\.]+)')

    groups = re.compile('\r?\n(?=\S)').split(out)
    for group in groups:
        data = dict()
        iface = ''
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
                data['hwaddr'] = mmac.group(1)
            if mip:
                if 'inet' not in data:
                    data['inet'] = list()
                addr_obj = dict()
                addr_obj['address'] = mip.group(1)
                mmask = pmask.match(line)
                if mmask:
                    if mmask.group(1):
                        mmask = _number_of_set_bits_to_ipv4_netmask(
                                int(mmask.group(1), 16))
                    else:
                        mmask = mmask.group(2)
                    addr_obj['netmask'] = mmask
                mbcast = pbcast.match(line)
                if mbcast:
                    addr_obj['broadcast'] = mbcast.group(1)
                data['inet'].append(addr_obj)
            if mupdown:
                updown = True
            if mip6:
                if 'inet6' not in data:
                    data['inet6'] = list()
                addr_obj = dict()
                addr_obj['address'] = mip6.group(1) or mip6.group(2)
                mmask6 = pmask6.match(line)
                if mmask6:
                    addr_obj['prefixlen'] = mmask6.group(1) or mmask6.group(2)
                data['inet6'].append(addr_obj)
        data['up'] = updown
        ret[iface] = data
        del data
    return ret


def interfaces():
    '''
    Return a dictionary of information about all the interfaces on the minion
    '''
    ifaces = dict()
    if salt.utils.which('ip'):
        cmd1 = subprocess.Popen(
                'ip link show',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).communicate()[0]
        cmd2 = subprocess.Popen(
                'ip addr show',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).communicate()[0]
        ifaces = _interfaces_ip(cmd1 + '\n' + cmd2)
    elif salt.utils.which('ifconfig'):
        cmd2 = subprocess.Popen(
                'ifconfig -a',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT).communicate()[0]
        ifaces = _interfaces_ifconfig(cmd)
    return ifaces


def ip4_addrs():
    '''
    Return a list of ip addrs
    '''
    ret = set()
    ifaces = interfaces()
    for face in ifaces:
        for inet in ifaces[face].get('inet', []):
            if 'address' in inet:
                ret.add(inet['address'])
    return sorted(ret)
