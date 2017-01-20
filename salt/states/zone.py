# -*- coding: utf-8 -*-
'''
Management of Solaris Zones

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.modules.zoneadm, salt.modules.zonecfg
:platform:      solaris

.. versionadded:: nitrogen

.. code-block:: yaml

    FIXME: add good example

.. note::

    TODO:
    - zone.resource_present
    - zone.resource_absent
    - zone.present
    - zone.absent

'''
from __future__ import absolute_import

# Import Python libs
import logging
import os

# Import Salt libs
import salt.utils
import salt.utils.files
import salt.utils.atomicfile
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the state's virtual name
__virtualname__ = 'zone'


def __virtual__():
    '''
    Provides zone state on Solaris
    '''
    if 'zonecfg.create' in __salt__ and 'zoneadm.install' in __salt__:
        return True
    else:
        return (
            False,
            '{0} state module can only be loaded on Solaris platforms'.format(
                __virtualname__
            )
        )


def property_present(name, property, value):
    '''
    Ensure property has a certain value

    name : string
        name of the zone
    property : string
        name of property
    value : string
        value of property

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if property in zonecfg:
            if zonecfg[property] != value:
                # update property
                zonecfg_res = __salt__['zonecfg.set_property'](name, property, value)
                ret['result'] = zonecfg_res['status']
                if 'messages' in zonecfg_res:
                    ret['comment'] = zonecfg_res['message']
                if ret['result']:
                    ret['changes'][property] = value
            else:
                ret['result'] = True
                ret['comment'] = 'The property {0} is already set to {1}!'.format(property, value)
        else:
            ret['result'] = False
            ret['comment'] = 'The property {0} does not exist!'.format(property)
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def property_absent(name, property):
    '''
    Ensure property is absent

    name : string
        name of the zone
    property : string
        name of property

    .. note::
        This does a zoneacfg clear call. So the property may be reset to a default value!
        Does has the side effect of always having to be called.

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True, configured=True)
    if name in zones:
        ## zone exists
        zonecfg = __salt__['zonecfg.info'](name, show_all=True)
        if property in zonecfg:
            # clear property
            zonecfg_res = __salt__['zonecfg.clear_property'](name, property)
            zonecfg_new = __salt__['zonecfg.info'](name, show_all=True)
            ret['result'] = zonecfg_res['status']
            if 'messages' in zonecfg_res:
                ret['comment'] = zonecfg_res['message']
            if zonecfg[property] != zonecfg_new[property]:
                ret['changes'][property] = zonecfg_new[property]
        else:
            ret['result'] = False
            ret['comment'] = 'The property {0} does not exist!'.format(property)
    else:
        ## zone does not exist
        ret['result'] = False
        ret['comment'] = 'The zone {0} is not in the configured, installed, or booted state.'.format(name)

    return ret


def booted(name):
    '''
    Ensure zone is booted

    name : string
        name of the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True)
    if name in zones:
        ## zone exists
        if zones[name]['state'] == 'running':
            ## zone is running
            ret['result'] = True
            ret['comment'] = 'zone {0} already booted'.format(name)
        else:
            ## try and boot the zone
            zoneadm_res = __salt__['zoneadm.boot'](name)
            if __opts__['test'] or zoneadm_res['status']:
                ret['result'] = True
                ret['changes'][name] = 'booted'
                ret['comment'] = 'zone {0} booted'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'failed to boot {0}'.format(name)
    else:
        ## zone does not exist
        ret['comment'] = []
        ret['comment'].append(
            'The zone {0} is not in the installed or booted state.'.format(name)
        )
        for zone in zones:
            if zones[zone]['uuid'] == name:
                ret['comment'].append(
                    'The zone {0} has a uuid of {1}, please use the zone name instead!'.format(
                        zone,
                        name,
                    )
                )

        ret['result'] = False
        ret['comment'] = "\n".join(ret['comment'])

    return ret


def halted(name):
    '''
    Ensure zone is halted

    name : string
        name of the zone

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    zones = __salt__['zoneadm.list'](installed=True)
    if name in zones:
        ## zone exists
        if zones[name]['state'] != 'running':
            ## zone is not running
            ret['result'] = True
            ret['comment'] = 'zone {0} already halted'.format(name)
        else:
            ## try and halt the zone
            zoneadm_res = __salt__['zoneadm.halt'](name)
            if __opts__['test'] or zoneadm_res['status']:
                ret['result'] = True
                ret['changes'][name] = 'halted'
                ret['comment'] = 'zone {0} halted'.format(name)
            else:
                ret['result'] = False
                ret['comment'] = 'failed to halt {0}'.format(name)
    else:
        ## zone does not exist
        ret['comment'] = []
        ret['comment'].append(
            'The zone {0} is not in the installed state.'.format(name)
        )
        for zone in zones:
            if zones[zone]['uuid'] == name:
                ret['comment'].append(
                    'The zone {0} has a uuid of {1}, please use the zone name instead!'.format(
                        zone,
                        name,
                    )
                )

        ret['result'] = False
        ret['comment'] = "\n".join(ret['comment'])

    return ret

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
