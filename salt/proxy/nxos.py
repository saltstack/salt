from __future__ import absolute_import
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException

import logging
log = logging.getLogger(__file__)

__proxyenabled__ = ['nxos']
__virtualname__ = 'nxos'
DETAILS = {}
GRAINS_CACHE = {}


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('nxos proxy __virtual__() called...')

    return __virtualname__


def init(opts):
    '''
    Required.
    Can be used to initialize the server connection.
    '''
    try:
        DETAILS['server'] = SSHConnection(
            host=opts['proxy']['host'],
            username=opts['proxy']['username'],
            password=opts['proxy']['password'],
            ssh_args=opts['proxy']['ssh_args'],
            prompt='{0}.*#'.format(opts['proxy']['hostname']))
        out, err = DETAILS['server'].sendline('terminal length 0')

    except TerminalException as e:
        log.error(e)
        return False


def ping():
    '''
    Required.
    Ping the device on the other end of the connection
    '''
    try:
        out, err = DETAILS['server'].sendline('show ver')
        return True
    except TerminalException as e:
        log.error(e)
        return False


def shutdown(opts):
    '''
    Disconnect
    '''
    DETAILS['server'].close_connection()


def sendline(command):
    out, err = DETAILS['server'].sendline(command)
    return out


def grains():
    if not GRAINS_CACHE:
        return _grains()
    return GRAINS_CACHE


def grains_refresh():
    '''
    Refresh the grains from the proxy device.
    '''
    GRAINS_CACHE = {}
    return grains()


def _grains():
    ret = __salt__['nxos.system_info']()
    GRAINS_CACHE.update(ret)
    return GRAINS_CACHE
