# -*- coding: utf-8 -*-
'''
The networking module for Windows based systems
'''

# Import python libs
import logging
import socket

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'ip'


def __virtual__():
    '''
    Confine this module to Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def _interface_configs():
    '''
    Return all interface configs
    '''
    cmd = 'netsh interface ip show config'
    lines = __salt__['cmd.run'](cmd).splitlines()
    iface = ''
    ip = 0
    dns_flag = None
    wins_flag = None
    ret = {}
    for line in lines:
        if dns_flag:
            try:
                socket.inet_aton(line.strip())
                ret[iface][dns_flag].append(line.strip())
                dns_flag = None
                continue
            except socket.error as exc:
                dns_flag = None
        if wins_flag:
            try:
                socket.inet_aton(line.strip())
                ret[iface][wins_flag].append(line.strip())
                wins_flag = None
                continue
            except socket.error as exc:
                wins_flag = None
        if not line:
            iface = ''
            continue
        if 'Configuration for interface' in line:
            _, iface = line.rstrip('"').split('"', 1)  # get iface name
            ret[iface] = {}
            ip = 0
            continue
        try:
            key, val = line.split(':', 1)
        except ValueError as exc:
            log.debug('Could not split line. Error was {0}.'.format(exc))
            continue
        if 'DNS Servers' in line:
            dns_flag = key.strip()
            ret[iface][key.strip()] = [val.strip()]
            continue
        if 'WINS Servers' in line:
            wins_flag = key.strip()
            ret[iface][key.strip()] = [val.strip()]
            continue
        if 'IP Address' in key:
            if 'ip_addrs' not in ret[iface]:
                ret[iface]['ip_addrs'] = []
            ret[iface]['ip_addrs'].append(dict([(key.strip(), val.strip())]))
            continue
        if 'Subnet Prefix' in key:
            subnet, _, netmask = val.strip().split(' ', 2)
            ret[iface]['ip_addrs'][ip]['Subnet'] = subnet.strip()
            ret[iface]['ip_addrs'][ip]['Netmask'] = netmask.lstrip().rstrip(')')
            ip = ip + 1
            continue
        else:
            ret[iface][key.strip()] = val.strip()
    return ret


def raw_interface_configs():
    '''
    Return raw configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt '*' ip.raw_interface_configs
    '''
    cmd = 'netsh interface ip show config'
    return __salt__['cmd.run'](cmd)


def get_all_interfaces():
    '''
    Return configs for all interfaces

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_all_interfaces
    '''
    return _interface_configs()


def get_interface(iface):
    '''
    Return the configuration of a network interface

    CLI Example:

    .. code-block:: bash

        salt '*' ip.get_interface 'Local Area Connection'
    '''
    ifaces = _interface_configs()
    if iface in ifaces:
        return ifaces[iface]
    return False


def set_static_ip(iface, addr, netmask, gateway):
    '''
    Set static IP configuration on a Windows NIC

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_static_ip 'Local Area Connection' 192.168.1.5 255.255.255.0 192.168.1.1
    '''
    if not any((iface, addr, netmask, gateway)):
        return False
    cmd = 'netsh int ip set address "{0}" static {1} {2} {3} 1'.format(
            iface,
            addr,
            netmask,
            gateway,
            )
    __salt__['cmd.run'](cmd)
    return {'IP Address': addr, 'Netmask': netmask, 'Default Gateway': gateway}


def set_dhcp_ip(iface):
    '''
    Set Windows NIC to get IP from DHCP

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_dhcp_ip 'Local Area Connection'
    '''
    cmd = 'netsh interface ip set address "{0}" dhcp'.format(iface)
    __salt__['cmd.run'](cmd)
    return {'Interface': iface, 'DHCP enabled': 'Yes'}


def set_static_dns(iface, *addrs):
    '''
    Set static DNS configuration on a Windows NIC

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_static_dns 'Local Area Connection' '192.168.1.1'
        salt '*' ip.set_static_dns 'Local Area Connection' '192.168.1.252' '192.168.1.253'
    '''
    addr_index = 1
    for addr in addrs:
        if addr_index == 1:
            cmd = 'netsh int ip set dns "{0}" static {1} primary'.format(
                    iface,
                    addrs[0],
                    )
            __salt__['cmd.run'](cmd)
            addr_index = addr_index + 1
        else:
            cmd = 'netsh interface ip add dns name="{0}" addr="{1}" index={2}'
            __salt__['cmd.run'](cmd.format(iface, addr, addr_index))
            addr_index = addr_index + 1
    return {'Interface': iface, 'DNS Server': addrs}


def set_dhcp_dns(iface):
    '''
    Set DNS source to DHCP on Windows

    CLI Example:

    .. code-block:: bash

        salt '*' ip.set_dhcp_dns 'Local Area Connection'
    '''
    cmd = 'netsh interface ip set dns "{0}" dhcp'.format(iface)
    __salt__['cmd.run'](cmd)
    return {'Interface': iface, 'DNS Server': 'DHCP'}


def set_dhcp_all(iface):
    '''
    Set both IP Address and DNS to DHCP

    CLI Example:

    ..code-block:: bash

        salt '*' ip.set_dhcp_all 'Local Area Connection'
    '''
    set_dhcp_ip(iface)
    set_dhcp_dns(iface)
    return {'Interface': iface, 'DNS Server': 'DHCP', 'DHCP enabled': 'Yes'}
