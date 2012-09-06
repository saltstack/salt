'''
Define some default interface functions to be imported in multiple network
interface modules.
'''


def ipaddr(interface=None):
    '''
    Returns the IP address for a given interface

    CLI Example::

        salt '*' network.ipaddr eth0
    '''
    iflist = interfaces()
    out = None

    if interface:
        data = iflist.get(interface) or dict()
        if data.get('inet'):
            return data.get('inet')[0]['address']
        if data.get('inet6'):
            return data.get('inet6')[0]['address']
        return out

    out = dict()
    for iface, data in iflist.items():
        if data.get('inet'):
            out[iface] = data.get('inet')[0]['address']
            continue
        if data.get('inet6'):
            out[iface] = data.get('inet6')[0]['address']
            continue
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
