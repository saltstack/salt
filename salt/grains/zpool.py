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
    'cmd.run_all': salt.modules.cmdmod.run_all,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Figure out if we need to be loaded
    '''
    # Don't load on windows, NetBSD, or proxy
    # NOTE: ZFS on Windows is in development
    # NOTE: ZFS on NetBSD is in development
    if salt.utils.platform.is_windows() or salt.utils.platform.is_netbsd() or 'proxyminion' in __opts__:
        return False

    # Don't load if we do not have the zpool command
    if not salt.utils.path.which('zpool'):
        return False

    return True


def _zpool_data(zpool_cmd):
    '''
    Provide grains about zpools
    '''
    # collect zpool data
    grains = {}
    for zpool in __salt__['cmd.run']('{zpool} list -H -o name,size'.format(zpool=zpool_cmd)).splitlines():
        if 'zpool' not in grains:
            grains['zpool'] = {}
        zpool = zpool.split()
        grains['zpool'][zpool[0]] = zpool[1]

    # return grain data
    return grains


def zpool():
    '''
    Provide grains for zfs/zpool
    '''
    grains = {}
    zpool_cmd = salt.utils.path.which('zpool')

    grains = salt.utils.dictupdate.update(grains, _zpool_data(zpool_cmd), merge_lists=True)

    return grains

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
