# -*- coding: utf-8 -*-
'''
    test grains
'''
from __future__ import absolute_import

# Import python libs
import os
import logging

# Import salt libs
import salt.utils

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod

__virtualname__ = 'mdata'
__salt__ = {
    'cmd.run': salt.modules.cmdmod.run,
    'cmd.run_all': salt.modules.cmdmod.run_all,
}

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Figure out if we need to be loaded
    '''
    ## collect mdata grains in a SmartOS zone
    if salt.utils.is_smartos_zone():
        return __virtualname__
    ## collect mdata grains in a LX zone
    if salt.utils.is_linux() and 'BrandZ virtual linux' in os.uname():
        return __virtualname__
    return False


def mdata():
    '''
    Provide grains from the SmartOS metadata
    '''
    grains = {}
    mdata_list = salt.utils.which('mdata-list')
    mdata_get = salt.utils.which('mdata-get')

    # parse sdc metadata
    grains['hypervisor_uuid'] = __salt__['cmd.run']('{0} sdc:server_uuid'.format(mdata_get))
    if "FAILURE" in grains['hypervisor_uuid'] or "No metadata" in grains['hypervisor_uuid']:
        grains['hypervisor_uuid'] = "Unknown"
    grains['datacenter'] = __salt__['cmd.run']('{0} sdc:datacenter_name'.format(mdata_get))
    if "FAILURE" in grains['datacenter'] or "No metadata" in grains['datacenter']:
        grains['datacenter'] = "Unknown"

    # parse vmadm metadata
    for mdata_grain in __salt__['cmd.run'](mdata_list).splitlines():
        grain_data = __salt__['cmd.run']('{0} {1}'.format(mdata_get, mdata_grain))

        if mdata_grain == 'roles':  # parse roles as roles grain
            grain_data = grain_data.split(',')
            grains['roles'] = grain_data
        else:  # parse other grains into mdata
            if not mdata_grain.startswith('sdc:'):
                if 'mdata' not in grains:
                    grains['mdata'] = {}

                mdata_grain = mdata_grain.replace('-', '_')
                mdata_grain = mdata_grain.replace(':', '_')
                grains['mdata'][mdata_grain] = grain_data

    return grains
