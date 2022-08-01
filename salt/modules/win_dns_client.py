"""
Module for configuring DNS Client on Windows systems
"""

import logging

import salt.utils.platform

try:
    import wmi

    import salt.utils.winapi

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_dns_client: module only works on Windows systems"
    if not HAS_LIBS:
        return False, "Module win_dns_client: missing required libraries"
    return "win_dns_client"


def get_dns_servers(interface="Local Area Connection"):
    """
    Return a list of the configured DNS servers of the specified interface

    Args:
        interface (str): The name of the network interface. This is the name as
        it appears in the Control Panel under Network Connections

    Returns:
        list: A list of dns servers

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_servers 'Local Area Connection'
    """
    # remove any escape characters
    interface = interface.split("\\")
    interface = "".join(interface)

    with salt.utils.winapi.Com():
        c = wmi.WMI()
        for iface in c.Win32_NetworkAdapter(NetEnabled=True):
            if interface == iface.NetConnectionID:
                iface_config = c.Win32_NetworkAdapterConfiguration(
                    Index=iface.Index
                ).pop()
                try:
                    return list(iface_config.DNSServerSearchOrder)
                except TypeError:
                    return []
    log.debug('Interface "%s" not found', interface)
    return False


def rm_dns(ip, interface="Local Area Connection"):
    """
    Remove the DNS server from the network interface

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.rm_dns <ip> <interface>
    """
    cmd = ["netsh", "interface", "ip", "delete", "dns", interface, ip, "validate=no"]
    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


def add_dns(ip, interface="Local Area Connection", index=1):
    """
    Add the DNS server to the network interface
    (index starts from 1)

    Note: if the interface DNS is configured by DHCP, all the DNS servers will
    be removed from the interface and the requested DNS will be the only one

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.add_dns <ip> <interface> <index>
    """
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

    cmd = [
        "netsh",
        "interface",
        "ip",
        "add",
        "dns",
        interface,
        ip,
        "index={}".format(index),
        "validate=no",
    ]

    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


def dns_dhcp(interface="Local Area Connection"):
    """
    Configure the interface to get its DNS servers from the DHCP server

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.dns_dhcp <interface>
    """
    cmd = ["netsh", "interface", "ip", "set", "dns", interface, "source=dhcp"]
    return __salt__["cmd.retcode"](cmd, python_shell=False) == 0


def get_dns_config(interface="Local Area Connection"):
    """
    Get the type of DNS configuration (dhcp / static).

    Args:
        interface (str): The name of the network interface. This is the
        Description in the Network Connection Details for the device

    Returns:
        bool: ``True`` if DNS is configured, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' win_dns_client.get_dns_config 'Local Area Connection'
    """
    # remove any escape characters
    interface = interface.split("\\")
    interface = "".join(interface)

    with salt.utils.winapi.Com():
        c = wmi.WMI()
        for iface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
            if interface == iface.Description:
                return iface.DHCPEnabled
