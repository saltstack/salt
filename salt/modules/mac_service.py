# -*- coding: utf-8 -*-
'''
The service module for FreeBSD
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError

__func_alias__ = {
    'reload_': 'reload'
}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only for Mac OS X
    '''
    if not salt.utils.is_darwin():
        return (False, 'Failed to load the mac_service module:\n'
                       'Only available on Mac OS X systems.')

    if not os.path.exists('/bin/launchctl'):
        return (False, 'Failed to load the mac_service module:\n'
                       'Required binary not found: "/bin/launchctl"')

    return __virtualname__


def list():
    cmd = ['launchctl', 'list']


def load(plist_path):
    cmd = ['launchctl', 'load', plist_path]
    return not __salt__['cmd.retcode'](cmd, python_shell=False)

