# -*- coding: utf-8 -*-
'''
Module for managing ext2/3/4 file systems
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import salt libs
import salt.utils.platform

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.platform.is_windows():
        return (
            False,
            'The extfs execution module cannot be loaded: only available on '
            'non-Windows systems.'
        )
    return True


def mkfs(device, fs_type, **kwargs):
    '''
    Create a file system on the specified device

    CLI Example:

    .. code-block:: bash

        salt '*' extfs.mkfs /dev/sda1 fs_type=ext4 opts='acl,noexec'

    Valid options are:

    * **block_size**: 1024, 2048 or 4096
    * **check**: check for bad blocks
    * **direct**: use direct IO
    * **ext_opts**: extended file system options (comma-separated)
    * **fragment_size**: size of fragments
    * **force**: setting force to True will cause mke2fs to specify the -F
      option twice (it is already set once); this is truly dangerous
    * **blocks_per_group**: number of blocks in a block group
    * **number_of_groups**: ext4 option for a virtual block group
    * **bytes_per_inode**: set the bytes/inode ratio
    * **inode_size**: size of the inode
    * **journal**: set to True to create a journal (default on ext3/4)
    * **journal_opts**: options for the fs journal (comma separated)
    * **blocks_file**: read bad blocks from file
    * **label**: label to apply to the file system
    * **reserved**: percentage of blocks reserved for super-user
    * **last_dir**: last mounted directory
    * **test**: set to True to not actually create the file system (mke2fs -n)
    * **number_of_inodes**: override default number of inodes
    * **creator_os**: override "creator operating system" field
    * **opts**: mount options (comma separated)
    * **revision**: set the filesystem revision (default 1)
    * **super**: write superblock and group descriptors only
    * **fs_type**: set the filesystem type (REQUIRED)
    * **usage_type**: how the filesystem is going to be used
    * **uuid**: set the UUID for the file system

    See the ``mke2fs(8)`` manpage for a more complete description of these
    options.
    '''
    kwarg_map = {'block_size': 'b',
                 'check': 'c',
                 'direct': 'D',
                 'ext_opts': 'E',
                 'fragment_size': 'f',
                 'force': 'F',
                 'blocks_per_group': 'g',
                 'number_of_groups': 'G',
                 'bytes_per_inode': 'i',
                 'inode_size': 'I',
                 'journal': 'j',
                 'journal_opts': 'J',
                 'blocks_file': 'l',
                 'label': 'L',
                 'reserved': 'm',
                 'last_dir': 'M',
                 'test': 'n',
                 'number_of_inodes': 'N',
                 'creator_os': 'o',
                 'opts': 'O',
                 'revision': 'r',
                 'super': 'S',
                 'usage_type': 'T',
                 'uuid': 'U'}

    opts = ''
    for key in kwargs:
        if key in kwarg_map:
            opt = kwarg_map[key]
            if kwargs[key] == 'True':
                opts += '-{0} '.format(opt)
            else:
                opts += '-{0} {1} '.format(opt, kwargs[key])
    cmd = 'mke2fs -F -t {0} {1}{2}'.format(fs_type, opts, device)
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    ret = []
    for line in out:
        if not line:
            continue
        elif line.startswith('mke2fs'):
            continue
        elif line.startswith('Discarding device blocks'):
            continue
        elif line.startswith('Allocating group tables'):
            continue
        elif line.startswith('Writing inode tables'):
            continue
        elif line.startswith('Creating journal'):
            continue
        elif line.startswith('Writing superblocks'):
            continue
        ret.append(line)
    return ret


def tune(device, **kwargs):
    '''
    Set attributes for the specified device (using tune2fs)

    CLI Example:

    .. code-block:: bash

        salt '*' extfs.tune /dev/sda1 force=True label=wildstallyns opts='acl,noexec'

    Valid options are:

    * **max**: max mount count
    * **count**: mount count
    * **error**: error behavior
    * **extended_opts**: extended options (comma separated)
    * **force**: force, even if there are errors (set to True)
    * **group**: group name or gid that can use the reserved blocks
    * **interval**: interval between checks
    * **journal**: set to True to create a journal (default on ext3/4)
    * **journal_opts**: options for the fs journal (comma separated)
    * **label**: label to apply to the file system
    * **reserved**: percentage of blocks reserved for super-user
    * **last_dir**: last mounted directory
    * **opts**: mount options (comma separated)
    * **feature**: set or clear a feature (comma separated)
    * **mmp_check**: mmp check interval
    * **reserved**: reserved blocks count
    * **quota_opts**: quota options (comma separated)
    * **time**: time last checked
    * **user**: user or uid who can use the reserved blocks
    * **uuid**: set the UUID for the file system

    See the ``mke2fs(8)`` manpage for a more complete description of these
    options.
    '''
    kwarg_map = {'max': 'c',
                 'count': 'C',
                 'error': 'e',
                 'extended_opts': 'E',
                 'force': 'f',
                 'group': 'g',
                 'interval': 'i',
                 'journal': 'j',
                 'journal_opts': 'J',
                 'label': 'L',
                 'last_dir': 'M',
                 'opts': 'o',
                 'feature': 'O',
                 'mmp_check': 'p',
                 'reserved': 'r',
                 'quota_opts': 'Q',
                 'time': 'T',
                 'user': 'u',
                 'uuid': 'U'}
    opts = ''
    for key in kwargs:
        if key in kwarg_map:
            opt = kwarg_map[key]
            if kwargs[key] == 'True':
                opts += '-{0} '.format(opt)
            else:
                opts += '-{0} {1} '.format(opt, kwargs[key])
    cmd = 'tune2fs {0}{1}'.format(opts, device)
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    return out


def attributes(device, args=None):
    '''
    Return attributes from dumpe2fs for a specified device

    CLI Example:

    .. code-block:: bash

        salt '*' extfs.attributes /dev/sda1
    '''
    fsdump = dump(device, args)
    return fsdump['attributes']


def blocks(device, args=None):
    '''
    Return block and inode info from dumpe2fs for a specified device

    CLI Example:

    .. code-block:: bash

        salt '*' extfs.blocks /dev/sda1
    '''
    fsdump = dump(device, args)
    return fsdump['blocks']


def dump(device, args=None):
    '''
    Return all contents of dumpe2fs for a specified device

    CLI Example:

    .. code-block:: bash

        salt '*' extfs.dump /dev/sda1
    '''
    cmd = 'dumpe2fs {0}'.format(device)
    if args:
        cmd = cmd + ' -' + args
    ret = {'attributes': {}, 'blocks': {}}
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    mode = 'opts'
    group = None
    for line in out:
        if not line:
            continue
        if line.startswith('dumpe2fs'):
            continue
        if mode == 'opts':
            line = line.replace('\t', ' ')
            comps = line.split(': ')
            if line.startswith('Filesystem features'):
                ret['attributes'][comps[0]] = comps[1].split()
            elif line.startswith('Group') and not line.startswith('Group descriptor size'):
                mode = 'blocks'
            else:
                if len(comps) < 2:
                    continue
                ret['attributes'][comps[0]] = comps[1].strip()

        if mode == 'blocks':
            if line.startswith('Group'):
                line = line.replace(':', '')
                line = line.replace('(', '')
                line = line.replace(')', '')
                line = line.replace('[', '')
                line = line.replace(']', '')
                comps = line.split()
                blkgrp = comps[1]
                group = 'Group {0}'.format(blkgrp)
                ret['blocks'][group] = {}
                ret['blocks'][group]['group'] = blkgrp
                ret['blocks'][group]['range'] = comps[3]
                # TODO: comps[4:], which may look one one of the following:
                #     ITABLE_ZEROED
                #     INODE_UNINIT, ITABLE_ZEROED
                # Does anyone know what to call these?
                ret['blocks'][group]['extra'] = []
            elif 'Free blocks:' in line:
                comps = line.split(': ')
                free_blocks = comps[1].split(', ')
                ret['blocks'][group]['free blocks'] = free_blocks
            elif 'Free inodes:' in line:
                comps = line.split(': ')
                inodes = comps[1].split(', ')
                ret['blocks'][group]['free inodes'] = inodes
            else:
                line = line.strip()
                ret['blocks'][group]['extra'].append(line)
    return ret
