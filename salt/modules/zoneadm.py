# -*- coding: utf-8 -*-
'''
Module for Solaris' zoneadm
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators
from salt.ext.six.moves import range

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'zoneadm'

# Function aliases
__func_alias__ = {
    'list_zones': 'list'
}


@salt.utils.decorators.memoize
def _is_globalzone():
    '''
    Check if we are running in the globalzone
    '''
    if not __grains__['kernel'] == 'SunOS':
        return False

    zonename = __salt__['cmd.run_all']('zonename')
    if zonename['retcode']:
        return False
    if zonename['stdout'] == 'global':
        return True

    return False


def __virtual__():
    '''
    We are available if we have zoneadm util and are a Solaris globalzone
    '''
    if _is_globalzone() and salt.utils.which('zoneadm'):
        return __virtualname__

    return (
        False,
        '{0} module can only be loaded in a solaris globalzone.'.format(
            __virtualname__
        )
    )


def list_zones(verbose=True, installed=False, configured=False, hide_global=True):
    '''
    List all zones

    verbose : boolean
        display additional zone information
    installed : boolean
        include installed zones in output
    configured : boolean
        include configured zones in output
    hide_global : boolean
        do not include global zone

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.list
    '''
    zones = {}

    ## fetch zones
    header = 'zoneid:zonename:state:zonepath:uuid:brand:ip-type'.split(':')
    zone_data = __salt__['cmd.run_all']('zoneadm list -p -c')
    if zone_data['retcode'] == 0:
        for zone in zone_data['stdout'].splitlines():
            zone = zone.split(':')

            # create zone_t
            zone_t = {}
            for i in range(0, len(header)):
                zone_t[header[i]] = zone[i]

            # skip if global and hide_global
            if hide_global and zone_t['zonename'] == 'global':
                continue

            # skip installed and configured
            if not installed and zone_t['state'] == 'installed':
                continue
            if not configured and zone_t['state'] == 'configured':
                continue

            # update dict
            zones[zone_t['zonename']] = zone_t
            del zones[zone_t['zonename']]['zonename']

    return zones if verbose else sorted(zones.keys())

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
