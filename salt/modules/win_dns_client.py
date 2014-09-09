# -*- coding: utf-8 -*-
'''
Module for configuring DNS Client on Windows systems
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
try:
    import wmi
except ImportError:
    pass

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return 'win_dns_client'
    return False


def get_dns_servers(interface='Local Area Connection'):
    '''
    Return a list of the configured DNS servers of the specified interface

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_servers 'Local Area Connection'
    '''
    # remove any escape characters
    interface = interface.split('\\')
    interface = ''.join(interface)

    with salt.utils.winapi.Com():
        c = wmi.WMI()
        for iface in c.Win32_NetworkAdapter(NetEnabled=True):
            if interface == iface.NetConnectionID:
                iface_config = c.Win32_NetworkAdapterConfiguration(Index=iface.Index).pop()
                return list(iface_config.DNSServerSearchOrder)
    log.debug('Interface "{0}" not found'.format(interface))
    return False


def rm_dns(ip, interface='Local Area Connection'):
    '''
    Remove the DNS server to the network interface

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.rm_dns <interface>
    '''
    return __salt__['cmd.retcode'](
            'netsh interface ip delete dns "{0}" {1} validate=no'.format(
                interface, ip)
            ) == 0


def add_dns(ip, interface='Local Area Connection', index=1):
    '''
    Add the DNS server to the network interface
    (index starts from 1)

    Note: if the interface DNS is configured by DHCP, all the DNS servers will
    be removed from the interface and the requested DNS will be the only one

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.add_dns <interface> <index>
    '''
    servers = get_dns_servers(interface)

    # Return False if could not find the interface
    if servers is False:
        return False

    # Return true if configured
    try:
        if servers[index - 1] == ip:
            return True
    except IndexError:
        pass

    # If configured in the wrong order delete it
    if ip in servers:
        rm_dns(ip, interface)
    cmd = 'netsh interface ip add dns "{0}" {1} index={2} validate=no'.format(
        interface, ip, index
        )

    retcode = __salt__['cmd.retcode'](cmd)
    return retcode == 0


def dns_dhcp(interface='Local Area Connection'):
    '''
    Configure the interface to get its DNS servers from the DHCP server

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.dns_dhcp <interface>
    '''
    return __salt__['cmd.retcode'](
            'netsh interface ip set dns "{0}" source=dhcp'.format(interface)
            ) == 0


def get_dns_config(interface='Local Area Connection'):
    '''
    Get the type of DNS configuration (dhcp / static)

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_config 'Local Area Connection'
    '''
    # remove any escape characters
    interface = interface.split('\\')
    interface = ''.join(interface)

    with salt.utils.winapi.Com():
        c = wmi.WMI()
        for iface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            if interface == iface.Description:
                return iface.DHCPEnabled
