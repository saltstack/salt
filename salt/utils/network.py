# -*- coding: utf-8 -*-
'''
Define some generic socket functions for network modules
'''

# Import python libs
from __future__ import absolute_import
import os
import re
import socket
import logging
from string import ascii_letters, digits

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
# Attempt to import wmi
try:
    import wmi
    import salt.utils.winapi
except ImportError:
    pass

# Import salt libs
import salt.utils
from salt._compat import subprocess, ipaddress

log = logging.getLogger(__name__)

# pylint: disable=C0103


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
    '''

    if not 1 <= int(port) <= 65535:
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    out = sock.connect_ex((sanitize_host(host), int(port)))

    return out


def host_to_ip(host):
    '''
    Returns the IP address of a given hostname
    '''
    try:
        family, socktype, proto, canonname, sockaddr = socket.getaddrinfo(
            host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM)[0]

        if family == socket.AF_INET:
            ip, port = sockaddr
        elif family == socket.AF_INET6:
            ip, port, flow_info, scope_id = sockaddr

    except Exception:
        ip = None
    return ip


def _filter_localhost_names(name_list):
    '''
    Returns list without local hostnames and ip addresses.
    '''
    h = []
    re_filters = [
        'localhost.*',
        'ip6-.*',
        '127.*',
        r'0\.0\.0\.0',
        '::1.*',
        'fe00::.*',
        'fe02::.*',
        '1.0.0.*.ip6.arpa',
    ]
    for name in name_list:
        filtered = False
        for f in re_filters:
            if re.match(f, name):
                filtered = True
                break
        if not filtered:
            h.append(name)
    return h


def _sort_hostnames(hostname_list):
    '''
    sort minion ids favoring in order of:
        - FQDN
        - public ipaddress
        - localhost alias
        - private ipaddress
    '''
    # punish matches in order of preference
    punish = [
        'localhost.localdomain',
        'localhost.my.domain',
        'localhost4.localdomain4',
        'localhost',
        'ip6-localhost',
        'ip6-loopback',
        'ipv6-localhost',
        'ipv6-loopback',
        '127.0.2.1',
        '127.0.1.1',
        '127.0.0.1',
        '0.0.0.0',
        '::1',
        'fe00::',
        'fe02::',
    ]

    def _key_hostname(e):
        # should never have a space in hostname
        # favor hostnames w/o spaces
        if ' ' in e:
            first = 1
        else:
            first = -1

        # punish localhost list
        if e in punish:
            second = punish.index(e)
        else:
            second = -1

        # punish ipv6
        third = e.count(':')

        # punish ipv4
        # punish ipv4 addresses that start with '127.' more
        e_is_ipv4 = e.count('.') == 3 and not any(c.isalpha() for c in e)
        if e_is_ipv4:
            if e.startswith('127.'):
                fourth = 1
            else:
                fourth = 0
        else:
            fourth = -1

        # favor hosts with more dots
        fifth = -(e.count('.'))

        # favor longest fqdn
        sixth = -(len(e))

        return (first, second, third, fourth, fifth, sixth)

    return sorted(hostname_list, key=_key_hostname)


def get_hostnames():
    '''
    Get list of hostnames using multiple strategies
    '''
    h = []
    h.append(socket.gethostname())
    h.append(socket.getfqdn())

    # try socket.getaddrinfo
    try:
        addrinfo = socket.getaddrinfo(
            socket.gethostname(), 0, socket.AF_UNSPEC, socket.SOCK_STREAM,
            socket.SOL_TCP, socket.AI_CANONNAME
        )
        for info in addrinfo:
            # info struct [family, socktype, proto, canonname, sockaddr]
            if len(info) >= 4:
                h.append(info[3])
    except socket.gaierror:
        pass

    # try /etc/hostname
    try:
        name = ''
        with salt.utils.fopen('/etc/hostname') as hfl:
            name = hfl.read()
        h.append(name)
    except (IOError, OSError):
        pass

    # try /etc/nodename (SunOS only)
    if salt.utils.is_sunos():
        try:
            name = ''
            with salt.utils.fopen('/etc/nodename') as hfl:
                name = hfl.read()
            h.append(name)
        except (IOError, OSError):
            pass

    # try /etc/hosts
    try:
        with salt.utils.fopen('/etc/hosts') as hfl:
            for line in hfl:
                names = line.split()
                try:
                    ip = names.pop(0)
                except IndexError:
                    continue
                if ip.startswith('127.') or ip == '::1':
                    for name in names:
                        h.append(name)
    except (IOError, OSError):
        pass

    # try windows hosts
    if salt.utils.is_windows():
        try:
            windir = os.getenv('WINDIR')
            with salt.utils.fopen(windir + r'\system32\drivers\etc\hosts') as hfl:
                for line in hfl:
                    # skip commented or blank lines
                    if line[0] == '#' or len(line) <= 1:
                        continue
                    # process lines looking for '127.' in first column
                    try:
                        entry = line.split()
                        if entry[0].startswith('127.'):
                            for name in entry[1:]:  # try each name in the row
                                h.append(name)
                    except IndexError:
                        pass  # could not split line (malformed entry?)
        except (IOError, OSError):
            pass

    # strip spaces and ignore empty strings
    hosts = []
    for name in h:
        name = name.strip()
        if len(name) > 0:
            hosts.append(name)

    # remove duplicates
    hosts = list(set(hosts))
    return hosts


def generate_minion_id():
    '''
    Returns a minion id after checking multiple sources for a FQDN.
    If no FQDN is found you may get an ip address
    '''
    possible_ids = get_hostnames()

    # include public and private ipaddresses
    for addr in salt.utils.network.ip_addrs():
        addr = ipaddress.ip_address(addr)
        if addr.is_loopback:
            continue
        possible_ids.append(str(addr))

    possible_ids = _filter_localhost_names(possible_ids)

    # if no minion id
    if len(possible_ids) == 0:
        return 'noname'

    hosts = _sort_hostnames(possible_ids)
    return hosts[0]


def get_socket(addr, type=socket.SOCK_STREAM, proto=0):
    '''
    Return a socket object for the addr
    IP-version agnostic
    '''

    version = ipaddress.ip_address(addr).version
    if version == 4:
        family = socket.AF_INET
    elif version == 6:
        family = socket.AF_INET6
    return socket.socket(family, type, proto)


def get_fqhostname():
    '''
    Returns the fully qualified hostname
    '''
    l = []
    l.append(socket.getfqdn())

    # try socket.getaddrinfo
    try:
        addrinfo = socket.getaddrinfo(
            socket.gethostname(), 0, socket.AF_UNSPEC, socket.SOCK_STREAM,
            socket.SOL_TCP, socket.AI_CANONNAME
        )
        for info in addrinfo:
            # info struct [family, socktype, proto, canonname, sockaddr]
            if len(info) >= 4:
                l.append(info[3])
    except socket.gaierror:
        pass

    l = _sort_hostnames(l)
    if len(l) > 0:
        return l[0]

    return None


def ip_to_host(ip):
    '''
    Returns the hostname of a given IP
    '''
    try:
        hostname, aliaslist, ipaddrlist = socket.gethostbyaddr(ip)
    except Exception:
        hostname = None
    return hostname

# pylint: enable=C0103


def _validate_ip(af, ip):
    '''
    Common logic for IPv4
    '''
    if af == socket.AF_INET6 and not socket.has_ipv6:
        raise RuntimeError('IPv6 not supported')
    try:
        socket.inet_pton(af, ip)
    except AttributeError:
        if af == socket.AF_INET6:
            raise RuntimeError('socket.inet_pton not available')
        try:
            socket.inet_aton(ip)
        except socket.error:
            return False
    except (socket.error, TypeError):
        return False
    return True


def is_ip(ip):
    '''
    Returns a bool telling if the passed IP is a valid IPv4 or IPv6 address.

    Will raise a RuntimeError if IPv6 is not supported on the host.
    '''
    for af in (socket.AF_INET, socket.AF_INET6):
        if _validate_ip(af, ip):
            return True
    return False


def is_ipv4(ip):
    '''
    Returns a bool telling if the value passed to it was a valid IPv4 address
    '''
    return _validate_ip(socket.AF_INET, ip)


def is_ipv6(ip):
    '''
    Returns a bool telling if the value passed to it was a valid IPv6 address

    Will raise a RuntimeError if IPv6 is not supported on the host.
    '''
    return _validate_ip(socket.AF_INET6, ip)


def cidr_to_ipv4_netmask(cidr_bits):
    '''
    Returns an IPv4 netmask
    '''
    try:
        cidr_bits = int(cidr_bits)
        if not 1 <= cidr_bits <= 32:
            return ''
    except ValueError:
        return ''

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


def _number_of_set_bits_to_ipv4_netmask(set_bits):  # pylint: disable=C0103
    '''
    Returns an IPv4 netmask from the integer representation of that mask.

    Ex. 0xffffff00 -> '255.255.255.0'
    '''
    return cidr_to_ipv4_netmask(_number_of_set_bits(set_bits))


# pylint: disable=C0103
def _number_of_set_bits(x):
    '''
    Returns the number of bits that are set in a 32bit int
    '''
    # Taken from http://stackoverflow.com/a/4912729. Many thanks!
    x -= (x >> 1) & 0x55555555
    x = ((x >> 2) & 0x33333333) + (x & 0x33333333)
    x = ((x >> 4) + x) & 0x0f0f0f0f
    x += x >> 8
    x += x >> 16
    return x & 0x0000003f

# pylint: enable=C0103


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
        scope = None
        if '/' in value:  # we have a CIDR in this address
            ip, cidr = value.split('/')  # pylint: disable=C0103
        else:
            ip = value  # pylint: disable=C0103
            cidr = 32

        if type_ == 'inet':
            mask = cidr_to_ipv4_netmask(int(cidr))
            if 'brd' in cols:
                brd = cols[cols.index('brd') + 1]
        elif type_ == 'inet6':
            mask = cidr
            if 'scope' in cols:
                scope = cols[cols.index('scope') + 1]
        return (ip, mask, brd, scope)

    groups = re.compile('\r?\n\\d').split(out)
    for group in groups:
        iface = None
        data = dict()

        for line in group.splitlines():
            if ' ' not in line:
                continue
            match = re.match(r'^\d*:\s+([\w.\-]+)(?:@)?([\w.\-]+)?:\s+<(.+)>', line)
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
                        ipaddr, netmask, broadcast, scope = parse_network(value, cols)
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
                            addr_obj['scope'] = scope
                            data['inet6'].append(addr_obj)
                    else:
                        if 'secondary' not in data:
                            data['secondary'] = list()
                        ip_, mask, brd, scp = parse_network(value, cols)
                        data['secondary'].append({
                            'type': type_,
                            'address': ip_,
                            'netmask': mask,
                            'broadcast': brd,
                            'label': iflabel,
                        })
                        del ip_, mask, brd, scp
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
    if salt.utils.is_sunos():
        pip = re.compile(r'.*?(?:inet\s+)([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)(.*)')
        pip6 = re.compile('.*?(?:inet6 )([0-9a-fA-F:]+)')
        pmask6 = re.compile(r'.*?(?:inet6 [0-9a-fA-F:]+/(\d+)).*')
    else:
        pip = re.compile(r'.*?(?:inet addr:|inet [^\d]*)(.*?)\s')
        pip6 = re.compile('.*?(?:inet6 addr: (.*?)/|inet6 )([0-9a-fA-F:]+)')
        pmask6 = re.compile(r'.*?(?:inet6 addr: [0-9a-fA-F:]+/(\d+)|prefixlen (\d+))(?: Scope:([a-zA-Z]+)| scopeid (0x[0-9a-fA-F]))?')
    pmask = re.compile(r'.*?(?:Mask:|netmask )(?:((?:0x)?[0-9a-fA-F]{8})|([\d\.]+))')
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
                if salt.utils.is_sunos():
                    expand_mac = []
                    for chunk in data['hwaddr'].split(':'):
                        expand_mac.append('0{0}'.format(chunk) if len(chunk) < 2 else '{0}'.format(chunk))
                    data['hwaddr'] = ':'.join(expand_mac)
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
                    if not salt.utils.is_sunos():
                        ipv6scope = mmask6.group(3) or mmask6.group(4)
                        addr_obj['scope'] = ipv6scope.lower() if ipv6scope is not None else ipv6scope
                if addr_obj['address'] != '::' and addr_obj['prefixlen'] != 0:  # SunOS sometimes has ::/0 as inet6 addr when using addrconf
                    data['inet6'].append(addr_obj)
        data['up'] = updown
        if iface in ret:
            # SunOS optimization, where interfaces occur twice in 'ifconfig -a'
            # output with the same name: for ipv4 and then for ipv6 addr family.
            # Every instance has it's own 'UP' status and we assume that ipv4
            # status determines global interface status.
            #
            # merge items with higher priority for older values
            # after that merge the inet and inet6 sub items for both
            ret[iface] = dict(list(data.items()) + list(ret[iface].items()))
            if 'inet' in data:
                ret[iface]['inet'].extend(x for x in data['inet'] if x not in ret[iface]['inet'])
            if 'inet6' in data:
                ret[iface]['inet6'].extend(x for x in data['inet6'] if x not in ret[iface]['inet6'])
        else:
            ret[iface] = data
        del data
    return ret


def linux_interfaces():
    '''
    Obtain interface information for *NIX/BSD variants
    '''
    ifaces = dict()
    ip_path = salt.utils.which('ip')
    ifconfig_path = None if ip_path else salt.utils.which('ifconfig')
    if ip_path:
        cmd1 = subprocess.Popen(
            '{0} link show'.format(ip_path),
            shell=True,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
        cmd2 = subprocess.Popen(
            '{0} addr show'.format(ip_path),
            shell=True,
            close_fds=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
        ifaces = _interfaces_ip("{0}\n{1}".format(
            salt.utils.to_str(cmd1),
            salt.utils.to_str(cmd2)))
    elif ifconfig_path:
        cmd = subprocess.Popen(
            '{0} -a'.format(ifconfig_path),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT).communicate()[0]
        ifaces = _interfaces_ifconfig(salt.utils.to_str(cmd))
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
            if addr and key == 'Subnet Mask':
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
            elif key == 'Physical Address':
                iface['hwaddr'] = val
            elif key == 'Media State':
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
                for ip in iface.IPAddress:
                    if '.' in ip:
                        if 'inet' not in ifaces[iface.Description]:
                            ifaces[iface.Description]['inet'] = []
                        item = {'address': ip,
                                'label': iface.Description}
                        if iface.DefaultIPGateway:
                            broadcast = next((i for i in iface.DefaultIPGateway if '.' in i), '')
                            if broadcast:
                                item['broadcast'] = broadcast
                        if iface.IPSubnet:
                            netmask = next((i for i in iface.IPSubnet if '.' in i), '')
                            if netmask:
                                item['netmask'] = netmask
                        ifaces[iface.Description]['inet'].append(item)
                    if ':' in ip:
                        if 'inet6' not in ifaces[iface.Description]:
                            ifaces[iface.Description]['inet6'] = []
                        item = {'address': ip}
                        if iface.DefaultIPGateway:
                            broadcast = next((i for i in iface.DefaultIPGateway if ':' in i), '')
                            if broadcast:
                                item['broadcast'] = broadcast
                        if iface.IPSubnet:
                            netmask = next((i for i in iface.IPSubnet if ':' in i), '')
                            if netmask:
                                item['netmask'] = netmask
                        ifaces[iface.Description]['inet6'].append(item)
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


def get_net_start(ipaddr, netmask):
    '''
    Return the address of the network
    '''
    net = ipaddress.ip_network('{0}/{1}'.format(ipaddr, netmask), strict=False)
    return str(net.network_address)


def get_net_size(mask):
    '''
    Turns an IPv4 netmask into it's corresponding prefix length
    (255.255.255.0 -> 24 as in 192.168.1.10/24).
    '''
    binary_str = ''
    for octet in mask.split('.'):
        binary_str += bin(int(octet))[2:].zfill(8)
    return len(binary_str.rstrip('0'))


def calc_net(ipaddr, netmask=None):
    '''
    Takes IP (CIDR notation supported) and optionally netmask
    and returns the network in CIDR-notation.
    (The IP can be any IP inside the subnet)
    '''
    if netmask is not None:
        ipaddr = '{0}/{1}'.format(ipaddr, netmask)

    return str(ipaddress.ip_network(ipaddr, strict=False))


def _ipv4_to_bits(ipaddr):
    '''
    Accepts an IPv4 dotted quad and returns a string representing its binary
    counterpart
    '''
    return ''.join([bin(int(x))[2:].rjust(8, '0') for x in ipaddr.split('.')])


def _get_iface_info(iface):
    '''
    If `iface` is available, return interface info and no error, otherwise
    return no info and log and return an error
    '''
    iface_info = interfaces()

    if iface in iface_info.keys():
        return iface_info, False
    else:
        error_msg = ('Interface "{0}" not in available interfaces: "{1}"'
                     ''.format(iface, '", "'.join(iface_info.keys())))
        log.error(error_msg)
        return None, error_msg


def hw_addr(iface):
    '''
    Return the hardware address (a.k.a. MAC address) for a given interface
    '''
    iface_info, error = _get_iface_info(iface)

    if error is False:
        return iface_info.get(iface, {}).get('hwaddr', '')
    else:
        return error


def interface(iface):
    '''
    Return the details of `iface` or an error if it does not exist
    '''
    iface_info, error = _get_iface_info(iface)

    if error is False:
        return iface_info.get(iface, {}).get('inet', '')
    else:
        return error


def interface_ip(iface):
    '''
    Return `iface` IPv4 addr or an error if `iface` does not exist
    '''
    iface_info, error = _get_iface_info(iface)

    if error is False:
        return iface_info.get(iface, {}).get('inet', {})[0].get('address', '')
    else:
        return error


def _subnets(proto='inet', interfaces_=None):
    '''
    Returns a list of subnets to which the host belongs
    '''
    if interfaces_ is None:
        ifaces = interfaces()
    elif isinstance(interfaces_, list):
        ifaces = {}
        for key, value in six.iteritems(interfaces()):
            if key in interfaces_:
                ifaces[key] = value
    else:
        ifaces = {interfaces_: interfaces().get(interfaces_, {})}

    ret = set()

    if proto == 'inet':
        subnet = 'netmask'
    elif proto == 'inet6':
        subnet = 'prefixlen'
    else:
        log.error('Invalid proto {0} calling subnets()'.format(proto))
        return

    for ip_info in six.itervalues(ifaces):
        addrs = ip_info.get(proto, [])
        addrs.extend([addr for addr in ip_info.get('secondary', []) if addr.get('type') == proto])

        for intf in addrs:
            intf = ipaddress.ip_interface('{0}/{1}'.format(intf['address'], intf[subnet]))
            if not intf.is_loopback:
                ret.add(intf.network)
    return [str(net) for net in sorted(ret)]


def subnets(interfaces=None):
    '''
    Returns a list of IPv4 subnets to which the host belongs
    '''
    return _subnets('inet', interfaces_=interfaces)


def subnets6():
    '''
    Returns a list of IPv6 subnets to which the host belongs
    '''
    return _subnets('inet6')


def in_subnet(cidr, addr=None):
    '''
    Returns True if host or (any of) addrs is within specified subnet, otherwise False
    '''
    try:
        cidr = ipaddress.ip_network(cidr)
    except ValueError:
        log.error('Invalid CIDR \'{0}\''.format(cidr))
        return False

    if addr is None:
        addr = ip_addrs()
        addr.extend(ip_addrs6())
    elif isinstance(addr, six.string_types):
        return ipaddress.ip_address(addr) in cidr

    for ip_addr in addr:
        if ipaddress.ip_address(ip_addr) in cidr:
            return True
    return False


def ip_in_subnet(addr, cidr):
    '''
    Returns True if given IP is within specified subnet, otherwise False

    .. deprecated:: Carbon
       Use :py:func:`~salt.utils.network.in_subnet` instead
    '''
    salt.utils.warn_until(
        'Carbon',
        'Support for \'ip_in_subnet\' has been deprecated and will be removed '
        'in Salt Carbon. Please use \'in_subnet\' instead.'
    )

    return in_subnet(cidr, addr)


def _ip_addrs(interface=None, include_loopback=False, interface_data=None, proto='inet'):
    '''
    Return the full list of IP adresses matching the criteria

    proto = inet|inet6
    '''
    ret = set()

    ifaces = interface_data \
        if isinstance(interface_data, dict) \
        else interfaces()
    if interface is None:
        target_ifaces = ifaces
    else:
        target_ifaces = dict([(k, v) for k, v in six.iteritems(ifaces)
                              if k == interface])
        if not target_ifaces:
            log.error('Interface {0} not found.'.format(interface))
    for ip_info in six.itervalues(target_ifaces):
        addrs = ip_info.get(proto, [])
        addrs.extend([addr for addr in ip_info.get('secondary', []) if addr.get('type') == proto])

        for addr in addrs:
            addr = ipaddress.ip_address(addr.get('address'))
            if not addr.is_loopback or include_loopback:
                ret.add(addr)
    return [str(addr) for addr in sorted(ret)]


def ip_addrs(interface=None, include_loopback=False, interface_data=None):
    '''
    Returns a list of IPv4 addresses assigned to the host. 127.0.0.1 is
    ignored, unless 'include_loopback=True' is indicated. If 'interface' is
    provided, then only IP addresses from that interface will be returned.
    '''
    return _ip_addrs(interface, include_loopback, interface_data, 'inet')


def ip_addrs6(interface=None, include_loopback=False, interface_data=None):
    '''
    Returns a list of IPv6 addresses assigned to the host. ::1 is ignored,
    unless 'include_loopback=True' is indicated. If 'interface' is provided,
    then only IP addresses from that interface will be returned.
    '''
    return _ip_addrs(interface, include_loopback, interface_data, 'inet6')


def hex2ip(hex_ip, invert=False):
    '''
    Convert a hex string to an ip, if a failure occurs the original hex is
    returned. If 'invert=True' assume that ip from /proc/net/<proto>
    '''
    if len(hex_ip) == 32:  # ipv6
        ip = []
        for i in range(0, 32, 8):
            ip_part = hex_ip[i:i + 8]
            ip_part = [ip_part[x:x + 2] for x in range(0, 8, 2)]
            if invert:
                ip.append("{0[3]}{0[2]}:{0[1]}{0[0]}".format(ip_part))
            else:
                ip.append("{0[0]}{0[1]}:{0[2]}{0[3]}".format(ip_part))
        try:
            return ipaddress.IPv6Address(":".join(ip)).compressed
        except ipaddress.AddressValueError as ex:
            log.error('hex2ip - ipv6 address error: {0}'.format(ex))
            return hex_ip

    try:
        hip = int(hex_ip, 16)
    except ValueError:
        return hex_ip
    if invert:
        return '{3}.{2}.{1}.{0}'.format(hip >> 24 & 255,
                                        hip >> 16 & 255,
                                        hip >> 8 & 255,
                                        hip & 255)
    return '{0}.{1}.{2}.{3}'.format(hip >> 24 & 255,
                                    hip >> 16 & 255,
                                    hip >> 8 & 255,
                                    hip & 255)


def mac2eui64(mac, prefix=None):
    '''
    Convert a MAC address to a EUI64 identifier
    or, with prefix provided, a full IPv6 address
    '''
    # http://tools.ietf.org/html/rfc4291#section-2.5.1
    eui64 = re.sub(r'[.:-]', '', mac).lower()
    eui64 = eui64[0:6] + 'fffe' + eui64[6:]
    eui64 = hex(int(eui64[0:2], 16) | 2)[2:].zfill(2) + eui64[2:]

    if prefix is None:
        return ':'.join(re.findall(r'.{4}', eui64))
    else:
        try:
            net = ipaddress.ip_network(prefix, strict=False)
            euil = int('0x{0}'.format(eui64), 16)
            return '{0}/{1}'.format(net[euil], net.prefixlen)
        except:  # pylint: disable=bare-except
            return


def active_tcp():
    '''
    Return a dict describing all active tcp connections as quickly as possible
    '''
    ret = {}
    for statf in ['/proc/net/tcp', '/proc/net/tcp6']:
        if os.path.isfile(statf):
            with salt.utils.fopen(statf, 'rb') as fp_:
                for line in fp_:
                    if line.strip().startswith('sl'):
                        continue
                    ret.update(_parse_tcp_line(line))
    return ret


def local_port_tcp(port):
    '''
    Return a set of remote ip addrs attached to the specified local port
    '''
    ret = _remotes_on(port, 'local_port')
    return ret


def remote_port_tcp(port):
    '''
    Return a set of ip addrs the current host is connected to on given port
    '''
    ret = _remotes_on(port, 'remote_port')
    return ret


def _remotes_on(port, which_end):
    '''
    Return a set of ip addrs active tcp connections
    '''
    port = int(port)
    ret = set()

    proc_available = False
    for statf in ['/proc/net/tcp', '/proc/net/tcp6']:
        if os.path.isfile(statf):
            proc_available = True
            with salt.utils.fopen(statf, 'rb') as fp_:
                for line in fp_:
                    if line.strip().startswith('sl'):
                        continue
                    iret = _parse_tcp_line(line)
                    sl = next(iter(iret))
                    if iret[sl][which_end] == port:
                        ret.add(iret[sl]['remote_addr'])

    if not proc_available:  # Fallback to use OS specific tools
        if salt.utils.is_sunos():
            return _sunos_remotes_on(port, which_end)
        if salt.utils.is_freebsd():
            return _freebsd_remotes_on(port, which_end)
        if salt.utils.is_netbsd():
            return _netbsd_remotes_on(port, which_end)
        if salt.utils.is_openbsd():
            return _openbsd_remotes_on(port, which_end)
        if salt.utils.is_windows():
            return _windows_remotes_on(port, which_end)

        return _linux_remotes_on(port, which_end)

    return ret


def _parse_tcp_line(line):
    '''
    Parse a single line from the contents of /proc/net/tcp or /proc/net/tcp6
    '''
    ret = {}
    comps = line.strip().split()
    sl = comps[0].rstrip(':')
    ret[sl] = {}
    l_addr, l_port = comps[1].split(':')
    r_addr, r_port = comps[2].split(':')
    ret[sl]['local_addr'] = hex2ip(l_addr, True)
    ret[sl]['local_port'] = int(l_port, 16)
    ret[sl]['remote_addr'] = hex2ip(r_addr, True)
    ret[sl]['remote_port'] = int(r_port, 16)
    return ret


def _sunos_remotes_on(port, which_end):
    '''
    SunOS specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    [root@salt-master ~]# netstat -f inet -n
    TCP: IPv4
       Local Address        Remote Address    Swind Send-Q Rwind Recv-Q    State
       -------------------- -------------------- ----- ------ ----- ------ -----------
       10.0.0.101.4505      10.0.0.1.45329       1064800      0 1055864      0 ESTABLISHED
       10.0.0.101.4505      10.0.0.100.50798     1064800      0 1055864      0 ESTABLISHED
    '''
    remotes = set()
    try:
        data = subprocess.check_output(['netstat', '-f', 'inet', '-n'])  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error('Failed netstat')
        raise

    lines = salt.utils.to_str(data).split('\n')
    for line in lines:
        if 'ESTABLISHED' not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[0].rsplit('.', 1)
        remote_host, remote_port = chunks[1].rsplit('.', 1)

        if which_end == 'remote_port' and int(remote_port) != port:
            continue
        if which_end == 'local_port' and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _freebsd_remotes_on(port, which_end):
    '''
    Returns set of ipv4 host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'sockstat' (FreeBSD)
    to get connections

    $ sudo sockstat -4
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1456    29  tcp4   *:4505           *:*
    root    python2.7   1445    17  tcp4   *:4506           *:*
    root    python2.7   1294    14  tcp4   127.0.0.1:11813  127.0.0.1:4505
    root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506

    $ sudo sockstat -4 -c -p 4506
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1294    41  tcp4   127.0.0.1:61115  127.0.0.1:4506
    '''

    port = int(port)
    remotes = set()

    try:
        cmd = salt.utils.shlex_split('sockstat -4 -c -p {0}'.format(port))
        data = subprocess.check_output(cmd)  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError as ex:
        log.error('Failed "sockstat" with returncode = {0}'.format(ex.returncode))
        raise

    lines = salt.utils.to_str(data).split('\n')

    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['root', 'python2.7', '1456', '37', 'tcp4',
        #  '127.0.0.1:4505-', '127.0.0.1:55703']
        # print chunks
        if 'COMMAND' in chunks[1]:
            continue  # ignore header
        if len(chunks) < 2:
            continue
        local = chunks[5]
        remote = chunks[6]
        lhost, lport = local.split(':')
        rhost, rport = remote.split(':')
        if which_end == 'local' and int(lport) != port:  # ignore if local port not port
            continue
        if which_end == 'remote' and int(rport) != port:  # ignore if remote port not port
            continue

        remotes.add(rhost)

    return remotes


def _netbsd_remotes_on(port, which_end):
    '''
    Returns set of ipv4 host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'sockstat' (NetBSD)
    to get connections

    $ sudo sockstat -4
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1456    29  tcp4   *.4505           *.*
    root    python2.7   1445    17  tcp4   *.4506           *.*
    root    python2.7   1294    14  tcp4   127.0.0.1.11813  127.0.0.1.4505
    root    python2.7   1294    41  tcp4   127.0.0.1.61115  127.0.0.1.4506

    $ sudo sockstat -4 -c -p 4506
    USER    COMMAND     PID     FD  PROTO  LOCAL ADDRESS    FOREIGN ADDRESS
    root    python2.7   1294    41  tcp4   127.0.0.1.61115  127.0.0.1.4506
    '''

    port = int(port)
    remotes = set()

    try:
        cmd = salt.utils.shlex_split('sockstat -4 -c -p {0}'.format(port))
        data = subprocess.check_output(cmd)  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError as ex:
        log.error('Failed "sockstat" with returncode = {0}'.format(ex.returncode))
        raise

    lines = salt.utils.to_str(data).split('\n')

    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['root', 'python2.7', '1456', '37', 'tcp4',
        #  '127.0.0.1.4505-', '127.0.0.1.55703']
        # print chunks
        if 'COMMAND' in chunks[1]:
            continue  # ignore header
        if len(chunks) < 2:
            continue
        local = chunks[5].split('.')
        lport = local.pop()
        lhost = '.'.join(local)
        remote = chunks[6].split('.')
        rport = remote.pop()
        rhost = '.'.join(remote)
        if which_end == 'local' and int(lport) != port:  # ignore if local port not port
            continue
        if which_end == 'remote' and int(rport) != port:  # ignore if remote port not port
            continue

        remotes.add(rhost)

    return remotes


def _openbsd_remotes_on(port, which_end):
    '''
    OpenBSD specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    $ netstat -nf inet
    Active Internet connections
    Proto   Recv-Q Send-Q  Local Address          Foreign Address        (state)
    tcp          0      0  10.0.0.101.4505        10.0.0.1.45329         ESTABLISHED
    tcp          0      0  10.0.0.101.4505        10.0.0.100.50798       ESTABLISHED
    '''
    remotes = set()
    try:
        data = subprocess.check_output(['netstat', '-nf', 'inet'])  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error('Failed netstat')
        raise

    lines = data.split('\n')
    for line in lines:
        if 'ESTABLISHED' not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[3].rsplit('.', 1)
        remote_host, remote_port = chunks[4].rsplit('.', 1)

        if which_end == 'remote_port' and int(remote_port) != port:
            continue
        if which_end == 'local_port' and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _windows_remotes_on(port, which_end):
    r'''
    Windows specific helper function.
    Returns set of ipv4 host addresses of remote established connections
    on local or remote tcp port.

    Parses output of shell 'netstat' to get connections

    C:\>netstat -n

    Active Connections

       Proto  Local Address          Foreign Address        State
       TCP    10.2.33.17:3007        130.164.12.233:10123   ESTABLISHED
       TCP    10.2.33.17:3389        130.164.30.5:10378     ESTABLISHED
    '''
    remotes = set()
    try:
        data = subprocess.check_output(['netstat', '-n'])  # pylint: disable=minimum-python-version
    except subprocess.CalledProcessError:
        log.error('Failed netstat')
        raise

    lines = salt.utils.to_str(data).split('\n')
    for line in lines:
        if 'ESTABLISHED' not in line:
            continue
        chunks = line.split()
        local_host, local_port = chunks[1].rsplit(':', 1)
        remote_host, remote_port = chunks[2].rsplit(':', 1)
        if which_end == 'remote_port' and int(remote_port) != port:
            continue
        if which_end == 'local_port' and int(local_port) != port:
            continue
        remotes.add(remote_host)
    return remotes


def _linux_remotes_on(port, which_end):
    '''
    Linux specific helper function.
    Returns set of ip host addresses of remote established connections
    on local tcp port port.

    Parses output of shell 'lsof'
    to get connections

    $ sudo lsof -iTCP:4505 -n
    COMMAND   PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
    Python   9971 root   35u  IPv4 0x18a8464a29ca329d      0t0  TCP *:4505 (LISTEN)
    Python   9971 root   37u  IPv4 0x18a8464a29b2b29d      0t0  TCP 127.0.0.1:4505->127.0.0.1:55703 (ESTABLISHED)
    Python  10152 root   22u  IPv4 0x18a8464a29c8cab5      0t0  TCP 127.0.0.1:55703->127.0.0.1:4505 (ESTABLISHED)
    Python  10153 root   22u  IPv4 0x18a8464a29c8cab5      0t0  TCP [fe80::249a]:4505->[fe80::150]:59367 (ESTABLISHED)

    '''
    remotes = set()

    try:
        data = subprocess.check_output(
            ['lsof', '-iTCP:{0:d}'.format(port), '-n', '-P']  # pylint: disable=minimum-python-version
        )
    except subprocess.CalledProcessError as ex:
        if ex.returncode == 1:
            # Lsof return 1 if any error was detected, including the failure
            # to locate Internet addresses, and it is not an error in this case.
            log.warning('"lsof" returncode = 1, likely no active TCP sessions.')
            return remotes
        log.error('Failed "lsof" with returncode = {0}'.format(ex.returncode))
        raise

    lines = salt.utils.to_str(data).split('\n')
    for line in lines:
        chunks = line.split()
        if not chunks:
            continue
        # ['Python', '9971', 'root', '37u', 'IPv4', '0x18a8464a29b2b29d', '0t0',
        # 'TCP', '127.0.0.1:4505->127.0.0.1:55703', '(ESTABLISHED)']
        # print chunks
        if 'COMMAND' in chunks[0]:
            continue  # ignore header
        if 'ESTABLISHED' not in chunks[-1]:
            continue  # ignore if not ESTABLISHED
        # '127.0.0.1:4505->127.0.0.1:55703'
        local, remote = chunks[8].split('->')
        _, lport = local.rsplit(':', 1)
        rhost, rport = remote.rsplit(':', 1)
        if which_end == 'remote_port' and int(rport) != port:
            continue
        if which_end == 'local_port' and int(lport) != port:
            continue
        remotes.add(rhost.strip("[]"))

    return remotes
