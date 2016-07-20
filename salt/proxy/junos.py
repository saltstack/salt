# -*- coding: utf-8 -*-
'''
Interface with a Junos device via proxy-minion.
'''

# Import python libs
from __future__ import absolute_import
from __future__ import print_function
import logging
import json

# Import 3rd-party libs
try:
    HAS_JUNOS = True
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.utils.config
except ImportError:
    HAS_JUNOS = False

__proxyenabled__ = ['junos']

thisproxy = {}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_JUNOS:
        return False, 'Missing dependency: The junos proxy minion requires the \'jnpr\' Python module.'

    return __virtualname__


def init(opts):
    '''
    Open the connection to the Junos device, login, and bind to the
    Resource class
    '''
    log.debug('Opening connection to junos')
    thisproxy['conn'] = jnpr.junos.Device(user=opts['proxy']['username'],
                                            host=opts['proxy']['host'],
                                            password=opts['proxy']['passwd'])
    thisproxy['conn'].open()
    thisproxy['conn'].bind(cu=jnpr.junos.utils.config.Config)


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
