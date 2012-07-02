'''
Module for gathering network interface information
'''

def _ip(out):
    '''
    Uses ip to return a dictionary of interfaces with various information about
    each (up/down state, ip address, netmask, and hwaddr)
    '''
    import re
    ret = dict()

    def parse_network(value, cols):
        """
        Return a tuple of ip, netmask, broadcast
        based on the current set of cols
        """
        brd = None
        if '/' in value:  # we have a CIDR in this address
            ip, cidr = value.split('/')
        else:
            ip = value
            cidr = 32

        if type == 'inet':
            mask = cidr
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
                iface,parent,attrs = m.groups()
                if 'UP' in attrs.split(','):
                    data['up'] = True
                else:
                    data['up'] = False
                if parent:
                    data['parent'] = parent
                continue

            cols = line.split()
            if len(cols) >= 2:
                type,value = tuple(cols[0:2])
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


def _ifconfig(out):
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
                        mmask = int(mmask.group(1), 16)
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


def _ipconfig(out):
    '''
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)
    '''
    import re
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
            k, v = line.split(',', 1)
            key = k.strip(' .')
            val = v.strip()
            if addr and key in ('Subnet Mask'):
                addr['netmask'] = val
            elif key in ('IP Address', 'IPv4 Address'):
                if 'inet' not in iface:
                    iface['inet'] = list()
                addr = {'address': val.rstrip('(Preferred)'),
                        'netmask': None,
                        'broadcast': None} # TODO find the broadcast
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
                iface['up'] = (v != 'Media disconnected')


def _interfaces_ethtool(ifaces):
    # parse offloading
    '''
    ethtool -k eth0
    Offload parameters for eth0:
    rx-checksumming: on
    tx-checksumming: on
    scatter-gather: on
    tcp-segmentation-offload: on
    udp-fragmentation-offload: off
    generic-segmentation-offload: on
    generic-receive-offload: on
    large-receive-offload: off
    rx-vlan-offload: on
    tx-vlan-offload: on
    ntuple-filters: off
    receive-hashing: off


    Different output for 10gige cards as well, with indents and []-notation

    tx-checksumming: on
            tx-checksum-ipv4: on
            tx-checksum-ip-generic: off [fixed]
            ...
    scatter-gather: on
    '''
    return ifaces


def _netifaces():
    import netifaces
    ifaces = dict()
    for ifname in netifaces.interfaces():
        iface = ifaces[ifname] = dict()
        for net in netifaces.ifaddresses(iface):
            if net is netifaces.AF_INET:
                if 'inet' not in iface:
                    iface['inet'] = list()
                iface['inet'].append(net)
            elif net is netifaces.AF_INET6:
                if 'inet6' not in iface:
                    iface['inet6'] = list()
                iface['inet6'].append(net)
            elif net is netifaces.AF_LINK:
                iface['hwaddr'] = net['addr']
            else:
                continue
    return ifaces


def interfaces():
    '''
    Returns a dictionary of interfaces with various information about each
    (up/down state, ip address, netmask, and hwaddr)

    CLI Example::

        salt '*' network.interfaces
    '''
    ifaces = dict()
    # find out which utility to use to gather interface information
    try:
        ifaces = _netifaces()
    except ImportError:
        pass

    if __salt__['cmd.has_exec']('ip'):
        cmd = __salt__['cmd.run']('ip addr show')
        ifaces = _ip(cmd)
    elif __salt__['cmd.has_exec']('ifconfig'):
        cmd = __salt__['cmd.run']('ifconfig -a')
        ifaces = _ifconfig(cmd)
    elif __salt__['cmd.has_exec']('ipconfig'):
        cmd = __salt__['cmd.run']('ipconfig /all')
        ifaces = _ifconfig(cmd)

    # Linux exposes device info through ethtool
    if __salt__['cmd.has_exec']('ethtool'):
        ifaces = _ethtool(ifaces)
    return ifaces


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


#XXX Broken
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


#XXX Broken
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
