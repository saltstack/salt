# -*- coding: utf-8 -*-
'''
Module for Solaris 10's zoneadm

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      OmniOS,OpenIndiana,SmartOS,OpenSolaris,Solaris 10

.. versionadded:: nitrogen

.. warning::
    Oracle Solaris 11's zoneadm is not supported by this module!

.. note::
    Not all subcommands are implemented.

    These subcommands are missing:
    attach, detach, clone, install,
    uninstall, move, ready, and verify

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
    We are available if we are have zoneadm and are the global zone on
    Solaris 10, OmniOS, OpenIndiana, OpenSolaris, or Smartos.
    '''
    ## note: we depend on PR#37472 to distinguish between Solaris and Oracle Solaris
    if _is_globalzone() and salt.utils.which('zoneadm'):
        if __grains__['os'] in ['Solaris', 'OpenSolaris', 'SmartOS', 'OmniOS', 'OpenIndiana']:
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


def boot(zone, single=False, altinit=None, smf_options=None):
    '''
    Boot (or activate) the specified zone.

    zone : string
        name of the zone
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.boot clementine
        salt '*' zoneadm.boot maeve single=True
        salt '*' zoneadm.boot teddy single=True smf_options=verbose
    '''
    ## zone is running
    if zone in list_zones():
        return True

    ## build boot_options
    boot_options = ''
    if single:
        boot_options = '-s {0}'.format(boot_options)
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = '-i {0} {1}'.format(altinit, boot_options)
    if smf_options:
        boot_options = '-m {0} {1}'.format(smf_options, boot_options)
    if boot_options != '':
        boot_options = ' -- {0}'.format(boot_options.strip())

    ## execute boot
    res = __salt__['cmd.run_all']('zoneadm -z {zone} boot{boot_opts}'.format(
        zone=zone,
        boot_opts=boot_options,
    ))
    return res['retcode'] == 0


def reboot(zone, single=False, altinit=None, smf_options=None):
    '''
    Restart the zone. This is equivalent to a halt boot sequence.

    zone : string
        name of the zone
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.reboot dolores
        salt '*' zoneadm.reboot teddy single=True
    '''
    ## build boot_options
    boot_options = ''
    if single:
        boot_options = '-s {0}'.format(boot_options)
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = '-i {0} {1}'.format(altinit, boot_options)
    if smf_options:
        boot_options = '-m {0} {1}'.format(smf_options, boot_options)
    if boot_options != '':
        boot_options = ' -- {0}'.format(boot_options.strip())

    ## execute boot
    res = __salt__['cmd.run_all']('zoneadm -z {zone} reboot{boot_opts}'.format(
        zone=zone,
        boot_opts=boot_options,
    ))
    return res['retcode'] == 0


def halt(zone):
    '''
    Halt the specified zone.

    zone : string
        name of the zone

    .. note::
        To cleanly shutdown the zone use the shutdown function.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.halt hector
    '''
    ## zone is not running or not available
    if zone not in list_zones():
        return True

    ## execute halt
    res = __salt__['cmd.run_all']('zoneadm -z {zone} halt'.format(
        zone=zone,
    ))
    return res['retcode'] == 0


def shutdown(zone, reboot=False, single=False, altinit=None, smf_options=None):
    '''
    Gracefully shutdown the specified zone.

    zone : string
        name of the zone
    reboot : boolean
        reboot zone after shutdown (equivalent of shutdown -i6 -g0 -y)
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.shutdown peter
        salt '*' zoneadm.shutdown armistice reboot=True
    '''
    ## build boot_options
    boot_options = ''
    if single:
        boot_options = '-s {0}'.format(boot_options)
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = '-i {0} {1}'.format(altinit, boot_options)
    if smf_options:
        boot_options = '-m {0} {1}'.format(smf_options, boot_options)
    if boot_options != '':
        boot_options = ' -- {0}'.format(boot_options.strip())

    ## execute boot
    res = __salt__['cmd.run_all']('zoneadm -z {zone} shutdown{reboot}{boot_opts}'.format(
        zone=zone,
        reboot=' -r' if reboot else '',
        boot_opts=boot_options,
    ))
    return res['retcode'] == 0

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
