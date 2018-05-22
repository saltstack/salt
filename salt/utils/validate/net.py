# -*- coding: utf-8 -*-
'''
Various network validation utilities
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import re
import socket

# Import Salt libs
import salt.utils.platform

# Import 3rd-party libs
from salt.ext.six import string_types
if salt.utils.platform.is_windows():
    from salt.ext import win_inet_pton  # pylint: disable=unused-import


def mac(addr):
    '''
    Validates a mac address
    '''
    valid = re.compile(r'''
                      (^([0-9A-F]{1,2}[-]){5}([0-9A-F]{1,2})$
                      |^([0-9A-F]{1,2}[:]){5}([0-9A-F]{1,2})$
                      |^([0-9A-F]{1,2}[.]){5}([0-9A-F]{1,2})$)
                      ''',
                      re.VERBOSE | re.IGNORECASE)
    return valid.match(addr) is not None


def __ip_addr(addr, address_family=socket.AF_INET):
    '''
    Returns True if the IP address (and optional subnet) are valid, otherwise
    returns False.
    '''
    mask_max = '32'
    if address_family == socket.AF_INET6:
        mask_max = '128'

    try:
        if '/' not in addr:
            addr = '{addr}/{mask_max}'.format(addr=addr, mask_max=mask_max)
    except TypeError:
        return False

    ip, mask = addr.rsplit('/', 1)

    # Verify that IP address is valid
    try:
        socket.inet_pton(address_family, ip)
    except socket.error:
        return False

    # Verify that mask is valid
    try:
        mask = int(mask)
    except ValueError:
        return False
    else:
        if not 1 <= mask <= int(mask_max):
            return False

    return True


def ipv4_addr(addr):
    '''
    Returns True if the IPv4 address (and optional subnet) are valid, otherwise
    returns False.
    '''
    return __ip_addr(addr, socket.AF_INET)


def ipv6_addr(addr):
    '''
    Returns True if the IPv6 address (and optional subnet) are valid, otherwise
    returns False.
    '''
    return __ip_addr(addr, socket.AF_INET6)


def netmask(mask):
    '''
    Returns True if the value passed is a valid netmask, otherwise return False
    '''
    if not isinstance(mask, string_types):
        return False

    octets = mask.split('.')
    if not len(octets) == 4:
        return False

    return ipv4_addr(mask) and octets == sorted(octets, reverse=True)
