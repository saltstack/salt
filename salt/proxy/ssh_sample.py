# -*- coding: utf-8 -*-
'''
    This is a simple proxy-minion designed to connect to and communicate with
    a server that exposes functionality via SSH.
    This can be used as an option when the device does not provide
    an api over HTTP and doesn't have the python stack to run a minion.
'''
from __future__ import absolute_import

# Import python libs
import json
import logging

# Import Salt's libs
from salt.utils.vt_helper import SSHConnection
from salt.utils.vt import TerminalException

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ['ssh_sample']

DETAILS = {}

# Want logging!
log = logging.getLogger(__file__)


# This does nothing, it's here just as an example and to provide a log
# entry when the module is loaded.
def __virtual__():
    '''
    Only return if all the modules are available
    '''
    log.info('ssh_sample proxy __virtual__() called...')

    return True


def init(opts):
    '''
    Required.
    Can be used to initialize the server connection.
    '''
    try:
        DETAILS['server'] = SSHConnection(host=__opts__['proxy']['host'],
                                          username=__opts__['proxy']['username'],
                                          password=__opts__['proxy']['password'])
        out, err = DETAILS['server'].sendline('help')

    except TerminalException as e:
        log.error(e)
        return False
    pass


def shutdown(opts):
    '''
    Disconnect
    '''
    DETAILS['server'].close_connection()


def package_list():
    '''
    List "packages" by executing a command via ssh
    This function is called in response to the salt command

    ..code-block::bash
        salt target_minion pkg.list_pkgs

    '''

    # Send the command to execute
    out, err = DETAILS['server'].sendline('pkg_list')

    jsonret = []
    in_json = False
    # "scrape" the output and return the right fields as a dict
    for l in out.split():
        if '{' in l:
            in_json = True
        if in_json:
            jsonret.append(l)
        if '}' in l:
            in_json = False
    return json.loads('\n'.join(jsonret))
