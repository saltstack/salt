# -*- coding: utf-8 -*-
'''
Module for configuring DNS Client on Windows systems
'''

# Import python libs
import re

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return 'win_dns_client'
    return False


def get_dns_servers(interface='Local Area Connection'):
    '''
    Return a list of the configured DNS servers of the specific interface

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_servers <interface>
    '''
    out = __salt__['cmd.run'](
            'netsh interface ip show dns "{0}"'.format(interface))
    return re.findall(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out)


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

        salt '*' win_dns_client.get_dns_config <interface>
    '''
    out = __salt__['cmd.run'](
            'netsh interface ip show dns "{0}"'.format(interface)
            )
    if re.search('DNS servers configured through DHCP', out):
        return 'dhcp'
    else:
        return 'static'
