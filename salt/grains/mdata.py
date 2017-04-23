# -*- coding: utf-8 -*-
'''
SmartOS Metadata grain provider

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils, salt.module.cmdmod
:platform:      SmartOS

.. versionadded:: nitrogen

'''
from __future__ import absolute_import

# Import python libs
import os
import json
import logging

# Import salt libs
import salt.utils
import salt.utils.dictupdate

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


def _user_mdata(mdata_list=None, mdata_get=None):
    '''
    User Metadata
    '''
    grains = {}

    if not mdata_list:
        mdata_list = salt.utils.which('mdata-list')

    if not mdata_get:
        mdata_get = salt.utils.which('mdata-get')

    if not mdata_list or not mdata_get:
        return grains

    for mdata_grain in __salt__['cmd.run'](mdata_list).splitlines():
        mdata_value = __salt__['cmd.run']('{0} {1}'.format(mdata_get, mdata_grain))

        if not mdata_grain.startswith('sdc:'):
            if 'mdata' not in grains:
                grains['mdata'] = {}

            log.debug('found mdata entry {name} with value {value}'.format(name=mdata_grain, value=mdata_value))
            mdata_grain = mdata_grain.replace('-', '_')
            mdata_grain = mdata_grain.replace(':', '_')
            grains['mdata'][mdata_grain] = mdata_value

    return grains


def _sdc_mdata(mdata_list=None, mdata_get=None):
    '''
    SDC Metadata specified by there specs
    https://eng.joyent.com/mdata/datadict.html
    '''
    grains = {}
    sdc_text_keys = [
        'uuid',
        'server_uuid',
        'datacenter_name',
        'hostname',
        'dns_domain',
    ]
    sdc_json_keys = [
        'resolvers',
        'nics',
        'routes',
    ]

    if not mdata_list:
        mdata_list = salt.utils.which('mdata-list')

    if not mdata_get:
        mdata_get = salt.utils.which('mdata-get')

    if not mdata_list or not mdata_get:
        return grains

    for mdata_grain in sdc_text_keys+sdc_json_keys:
        mdata_value = __salt__['cmd.run']('{0} sdc:{1}'.format(mdata_get, mdata_grain))

        if not mdata_value.startswith('No metadata for '):
            if 'mdata' not in grains:
                grains['mdata'] = {}
            if 'sdc' not in grains['mdata']:
                grains['mdata']['sdc'] = {}

            log.debug('found mdata entry sdc:{name} with value {value}'.format(name=mdata_grain, value=mdata_value))
            mdata_grain = mdata_grain.replace('-', '_')
            mdata_grain = mdata_grain.replace(':', '_')
            if mdata_grain in sdc_json_keys:
                grains['mdata']['sdc'][mdata_grain] = json.loads(mdata_value)
            else:
                grains['mdata']['sdc'][mdata_grain] = mdata_value

    return grains


def _legacy_grains(grains):
    '''
    Grains for backwards compatibility
    '''
    # parse legacy sdc grains
    if 'mdata' in grains and 'sdc' in grains['mdata']:
        if 'server_uuid' not in grains['mdata']['sdc'] or 'FAILURE' in grains['mdata']['sdc']['server_uuid']:
            grains['hypervisor_uuid'] = 'unknown'
        else:
            grains['hypervisor_uuid'] = grains['mdata']['sdc']['server_uuid']

        if 'datacenter_name' not in grains['mdata']['sdc'] or 'FAILURE' in grains['mdata']['sdc']['datacenter_name']:
            grains['datacenter'] = 'unknown'
        else:
            grains['datacenter'] = grains['mdata']['sdc']['datacenter_name']

    # parse rules grains
    if 'mdata' in grains and 'rules' in grains['mdata']:
        grains['roles'] = grains['mdata']['roles'].split(',')

    return grains


def mdata():
    '''
    Provide grains from the SmartOS metadata
    '''
    grains = {}
    mdata_list = salt.utils.which('mdata-list')
    mdata_get = salt.utils.which('mdata-get')

    grains = salt.utils.dictupdate.update(grains, _user_mdata(mdata_list, mdata_get), merge_lists=True)
    grains = salt.utils.dictupdate.update(grains, _sdc_mdata(mdata_list, mdata_get), merge_lists=True)
    grains = _legacy_grains(grains)

    return grains

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
