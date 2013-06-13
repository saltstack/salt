'''
Define some generic socket functions for network modules
'''

# Import python libs
import socket
import subprocess
import re
import logging
from string import ascii_letters, digits

# Attempt to import wmi
try:
    import wmi
    import salt.utils.winapi
except ImportError:
    pass

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

        if type_ == 'inet':
            mask = _cidr_to_ipv4_netmask(int(cidr))
            if 'brd' in cols:
                brd = cols[cols.index('brd') + 1]
        elif type_ == 'inet6':
            mask = cidr
        return (ip, mask, brd)

    groups = re.compile('\r?\n\\d').split(out)
    for group in groups:
        iface = None
        data = dict()

        for line in group.splitlines():
            if not ' ' in line:
                continue
            match = re.match(r'^\d*:\s+([\w.]+)(?:@)?(\w+)?:\s+<(.+)>', line)
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
                type_, value = tuple(cols[0:2])
                iflabel = cols[-1:][0]
                if type_ in ('inet', 'inet6'):
                    if 'secondary' not in cols:
                        ipaddr, netmask, broadcast = parse_network(value, cols)
                        if type_ == 'inet':
                            if 'inet' not in data:
                                data['inet'] = list()
                            addr_obj = dict()
                            addr_obj['address'] = ipaddr
                            addr_obj['netmask'] = netmask
                            addr_obj['broadcast'] = broadcast
                            addr_obj['label'] = iflabel
                            data['inet'].append(addr_obj)
                        elif type_ == 'inet6':
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
                            'type': type_,
                            'address': ip_,
                            'netmask': mask,
                            'broadcast': brd,
                            'label': iflabel,
                        })
                        del ip_, mask, brd
                elif type_.startswith('link'):
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

    piface = re.compile(r'^([^\s:]+)')
    pmac = re.compile('.*?(?:HWaddr|ether|address:|lladdr) ([0-9a-fA-F:]+)')
    pip = re.compile(r'.*?(?:inet addr:|inet )(.*?)\s')
    pip6 = re.compile('.*?(?:inet6 addr: (.*?)/|inet6 )([0-9a-fA-F:]+)')
    pmask = re.compile(r'.*?(?:Mask:|netmask )(?:((?:0x)?[0-9a-fA-F]{8})|([\d\.]+))')
    pmask6 = re.compile(r'.*?(?:inet6 addr: [0-9a-fA-F:]+/(\d+)|prefixlen (\d+)).*')
    pupdown = re.compile('UP')
    pbcast = re.compile(r'.*?(?:Bcast:|broadcast )([\d\.]+)')

    groups = re.compile('\r?\n(?=\\S)').split(out)
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


def linux_interfaces():
    '''
    Obtain interface information for *NIX/BSD variants
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
        cmd = subprocess.Popen(
            'ifconfig -a',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
        ifaces = _interfaces_ifconfig(cmd)
    return ifaces


def _interfaces_ipconfig(out):
    '''
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)

    NOTE: This is not used by any function and may be able to be removed in the
    future.
    '''
    ifaces = dict()
    iface = None
    adapter_iface_regex = re.compile(r'adapter (\S.+):$')

    for line in out.splitlines():
        if not line:
            continue
        # TODO what does Windows call Infiniband and 10/40gige adapters
        if line.startswith('Ethernet'):
            iface = ifaces[adapter_iface_regex.search(line).group(1)]
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


def win_interfaces():
    '''
    Obtain interface information for Windows systems
    '''
    with salt.utils.winapi.Com():
        c = wmi.WMI()
        ifaces = {}
        for iface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            ifaces[iface.Description] = dict()
            if iface.MACAddress:
                ifaces[iface.Description]['hwaddr'] = iface.MACAddress
            if iface.IPEnabled:
                ifaces[iface.Description]['up'] = True
                ifaces[iface.Description]['inet'] = []
                for ip in iface.IPAddress:
                    item = {}
                    item['broadcast'] = ''
                    try:
                        item['broadcast'] = iface.DefaultIPGateway[0]
                    except Exception:
                        pass
                    item['netmask'] = iface.IPSubnet[0]
                    item['label'] = iface.Description
                    item['address'] = ip
                    ifaces[iface.Description]['inet'].append(item)
            else:
                ifaces[iface.Description]['up'] = False
    return ifaces


def interfaces():
    '''
    Return a dictionary of information about all the interfaces on the minion
    '''
    if salt.utils.is_windows():
        return win_interfaces()
    else:
        return linux_interfaces()


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


def hwaddr(iface):
    '''
    Return the hardware address (a.k.a. MAC address) for a given interface
    '''
    return interfaces().get(iface, {}).get('hwaddr', '')


def subnets():
    '''
    Returns a list of subnets to which the host belongs
    '''
    ifaces = interfaces()
    subnetworks = []

    for ipv4_info in ifaces.values():
        for ipv4 in ipv4_info.get('inet', []):
            if ipv4['address'] == '127.0.0.1':
                continue
            network = _calculate_subnet(ipv4['address'], ipv4['netmask'])
            subnetworks.append(network)
    return subnetworks


def in_subnet(cidr, addrs=None):
    '''
    Returns True if host is within specified subnet, otherwise False
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

    if addrs is None:
        addrs = ip_addrs()

    for ip_addr in addrs:
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
                    or (not include_loopback
                        and ipv4['address'] != '127.0.0.1'):
                ret.append(ipv4['address'])
    return ret


def ip_addrs6(interface=None, include_loopback=False):
    '''
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.
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


def hex2ip(hex_ip):
    '''
    Convert a hex string to an ip, if a failure occurs the original hex is
    returned
    '''
    try:
        hip = int(hex_ip, 16)
    except ValueError:
        return hex_ip
    return '{0}.{1}.{2}.{3}'.format(hip >> 24 & 255,
                                    hip >> 16 & 255,
                                    hip >> 8 & 255,
                                    hip & 255)


class IPv4Address(object):
    '''
    A very minimal subset of the IPv4Address object in the ip_address module.
    '''

    def __init__(self, address_str):
        self.address_str = address_str
        octets = self.address_str.split('.')
        if len(octets) != 4:
            raise ValueError(
                'IPv4 addresses must be in dotted-quad form.'
            )
        try:
            self.dotted_quad = [int(octet) for octet in octets]
        except ValueError as err:
            raise ValueError(
                'IPv4 addresses must be in dotted-quad form. {0}'.format(err)
            )

    def __str__(self):
        return self.address_str

    def __repr__(self):
        return 'IPv4Address("{0}")'.format(str(self))

    def __cmp__(self, other):
        return cmp(self.dotted_quad, other.dotted_quad)

    @property
    def is_private(self):
        '''
        :return: Returns True if the address is a non-routable IPv4 address.
                 Otherwise False.
        '''
        if 10 == self.dotted_quad[0]:
            return True
        if 172 == self.dotted_quad[0]:
            return 16 <= self.dotted_quad[1] <= 31
        if 192 == self.dotted_quad[0]:
            return 168 == self.dotted_quad[1]
        return False

    @property
    def is_loopback(self):
        '''
        :return: True if the address is a loopback address. Otherwise False.
        '''
        return 127 == self.dotted_quad[0]
