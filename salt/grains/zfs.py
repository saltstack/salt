# -*- coding: utf-8 -*-
'''
ZFS grain provider

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils, salt.module.cmdmod
:platform:      illumos,freebsd,linux

.. versionadded:: 2018.3.0

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.utils.dictupdate
import salt.utils.path
import salt.utils.platform

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod
import salt.utils.zfs

__virtualname__ = 'zfs'
__salt__ = {
    'cmd.run': salt.modules.cmdmod.run,
}
__utils__ = {
    'zfs.is_supported': salt.utils.zfs.is_supported,
    'zfs.has_feature_flags': salt.utils.zfs.has_feature_flags,
    'zfs.zpool_command': salt.utils.zfs.zpool_command,
    'zfs.to_size': salt.utils.zfs.to_size,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load zfs grains
    '''
    # NOTE: we always load this grain so we can properly export
    #       at least the zfs_support grain
    return __virtualname__


def _zfs_pool_data():
    '''
    Provide grains about zpools
    '''
    grains = {}

    # collect zpool data
    zpool_list_cmd = __utils__['zfs.zpool_command'](
        'list',
        flags=['-H', '-p'],
        opts={'-o': 'name,size'},
    )
    for zpool in __salt__['cmd.run'](zpool_list_cmd).splitlines():
        if 'zpool' not in grains:
            grains['zpool'] = {}
        zpool = zpool.split()
        grains['zpool'][zpool[0]] = __utils__['zfs.to_size'](zpool[1], True)

    # return grain data
    return grains


def zfs():
    '''
    Provide grains for zfs/zpool
    '''
    grains = {}
    grains['zfs_support'] = __utils__['zfs.is_supported']()
    grains['zfs_feature_flags'] = __utils__['zfs.has_feature_flags']()
    if grains['zfs_support']:
        grains = salt.utils.dictupdate.update(grains, _zfs_pool_data(), merge_lists=True)

    return grains

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
