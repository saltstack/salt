# -*- coding: utf-8 -*-
'''
Manage chassis via Salt Proxies.

.. versionadded:: 2015.8.2

Example managing a Dell chassis:

.. code-block:: yaml

    my-dell-chassis:
      chassis.dell:
        - name: my-dell-chassis
        - location: my-location
        - mode: 2
        - idrac_launch: 1
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs

log = logging.getLogger(__name__)


def __virtual__():
    return 'chassis.cmd' in __salt__


def dell(name, location=None, mode=None, idrac_launch=None, slot_names=None):
    '''
    Manaage a Dell Chassis.

    name
        The name of the chassis.

    location
        The location of the chassis.

    mode
        The management mode of the chassis. Viable options are:

        - 0: None
        - 1: Monitor
        - 2: Manage and Monitor

    idrac_launch
        The iDRAC launch method of the chassis. Viable options are:

        - 0: Disabled (launch iDRAC using IP address)
        - 1: Enabled (launch iDRAC using DNS name)

    slot_names
        The names of the slots, provided as a list.

    Example:

    .. code-block:: yaml

        my-dell-chassis:
          chassis.dell:
            - name: my-dell-chassis
            - location: my-location
            - mode: 2
            - idrac_launch: 1
            - slot_names:
              - 1: my-slot-name
              - 2: my-other-slot-name
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    chassis_cmd = 'chassis.cmd'
    current_name = __salt__[chassis_cmd]('get_chassis_name')
    current_location = __salt__[chassis_cmd]('get_chassis_location')
    mode_cmd = 'cfgRacTuning cfgRacTuneChassisMgmtAtServer'
    current_mode = __salt__[chassis_cmd]('get_general {0}'.format(mode_cmd))
    launch_cmd = 'cfgRacTuning cfgRacTuneIdracDNSLaunchEnable'
    current_launch_method = __salt__[chassis_cmd]('get_general {0}'.format(launch_cmd))
    current_slot_names = __salt__[chassis_cmd]('list_slotnames')

    if name != current_name:
        ret['changes'].update({'Name':
                              {'Old': current_name,
                               'New': name}})

    if location != current_location:
        ret['changes'].update({'Location':
                              {'Old': current_location,
                               'New': location}})

    if mode != current_mode:
        ret['changes'].update({'Management Mode':
                              {'Old': current_mode,
                               'New': mode}})

    if idrac_launch != current_launch_method:
        ret['changes'].update({'iDrac Launch Method':
                              {'Old': current_launch_method,
                               'New': idrac_launch}})
#    if slot_names is None:
#        slot_names = []
#    for item in slot_names:
#        slot_name = slot_names.get(item)
#       current_slot_name = current_slot_names.get(item).get('slotname')
#       if current_slot_name != slot_name:
#            ret['changes'].update({'Slot Names':
#                                  {'Old': {item: current_slot_name},
#                                   'New': {item: slot_name}}})

    if ret['changes'] == {}:
        ret['comment'] = 'Dell chassis is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Dell chassis configuration will change.'
        return ret

    # Finally, set the necessary configurations on the chassis.
    name = __salt__[chassis_cmd]('set_chassis_name {0}'.format(name))
    if location:
        location = __salt__[chassis_cmd]('set_chassis_location {0}'.format(location))
    if mode:
        mode = __salt__[chassis_cmd]('set_general {0} {1}'.format(mode_cmd, mode))
    if idrac_launch:
        idrac_launch = __salt__[chassis_cmd]('set_general {0} {1}'.format(launch_cmd, idrac_launch))

    if any([name, location, mode, idrac_launch]) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the Dell chassis.'

    ret['comment'] = 'Dell chassis was updated.'
    return ret


def blade(name, idrac_dns, power):
    '''
    Manage Dell Blades via iDRAC.

    name
        The name of the blade.

    idrac_dns


    power

    '''
