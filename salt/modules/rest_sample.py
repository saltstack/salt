# -*- coding: utf-8 -*-
'''
Module for interfacing to the REST example

pre-pre-ALPHA QUALITY code.

'''

# Import python libraries
import re
import logging

# Salt libraries
import salt.roster


# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'rest_example'

__proxyenabled__ = ['rest_example']


def __virtual__():
    '''
    '''
    if 'proxyobject' in __opts__:
        return __virtualname__
    else:
        return False


def grains_refresh():
    '''
    Refresh the cache.
    '''

    return __opts__['proxyobject'].grains_refresh()


def ping():

    ret = dict()
    conn = __opts__['proxyobject']
    if conn.ping():
        ret['message'] = 'pong'
        ret['out'] = True
    else:
        ret['out'] = False
