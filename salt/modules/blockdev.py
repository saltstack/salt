# -*- coding: utf-8 -*-
'''
Module for managing block devices

.. versionadded:: 2014.7.0
'''

# Import python libs
import logging
import subprocess

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return True


def tune(device, **kwargs):
    '''
    Set attributes for the specified device

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.tune /dev/sda1 read-ahead=1024 read-write=True

    Valid options are: ``read-ahead``, ``filesystem-read-ahead``,
    ``read-only``, ``read-write``.

    See the ``blockdev(8)`` manpage for a more complete description of these
    options.
    '''

    kwarg_map = {'read-ahead': 'setra',
                 'filesystem-read-ahead': 'setfra',
                 'read-only': 'setro',
                 'read-write': 'setrw'}
    opts = ''
    args = []
    for key in kwargs:
        if key in kwarg_map:
            switch = kwarg_map[key]
            if key != 'read-write':
                args.append(switch.replace('set', 'get'))
            else:
                args.append('getro')
            if kwargs[key] == 'True' or kwargs[key] is True:
                opts += '--{0} '.format(key)
            else:
                opts += '--{0} {1} '.format(switch, kwargs[key])
    cmd = 'blockdev {0}{1}'.format(opts, device)
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    return dump(device, args)


def wipe(device):
    '''
    Remove the filesystem information

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.wipe /dev/sda1
    '''

    cmd = 'wipefs {0}'.format(device)
    try:
        out = __salt__['cmd.run_all'](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out['retcode'] == 0:
        return True


def dump(device, args=None):
    '''
    Return all contents of dumpe2fs for a specified device

    CLI Example:
    .. code-block:: bash

        salt '*' extfs.dump /dev/sda1
    '''
    cmd = 'blockdev --getro --getsz --getss --getpbsz --getiomin --getioopt --getalignoff  --getmaxsect --getsize --getsize64 --getra --getfra {0}'.format(device)
    ret = {}
    opts = [c[2:] for c in cmd.split() if c.startswith('--')]
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] == 0:
        lines = [line for line in out['stdout'].splitlines() if line]
        count = 0
        for line in lines:
            ret[opts[count]] = line
            count = count+1
        if args:
            temp_ret = {}
            for arg in args:
                temp_ret[arg] = ret[arg]
            return temp_ret
        else:
            return ret
    else:
        return False
