# -*- coding: utf-8 -*-
'''
Various network validation utilities
'''

# Import python libs
import re


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
