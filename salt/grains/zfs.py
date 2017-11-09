# -*- coding: utf-8 -*-
'''
ZFS grain provider

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils, salt.module.cmdmod
:platform:      illumos,freebsd,linux

.. versionadded:: Oxygen

'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils.dictupdate
import salt.utils.path
import salt.utils.platform

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__virtualname__ = 'zfs'
__salt__ = {
    'cmd.run': salt.modules.cmdmod.run,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load zfs grains
    '''
    # NOTE: we always load this grain so we can properly export
    #       atleast the zfs_support grain
    return __virtualname__


def _check_retcode(cmd):
    '''
    Simple internal wrapper for cmdmod.retcode
    '''
    return salt.modules.cmdmod.retcode(cmd, output_loglevel='quiet', ignore_retcode=True) == 0


def _zfs_support():
    '''
    Provide information about zfs kernel module
    '''
    grains = {'zfs_support': False}

    # Check for zfs support
    # NOTE: ZFS on Windows is in development
    # NOTE: ZFS on NetBSD is in development
    on_supported_platform = False
    if salt.utils.platform.is_sunos() and salt.utils.path.which('zfs'):
        on_supported_platform = True
    elif salt.utils.platform.is_freebsd() and _check_retcode('kldstat -q -m zfs'):
        on_supported_platform = True
    elif salt.utils.platform.is_linux():
        modinfo = salt.utils.path.which('modinfo')
        if modinfo:
            on_supported_platform = _check_retcode('{0} zfs'.format(modinfo))
        else:
            on_supported_platform = _check_retcode('ls /sys/module/zfs')

        # NOTE: fallback to zfs-fuse if needed
        if not on_supported_platform:
            _zfs_fuse = lambda f: __salt__['service.' + f]('zfs-fuse')
            if _zfs_fuse('available') and (_zfs_fuse('status') or _zfs_fuse('start')):
                on_supported_platform = True

    # Additional check for the zpool command
    if on_supported_platform and salt.utils.path.which('zpool'):
        grains['zfs_support'] = True

    return grains


def _zfs_pool_data():
    '''
    Provide grains about zpools
    '''
    grains = {}

    # collect zpool data
    zpool_cmd = salt.utils.path.which('zpool')
    for zpool in __salt__['cmd.run']('{zpool} list -H -o name,size'.format(zpool=zpool_cmd)).splitlines():
        if 'zpool' not in grains:
            grains['zpool'] = {}
        zpool = zpool.split()
        grains['zpool'][zpool[0]] = zpool[1]

    # return grain data
    return grains


def zfs():
    '''
    Provide grains for zfs/zpool
    '''
    grains = {}

    grains = salt.utils.dictupdate.update(grains, _zfs_support(), merge_lists=True)
    if grains['zfs_support']:
        grains = salt.utils.dictupdate.update(grains, _zfs_pool_data(), merge_lists=True)

    return grains

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
