# -*- coding: utf-8 -*-
'''
Manage snap packages via Salt

:depends: snapd for distribution

'''

from __future__ import absolute_import, print_function, unicode_literals
import os
import subprocess

import salt.utils.path

SNAP_BINARY_NAME='snap'

__virtualname__ = 'snap'

def __virtual__():
    if salt.utils.path.which('snap'):
        return __virtualname__

    return (False, 'The snap execution module cannot be loaded: the "snap" binary is not in the path.')

def install(pkg, channel=None):
    args = []
    if type(channel) is str:
        args += '--channel'
        args += channel
    retcode = subprocess.call([SNAP_BINARY_NAME, 'install', pkg] + args)
    return retcode == 0

def is_installed(pkg):
    # snap returns 0 if there is at least one match, otherwise 1
    retcode = subprocess.call([SNAP_BINARY_NAME, 'list', pkg])
    return retcode == 0

def remove(pkg):
    retcode = subprocess.call([SNAP_BINARY_NAME, 'remove', pkg])
    return retcode == 0

def versions_installed(pkg):
    try:
        output = subprocess.check_output([SNAP_BINARY_NAME, 'list', pkg])
    except subprocess.CalledProcessError:
        return []

    lines = output.splitlines()[1:]
    versions = [ item.split()[1] for item in lines ]
    return versions
