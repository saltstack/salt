# -*- coding: utf-8 -*-
'''
Various network validation utilities
'''

# Import python libs
import re
import socket

# Import salt libs
from salt._compat import string_types


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


def ipv4_addr(addr):
    '''
    Returns True if the IP address (and optional subnet) are valid, otherwise
    returns False.
    '''
    try:
        if '/' not in addr:
            addr += '/32'
    except TypeError:
        return False

    ip, subnet_len = addr.rsplit('/', 1)

    # Verify that IP address is valid
    try:
        socket.inet_aton(ip)
    except socket.error:
        return False
    else:
        if len(ip.split('.')) != 4:
            return False

    # Verify that subnet length is valid
    try:
        subnet_len = int(subnet_len)
    except ValueError:
        return False
    else:
        if not 1 <= subnet_len <= 32:
            return False

    return True


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
