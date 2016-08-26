# -*- coding: utf-8 -*-
'''
Salt module to manage Unix cryptsetup jobs and the crypttab file
'''

# Import python libraries
from __future__ import absolute_import
import logging

# Import salt libraries
import salt

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'cryptdev'

def __virtual__():
    '''
    Only load on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return (False, 'The cryptdev module cannot be loaded: not a POSIX-like system')
    else:
        return True
