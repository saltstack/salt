# -*- coding: utf-8 -*-
'''
Module for Solaris 10's zonecfg

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      OmniOS,OpenIndiana,SmartOS,OpenSolaris,Solaris 10

.. versionadded:: nitrogen

.. todo:
    - set (location default=global)
    - add (resource)
    - remove (resource)
    - info

.. warning::
    Oracle Solaris 11's zonecfg is not supported by this module!
'''
from __future__ import absolute_import

# Import Python libs
import logging

# Import Salt libs
import salt.utils
import salt.utils.decorators

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'zonecfg'


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
    We are available if we are have zonecfg and are the global zone on
    Solaris 10, OmniOS, OpenIndiana, OpenSolaris, or Smartos.
    '''
    ## note: we depend on PR#37472 to distinguish between Solaris and Oracle Solaris
    if _is_globalzone() and salt.utils.which('zonecfg'):
        if __grains__['os'] in ['Solaris', 'OpenSolaris', 'SmartOS', 'OmniOS', 'OpenIndiana']:
            return __virtualname__

    return (
        False,
        '{0} module can only be loaded in a solaris globalzone.'.format(
            __virtualname__
        )
    )


def info(zone, resource=None):
    '''
    Display zone configuration

    zone : string
        name of zone
    resource : string
        optional resource type

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.info dolores
        salt '*' zonecfg.info dolores fs
    '''
    zonecfg = {}

    ##TODO

    return zonecfg


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
