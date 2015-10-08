# -*- coding: utf-8 -*-
'''
Manage Chassis via Salt Proxy.

Example using iDRAC:

.. code-block:: yaml

    my-chassis:
      chassis.named:
        - name: my-chassis
      chassis.located:
        - name: my-location
      chassis.mode_managed:
        - name: 2
      chassis.idrac_launched:
        - name: 0
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt Libs

log = logging.getLogger(__name__)


def __virtual__():
    return 'chassis.cmd' in __salt__


def named(name):
    '''
    Ensure the chassis's name.

    name
        The name the chassis should have.

    Example:

    .. code-block:: yaml

        my-chassis:
          chassis.named:
            - name: my-chassis
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    current_name = __salt__['chassis.cmd']('get_chassis_name')
    if name == current_name:
        ret['comment'] = 'Chassis name is up to date.'
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['changes'] = {
            'old': current_name,
            'new': name
        }
        ret['comment'] = 'Chassis name will change.'
        return ret

    if __salt__['chassis.cmd']('set_chassis_name') is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the name.'
        return ret

    ret['comment'] = 'Chassis name was set to {0}'.format(name)
    return ret


def located(name):
    '''
    Ensure the chassis's location.

    name
        The name of location the chassis should have.

    Example:

    .. code-block:: yaml

        my-chassis-location:
          chassis.located:
            - name: my-chassis-location
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    current_location = __salt__['chassis.cmd']('get_chassis_location')
    if name == current_location:
        ret['comment'] = 'Chassis location is up to date.'
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['changes'] = {
            'old': current_location,
            'new': name
        }
        ret['comment'] = 'Chassis location will change.'
        return ret

    if __salt__['chassis.cmd']('set_chassis_name') is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the location.'
        return ret

    ret['comment'] = 'Chassis location was set to {0}'.format(name)
    return ret


def mode_managed(name):
    '''
    Ensure the chassis management mode is configured appropriately.

    name
        The value the management mode should have. Viable options are:

        - 0: None
        - 1: Monitor
        - 2: Manage and Monitor

    Example:

    .. code-block:: yaml

        my-chassis-management-mode:
          chassis.mode_managed:
            - name: 1

    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    cmd = 'cfgRacTuning cfgRacTuneChassisMgmtAtServer'
    current_mode = __salt__['chassis.cmd']('get_general {0}'.format(cmd))
    if name == current_mode:
        ret['comment'] = 'Chassis management mode is up to date.'
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['changes'] = {
            'old': current_mode,
            'new': name
        }
        ret['comment'] = 'Chassis management mode will change.'
        return ret

    if __salt__['chassis.cmd']('set_general {0} {1}'.format(cmd, name)) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the management mode.'
        return ret

    ret['comment'] = 'Chassis management mode was set to {0}'.format(name)
    return ret


def idrac_launched(name):
    '''
    Ensure the iDRAC launch method is configured appropriately.

    name
        The value the launch method should have. Viable options are:

        - 0: Disabled (launch iDRAC using IP address)
        - 1: Enabled (launch iDRAC using DNS name)

    Example:

    .. code-block:: yaml

        my-iDRAC-launch-method:
          chassis.idrac_launched:
            - name: 1

    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    cmd = 'cfgRacTuning cfgRacTuneIdracDNSLaunchEnable'
    current_launch_method = __salt__['chassis.cmd']('get_general {0}'.format(cmd))
    if name == current_launch_method:
        ret['comment'] = 'Chassis iDRAC method is up to date.'
        return ret
    elif __opts__['test']:
        ret['result'] = None
        ret['changes'] = {
            'old': current_launch_method,
            'new': name
        }
        ret['comment'] = 'The iDRAC launch method will change.'
        return ret

    if __salt__['chassis.cmd']('set_general {0} {1}'.format(cmd, name)) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the iDRAC launch method.'
        return ret

    ret['comment'] = 'The iDRAC launch method was set to {0}'.format(name)
    return ret
