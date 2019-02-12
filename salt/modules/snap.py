# -*- coding: utf-8 -*-
'''
Manage snap packages via Salt

:depends: snapd for distribution

'''

from __future__ import absolute_import, print_function, unicode_literals
import subprocess

import salt.utils.path

SNAP_BINARY_NAME = 'snap'

__virtualname__ = 'snap'


def __virtual__():
    if salt.utils.path.which('snap'):
        return __virtualname__

    return (False, 'The snap execution module cannot be loaded: the "snap" binary is not in the path.')


def install(pkg, channel=None, refresh=False):
    args = []
    ret = {'result': None, 'output': ""}

    if refresh:
        cmd = 'refresh'
    else:
        cmd = 'install'

    if channel:
        args.append('--channel=' + channel)

    try:
        # Try to run it, merging stderr into output
        ret['output'] = subprocess.check_output([SNAP_BINARY_NAME, cmd, pkg] + args, stderr=subprocess.STDOUT)
        ret['result'] = True
    except subprocess.CalledProcessError as e:
        ret['output'] = e.output
        ret['result'] = False

    return ret


def is_installed(pkg):
    return bool(versions_installed(pkg))


def remove(pkg):
    retcode = subprocess.call([SNAP_BINARY_NAME, 'remove', pkg])
    return retcode == 0


# Parse 'snap list' into a dict
def versions_installed(pkg):
    try:
        # Try to run it, merging stderr into output
        output = subprocess.check_output([SNAP_BINARY_NAME, 'list', pkg], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        return []

    lines = output.splitlines()[1:]
    ret = []
    for item in lines:
        # If fields contain spaces this will break.
        i = item.split()
        # Ignore 'Notes' field
        ret.append({
            'name':         i[0],
            'version':      i[1],
            'rev':          i[2],
            'tracking':     i[3],
            'publisher':    i[4]
            })

    return ret
