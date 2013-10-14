# -*- coding: utf-8 -*-
'''
Various network validation utilities
'''

import re

def mac(mac):
    '''
    Validates a mac address
    '''
    valid = re.compile(r'''
                      (^([0-9A-F]{1,2}[-]){5}([0-9A-F]{1,2})$
                      |^([0-9A-F]{1,2}[:]){5}([0-9A-F]{1,2})$)
                      ''',
                      re.VERBOSE|re.IGNORECASE)
    if valid.match(mac) is None:
            return False
    return True
