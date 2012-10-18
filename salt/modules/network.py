'''
Module for gathering and managing network information
'''
# Import Python libs
import sys
import logging

# Import Salt libs
from salt.utils.socket_util import sanitize_host

__outputter__ = {
    'dig':     'txt',
    'ping':    'txt',
    'netstat': 'txt',
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on Windows, a specific file module exists:
    if __grains__['os'] in ('Windows',):
        return False

    return 'network'


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
            netmask += '{0:d}'.format(256-(2**(8-cidr_bits)))
            cidr_bits = 0
    return netmask


def _number_of_set_bits_to_ipv4_netmask(set_bits):
    '''
    Returns an IPv4 netmask from the integer representation of that mask.

    Ex. 0xffffff00 -> '255.255.255.0'
    '''
    return _cidr_to_ipv4_netmask(_number_of_set_bits(set_bits))


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


def _interfaces_ip(out):
    '''
    Uses ip to return a dictionary of interfaces with various information about
    each (up/down state, ip address, netmask, and hwaddr)
    '''
    import re
    ret = dict()

    def parse_network(value, cols):
        '''
        Return a tuple of ip, netmask, broadcast
        based on the current set of cols
        '''
        brd = None
        if '/' in value:  # we have a CIDR in this address
            ip, cidr = value.split('/')
        else:
            ip = value
            cidr = 32

        if type == 'inet':
            mask = _cidr_to_ipv4_netmask(int(cidr))
            if 'brd' in cols:
                brd = cols[cols.index('brd')+1]
        elif type == 'inet6':
            mask = cidr
        return (ip, mask, brd)

    groups = re.compile('\r?\n\d').split(out)
    for group in groups:
        iface = None
        data = dict()

        for line in group.split('\n'):
            if not ' ' in line:
                continue
            m = re.match('^\d*:\s+([\w.]+)(?:@)?(\w+)?:\s+<(.+)>', line)
            if m:
                iface, parent, attrs = m.groups()
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
                        ip, mask, brd = parse_network(value, cols)
                        data['secondary'].append({
                            'type': type,
                            'address': ip,
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


def _interfaces_ifconfig(out):
    '''
    Uses ifconfig to return a dictionary of interfaces with various information
    about each (up/down state, ip address, netmask, and hwaddr)
    '''
    import re
    ret = dict()

    piface = re.compile('^(\S+):?')
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
        for line in group.split('\n'):
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

    CLI Example::

        salt '*' network.interfaces
    '''
    ifaces = dict()
    if __salt__['cmd.has_exec']('ip'):
        cmd = __salt__['cmd.run']('ip addr show')
        ifaces = _interfaces_ip(cmd)
    elif __salt__['cmd.has_exec']('ifconfig'):
        cmd = __salt__['cmd.run']('ifconfig -a')
        ifaces = _interfaces_ifconfig(cmd)
    return ifaces


def _get_net_start(ipaddr, netmask):
    ipaddr_octets = ipaddr.split('.')
    netmask_octets = netmask.split('.')
    net_start_octets = [str(int(ipaddr_octets[x]) & int(netmask_octets[x]))
                       for x in range(0, 4)]
    return '.'.join(net_start_octets)


def _get_net_size(mask):
    binary_str = ''
    for octet in mask.split('.'):
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip('0'))


def _calculate_subnet(ipaddr, netmask):
    return '{0}/{1}'.format(_get_net_start(ipaddr, netmask),
                            _get_net_size(netmask))


def _ipv4_to_bits(ipaddr):
    '''
    Accepts an IPv4 dotted quad and returns a string representing its binary
    counterpart
    '''
    return ''.join([bin(int(x))[2:].rjust(8, '0') for x in ipaddr.split('.')])


def subnets():
    '''
    Returns a list of subnets to which the host belongs
    '''
    ifaces = interfaces()
    subnets = []

    for ipv4_info in ifaces.values():
        for ipv4 in ipv4_info.get('inet', []):
            if ipv4['address'] == '127.0.0.1': continue
            network = _calculate_subnet(ipv4['address'], ipv4['netmask'])
            subnets.append(network)
    return subnets


def in_subnet(cidr):
    '''
    Returns True if host is within specified subnet, otherwise False
    '''
    try:
        netstart, netsize = cidr.split('/')
        netsize = int(netsize)
    except:
        log.error('Invalid CIDR \'{0}\''.format(cidr))
        return False

    netstart_bin = _ipv4_to_bits(netstart)

    if netsize < 32 and len(netstart_bin.rstrip('0')) > netsize:
        log.error('Invalid network starting IP \'{0}\' in CIDR '
                  '\'{1}\''.format(netstart, cidr))
        return False

    netstart_leftbits = netstart_bin[0:netsize]
    for ip_addr in ip_addrs():
        if netsize == 32:
            if netstart == ip_addr: return True
        else:
            ip_leftbits = _ipv4_to_bits(ip_addr)[0:netsize]
            if netstart_leftbits == ip_leftbits: return True

    return False


def ip_addrs(include_loopback=False):
    '''
    Returns a list of IPv4 addresses assigned to the host. (127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated)
    '''
    ret = []
    ifaces = interfaces()
    for ipv4_info in ifaces.values():
        for ipv4 in ipv4_info.get('inet',[]):
            if ipv4['address'] != '127.0.0.1': ret.append(ipv4['address'])
            else:
                if include_loopback: ret.append(ipv4['address'])
    return ret


def ip_addrs6(include_loopback=False):
    '''
    Returns a list of IPv6 addresses assigned to the host. (::1 is ignored,
    unless 'include_loopback=True' is indicated)
    '''
    ret = []
    ifaces = interfaces()
    for ipv6_info in ifaces.values():
        for ipv6 in ipv6_info.get('inet6',[]):
            if ipv6['address'] != '::1': ret.append(ipv6['address'])
            else:
                if include_loopback: ret.append(ipv6['address'])
    return ret


def ping(host):
    '''
    Performs a ping to a host

    CLI Example::

        salt '*' network.ping archlinux.org
    '''
    cmd = 'ping -c 4 {0}'.format(sanitize_host(host))
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
    cmd = 'traceroute {0}'.format(sanitize_host(host))
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
    cmd = 'dig {0}'.format(sanitize_host(host))
    return __salt__['cmd.run'](cmd)
