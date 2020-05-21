# -*- coding: utf-8 -*-
"""
Module for getting information about network addresses.

.. versionadded:: 2016.3.0

:depends: netaddr
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.ext import six

__virtualname__ = "netaddress"

# Import third party libs
try:
    import netaddr

    HAS_NETADDR = True
except ImportError as e:
    HAS_NETADDR = False


def __virtual__():
    """
    Only load if netaddr library exist.
    """
    if not HAS_NETADDR:
        return (
            False,
            "The netaddress execution module cannot be loaded: "
            "netaddr python library is not installed.",
        )
    return __virtualname__


def list_cidr_ips(cidr):
    """
    Get a list of IP addresses from a CIDR.

    CLI example::

        salt myminion netaddress.list_cidr_ips 192.168.0.0/20
    """
    ips = netaddr.IPNetwork(cidr)
    return [six.text_type(ip) for ip in list(ips)]


def list_cidr_ips_ipv6(cidr):
    """
    Get a list of IPv6 addresses from a CIDR.

    CLI example::

        salt myminion netaddress.list_cidr_ips_ipv6 192.168.0.0/20
    """
    ips = netaddr.IPNetwork(cidr)
    return [six.text_type(ip.ipv6()) for ip in list(ips)]


def cidr_netmask(cidr):
    """
    Get the netmask address associated with a CIDR address.

    CLI example::

        salt myminion netaddress.cidr_netmask 192.168.0.0/20
    """
    ips = netaddr.IPNetwork(cidr)
    return six.text_type(ips.netmask)


def cidr_broadcast(cidr):
    """
    Get the broadcast address associated with a CIDR address.

    CLI example::

        salt myminion netaddress.cidr_netmask 192.168.0.0/20
    """
    ips = netaddr.IPNetwork(cidr)
    return six.text_type(ips.broadcast)
