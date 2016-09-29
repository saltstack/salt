# -*- coding: utf-8 -*-
'''
Module for managing block devices

.. versionadded:: 2014.7.0
.. deprecated:: Carbon
   Merged to `disk` module

'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

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


def format_(device, fs_type='ext4',
            inode_size=None, lazy_itable_init=None, force=False):
    '''
    Format a filesystem onto a block device

    .. versionadded:: 2015.8.2

    .. deprecated:: Carbon

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

    force
        Force mke2fs to create a filesystem, even if the specified device is
        not a partition on a block special device. This option is only enabled
        for ext and xfs filesystems

        This option is dangerous, use it with caution.

        .. versionadded:: Carbon

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.format /dev/sdX1
    '''
    salt.utils.warn_until(
        'Oxygen',
        'The blockdev module has been merged with the disk module,'
        'and will disappear in Oxygen. Use the disk.format_ function instead.'
    )
    return __salt__['disk.format_'](device,
                                    fs_type=fs_type,
                                    inode_size=inode_size,
                                    lazy_itable_init=lazy_itable_init,
                                    force=force)


def fstype(device):
    '''
    Return the filesystem name of a block device

    .. versionadded:: 2015.8.2

    .. deprecated:: Carbon

    device
        The name of the block device

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.fstype /dev/sdX1
    '''
    salt.utils.warn_until(
        'Oxygen',
        'The blockdev module has been merged with the disk module,'
        'and will disappear in Oxygen. Use the disk.fstype function instead.'
    )
    return __salt__['disk.fstype'](device)
