# -*- coding: utf-8 -*-
'''
Module for managing block devices

.. versionadded:: 2014.7.0
.. deprecated:: Boron
   Merged to `disk` module

'''
from __future__ import absolute_import

# Import python libs
import logging

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

    .. deprecated:: Boron
       Use `disk.tune`

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.tune /dev/sda1 read-ahead=1024 read-write=True

    Valid options are: ``read-ahead``, ``filesystem-read-ahead``,
    ``read-only``, ``read-write``.

    See the ``blockdev(8)`` manpage for a more complete description of these
    options.
    '''
    salt.utils.warn_until(
        'Carbon',
        'The blockdev module has been merged with the disk module, and will disappear in Carbon'
    )
    return __salt__['disk.tune'](device, **kwargs)


def wipe(device):
    '''
    Remove the filesystem information

    .. deprecated:: Boron
       Use `disk.tune`

    CLI Example:

    .. code-block:: bash

        salt '*' blockdev.wipe /dev/sda1
    '''
    salt.utils.warn_until(
        'Carbon',
        'The blockdev module has been merged with the disk module, and will disappear in Carbon'
    )
    return __salt__['disk.wipe'](device)


def dump(device, args=None):
    '''
    Return all contents of dumpe2fs for a specified device

    .. deprecated:: Boron
       Use `disk.dump`

    CLI Example:
    .. code-block:: bash

        salt '*' extfs.dump /dev/sda1
    '''
    salt.utils.warn_until(
        'Carbon',
        'The blockdev module has been merged with the disk module, and will disappear in Carbon'
    )
    return __salt__['disk.dump'](device, args)


def resize2fs(device):
    '''
    Resizes the filesystem.

    .. deprecated:: Boron
       Use `disk.resize2fs`

    CLI Example:
    .. code-block:: bash

        salt '*' blockdev.resize2fs /dev/sda1
    '''
    salt.utils.warn_until(
        'Carbon',
        'The blockdev module has been merged with the disk module, and will disappear in Carbon'
    )
    return __salt__['disk.resize2fs'](device)
