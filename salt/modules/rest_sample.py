# -*- coding: utf-8 -*-
'''
Module for interfacing to the REST example

pre-pre-ALPHA QUALITY code.

'''

# Import python libraries
import logging

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'rest_example'

__proxyenabled__ = ['rest_example']

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


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


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' rest_example.help

    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
