def ipaddr(interface=None):
    '''
    Returns the IP address for a given interface

    CLI Example::

        salt '*' network.ipaddr eth0
    '''
    iflist = interfaces()
    out = None

    if interface:
        data = iflist.get(interface)
        if data.get('inet'):
            if not out:
                out = list()
            out += data.get('inet')
        if data.get('inet6'):
            if not out:
                out = list()
            out += data.get('inet6')
        return out

    for iface, data in iflist.items():
        if data.get('inet'):
            if not out[iface]: out[iface] = list()
            out[iface] += data.get('inet')
        if data.get('inet6'):
            if not out[iface]: out[iface] = list()
            out[iface] += data.get('inet6')
    return out


def netmask(interface):
    '''
    Returns the netmask for a given interface

    CLI Example::

        salt '*' network.netmask eth0
    '''
    out = list()

    data = interfaces().get(interface)
    if data.get('inet'):
        for addrinfo in data.get('inet'):
            if addrinfo.get('netmask'):
                out.append(addrinfo['netmask'])
    if data.get('inet6'):
        # TODO: This should return the prefix for the address
        pass
    return out or None


def hwaddr(interface):
    '''
    Returns the hwaddr for a given interface

    CLI Example::

        salt '*' network.hwaddr eth0
    '''
    data = interfaces().get(interface) or {}
    return data.get('hwaddr')


def up(interface):
    '''
    Returns True if interface is up, otherwise returns False

    CLI Example::

        salt '*' network.up eth0
    '''
    data = interfaces().get(interface) or {}
    return data.get('up')
