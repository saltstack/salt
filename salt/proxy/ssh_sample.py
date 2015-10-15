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

# This must be present or the Salt loader won't load this module
__proxyenabled__ = ['ssh_sample']

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
    pass


def shutdown(opts):
    '''
    Required.
    Can be used to dispose the server connection.
    '''
    pass


def package_list():
    '''
    List "packages" by executing a command via ssh
    This function is called in response to the salt command

    ..code-block::bash
        salt target_minion pkg.list_pkgs

    '''
    # This method shows the full sequence from
    # initializing a connection, executing a command,
    # parsing the output and closing the connection.
    # In production these steps can (and probably should)
    # be in separate methods.

    # Create the server connection
    server = SSHConnection(host='salt',
                           username='salt',
                           password='password')

    # Send the command to execute
    out, err = server.sendline('pkg_list')

    # "scrape" the output and return the right fields as a dict
    return json.loads(out[9:-7])
