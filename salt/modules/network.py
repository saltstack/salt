'''
Module for gathering and managing network information
'''

# Import python libs
import re
import logging

# Import salt libs
import salt.utils.socket_util


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
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


def interfaces():
    '''
    Return a dictionary of information about all the interfaces on the minion

    CLI Example::

        salt '*' network.interfaces
    '''
    return salt.utils.socket_util.interfaces()

def hwaddr(iface):
    '''
    Return the hardware address (a.k.a. MAC address) for a given interface

    CLI Example::

        salt '*' network.hwaddr eth0
    '''
    return interfaces().get(iface, {}).get('hwaddr', '')


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

    CLI Example::

        salt '*' network.subnets
    '''
    ifaces = interfaces()
    subnets = []

    for ipv4_info in ifaces.values():
        for ipv4 in ipv4_info.get('inet', []):
            if ipv4['address'] == '127.0.0.1':
                continue
            network = _calculate_subnet(ipv4['address'], ipv4['netmask'])
            subnets.append(network)
    return subnets


def in_subnet(cidr):
    '''
    Returns True if host is within specified subnet, otherwise False

    CLI Example::

        salt '*' network.in_subnet 10.0.0.0/16
    '''
    try:
        netstart, netsize = cidr.split('/')
        netsize = int(netsize)
    except Exception:
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
            if netstart == ip_addr:
                return True
        else:
            ip_leftbits = _ipv4_to_bits(ip_addr)[0:netsize]
            if netstart_leftbits == ip_leftbits:
                return True
    return False


def ip_addrs(interface=None, include_loopback=False):
    '''
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.

    CLI Example::

        salt '*' network.ip_addrs
    '''
    ret = []
    ifaces = interfaces()
    if interface is None:
        target_ifaces = ifaces
    else:
        target_ifaces = dict([(k, v) for k, v in ifaces.iteritems()
                              if k == interface])
        if not target_ifaces:
            log.error('Interface {0} not found.'.format(interface))
    for ipv4_info in target_ifaces.values():
        for ipv4 in ipv4_info.get('inet', []):
            if include_loopback \
            or (not include_loopback and ipv4['address'] != '127.0.0.1'):
                ret.append(ipv4['address'])
    return ret


def ip_addrs6(interface=None, include_loopback=False):
    '''
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.

    CLI Example::

        salt '*' network.ip_addrs6
    '''
    ret = []
    ifaces = interfaces()
    if interface is None:
        target_ifaces = ifaces
    else:
        target_ifaces = dict([(k, v) for k, v in ifaces.iteritems()
                              if k == interface])
        if not target_ifaces:
            log.error('Interface {0} not found.'.format(interface))
    for ipv6_info in target_ifaces.values():
        for ipv6 in ipv6_info.get('inet6', []):
            if include_loopback \
            or (not include_loopback and ipv6['address'] != '::1'):
                ret.append(ipv6['address'])
    return ret


def ping(host):
    '''
    Performs a ping to a host

    CLI Example::

        salt '*' network.ping archlinux.org
    '''
    cmd = 'ping -c 4 {0}'.format(salt.utils.socket_util.sanitize_host(host))
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
    out = __salt__['cmd.run'](cmd).splitlines()
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


def traceroute(host):
    '''
    Performs a traceroute to a 3rd party host

    CLI Example::

        salt '*' network.traceroute archlinux.org
    '''
    ret = []
    cmd = 'traceroute {0}'.format(salt.utils.socket_util.sanitize_host(host))
    out = __salt__['cmd.run'](cmd)
    
    # Parse version of traceroute
    cmd2 = 'traceroute --version'
    out2 = __salt__['cmd.run'](cmd2)
    traceroute_version = re.findall(r'version (\d+)\.(\d+)\.(\d+)', out2)[0]

    for line in out.splitlines():
        if not ' ' in line:
            continue
        if line.startswith('traceroute'):
            continue

        if (traceroute_version[0] >= 2 and traceroute_version[2] >= 14
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


def dig(host):
    '''
    Performs a DNS lookup with dig

    CLI Example::

        salt '*' network.dig archlinux.org
    '''
    cmd = 'dig {0}'.format(salt.utils.socket_util.sanitize_host(host))
    return __salt__['cmd.run'](cmd)

def arp():
    '''
    Return the arp table from the minion

    CLI Example::

        salt '*' '*' network.arp
    '''
    ret = {}
    out = __salt__['cmd.run']('arp -an')
    for line in out.splitlines():
        comps = line.split()
        if len(comps) < 4:
            continue
        ret[comps[3]] = comps[1].strip('(').strip(')')
    return ret
