# -*- coding: utf-8 -*-
'''
Module for managing block devices

.. versionadded:: 2014.7.0
'''
from __future__ import absolute_import

# Import python libs
import logging
import subprocess

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators

log = logging.getLogger(__name__)

__func_alias__ = {
    'format_': 'format'
}

__virtualname__ = 'blockdev'


def __virtual__():
    '''
    Only load this module if the blockdev utility is available
    '''
    if salt.utils.is_windows():
        return (False, ('The {0} execution module '
                        'is not supported on windows'.format(__virtualname__)))
    elif not salt.utils.which('blockdev'):
        return (False, ('Cannot load the {0} execution module: '
                        'blockdev utility not found'.format(__virtualname__)))
    return __virtualname__


def tune(device, **kwargs):
    '''
    Set attributes for the specified device

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.tune /dev/sdX1 read-ahead=1024 read-write=True

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


@decorators.which('wipefs')
def wipe(device):
    '''
    Remove the filesystem information

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.wipe /dev/sdX1
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

    args
        a list containing only the desired arguments to return

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.dump /dev/sdX1
    '''
    cmd = ['blockdev',
           '--getro',
           '--getsz',
           '--getss',
           '--getpbsz',
           '--getiomin',
           '--getioopt',
           '--getalignoff',
           '--getmaxsect',
           '--getsize',
           '--getsize64',
           '--getra',
           '--getfra',
           str(device)]
    ret = {}
    opts = [c[2:] for c in cmd if c.startswith('--')]
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] == 0:
        lines = [line for line in out['stdout'].splitlines() if line]
        count = 0
        for line in lines:
            ret[opts[count]] = line
            count += 1
        if args:
            temp_ret = {}
            for arg in args:
                temp_ret[arg] = ret[arg]
            return temp_ret
        else:
            return ret
    else:
        return False


@decorators.which('sync')
@decorators.which('mkfs')
def format_(device, fs_type='ext4', inode_size=None, lazy_itable_init=None):
    '''
    Format a filesystem onto a block device

    .. versionadded:: 2015.8.2

    device
        The block device in which to create the new filesystem

    fs_type
        The type of filesystem to create

    inode_size
        Size of the inodes

        This option is only enabled for ext and xfs filesystems

    lazy_itable_init
        If enabled and the uninit_bg feature is enabled, the inode table will
        not be fully initialized by mke2fs.  This speeds up filesystem
        initialization noticeably, but it requires the kernel to finish
        initializing the filesystem  in  the  background  when  the filesystem
        is first mounted.  If the option value is omitted, it defaults to 1 to
        enable lazy inode table zeroing.

        This option is only enabled for ext filesystems

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.format /dev/sdX1
    '''
    cmd = ['mkfs', '-t', str(fs_type)]
    if inode_size is not None:
        if fs_type[:3] == 'ext':
            cmd.extend(['-i', str(inode_size)])
        elif fs_type == 'xfs':
            cmd.extend(['-i', 'size={0}'.format(inode_size)])
    if lazy_itable_init is not None:
        if fs_type[:3] == 'ext':
            cmd.extend(['-E', 'lazy_itable_init={0}'.format(lazy_itable_init)])
    cmd.append(str(device))

    mkfs_success = __salt__['cmd.retcode'](cmd, ignore_retcode=True) == 0
    sync_success = __salt__['cmd.retcode']('sync', ignore_retcode=True) == 0

    return all([mkfs_success, sync_success])


@decorators.which_bin(['lsblk', 'df'])
def fstype(device):
    '''
    Return the filesystem name of a block device

    .. versionadded:: 2015.8.2

    device
        The name of the block device

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.fstype /dev/sdX1
    '''
    if salt.utils.which('lsblk'):
        lsblk_out = __salt__['cmd.run']('lsblk -o fstype {0}'.format(device)).splitlines()
        if len(lsblk_out) > 1:
            fs_type = lsblk_out[1].strip()
            if fs_type:
                return fs_type

    if salt.utils.which('df'):
        # the fstype was not set on the block device, so inspect the filesystem
        # itself for its type
        df_out = __salt__['cmd.run']('df -T {0}'.format(device)).splitlines()
        if len(df_out) > 1:
            fs_type = df_out[1]
            if fs_type:
                return fs_type

    return ''


@decorators.which('resize2fs')
def resize2fs(device):
    '''
    Resizes the filesystem.

    CLI Example:
    .. code-block:: bash

        salt '*' blockdev.resize2fs /dev/sdX1
    '''
    ret = {}
    cmd = 'resize2fs {0}'.format(device)
    try:
        out = __salt__['cmd.run_all'](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out['retcode'] == 0:
        return True
