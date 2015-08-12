# -*- coding: utf-8 -*-
'''
Interface with a Junos device via proxy-minion.
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import

import logging

# Import 3rd-party libs
# import jnpr.junos
# import jnpr.junos.utils
# import jnpr.junos.utils.config
import json
HAS_JUNOS = True

__proxyenabled__ = ['junos']

thisproxy = {}

log = logging.getLogger(__name__)

# def __init__(opts):
#     '''
#     Open the connection to the Junos device, login, and bind to the
#     Resource class
#     '''
#     log.debug('Opening connection to junos')
#     thisproxy['conn'] = jnpr.junos.Device(user=opts['proxy']['username'],
#                                             host=opts['proxy']['host'],
#                                             password=opts['proxy']['passwd'])
#     thisproxy['conn'].open()
#     thisproxy['conn'].bind(cu=jnpr.junos.utils.config.Config)


def conn():
    return thisproxy['conn']


def facts():
    return thisproxy['conn'].facts


def refresh():
    return thisproxy['conn'].facts_refresh()


def proxytype():
    '''
    Returns the name of this proxy
    '''
    return 'junos'


def id(opts):
    '''
    Returns a unique ID for this proxy minion
    '''
    return thisproxy['conn'].facts['hostname']


def ping():
    '''
    Ping?  Pong!
    '''
    return thisproxy['conn'].connected


def shutdown(opts):
    '''
    This is called when the proxy-minion is exiting to make sure the
    connection to the device is closed cleanly.
    '''

    log.debug('Proxy module {0} shutting down!!'.format(opts['id']))
    try:
        thisproxy['conn'].close()
    except Exception:
        pass


def rpc():
    return json.dumps(thisproxy['conn'].rpc.get_software_information())
