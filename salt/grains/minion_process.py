# -*- coding: utf-8 -*-
'''
Set grains describing the minion process.
'''

from __future__ import absolute_import, print_function, unicode_literals

import os

# Import salt libs
import salt.utils.platform

try:
    import pwd
except ImportError:
    import getpass
    pwd = None

try:
    import grp
except ImportError:
    grp = None


def _uid():
    '''
    Grain for the minion User ID
    '''
    if salt.utils.platform.is_windows():
        return None
    return os.getuid()


def _username():
    '''
    Grain for the minion username
    '''
    if pwd:
        username = pwd.getpwuid(os.getuid()).pw_name
    else:
        username = getpass.getuser()

    return username


def _gid():
    '''
    Grain for the minion Group ID
    '''
    if salt.utils.platform.is_windows():
        return None
    return os.getgid()


def _groupname():
    '''
    Grain for the minion groupname
    '''
    if grp:
        groupname = grp.getgrgid(os.getgid()).gr_name
    else:
        groupname = ''

    return groupname


def _pid():
    return os.getpid()


def grains():
    ret = {
        'username': _username(),
        'groupname': _groupname(),
        'pid': _pid(),
    }

    if not salt.utils.platform.is_windows():
        ret['gid'] = _gid()
        ret['uid'] = _uid()

    return ret
