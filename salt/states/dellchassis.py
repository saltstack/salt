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
        - slot_names:
          - 1: my-slot-name
          - 2: my-other-slot-name
        - blade_power_states:
          - server-1: on
          - server-2: off
          - server-3: powercycle

'''

# Import python libs
from __future__ import absolute_import
import logging

log = logging.getLogger(__name__)


def __virtual__():
    return 'chassis.cmd' in __salt__


def dell(name, location=None, mode=None, idrac_launch=None, slot_names=None,
         blade_power_states=None):
    '''
    Manage a Dell Chassis.

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
        The names of the slots, provided as a listidentified by
        their slot numbers.

    blade_power_states
        The power states of a blade server, provided as a list and
        identified by their server numbers. Viable options are:

         - on: Ensure the blade server is powered on.
         - off: Ensure the blade server is powered off.
         - powercycle: Power cycle the blade server.

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
            - blade_power_states:
              - server-1: on
              - server-2: off
              - server-3: powercycle
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    chassis_cmd = 'chassis.cmd'
    cfg_tuning = 'cfgRacTuning'
    mode_cmd = 'cfgRacTuneChassisMgmtAtServer'
    launch_cmd = 'cfgRacTuneIdracDNSLaunchEnable'

    current_name = __salt__[chassis_cmd]('get_chassis_name')
    if name != current_name:
        ret['changes'].update({'Name':
                              {'Old': current_name,
                               'New': name}})

    if location:
        current_location = __salt__[chassis_cmd]('get_chassis_location')
        if location != current_location:
            ret['changes'].update({'Location':
                                  {'Old': current_location,
                                   'New': location}})
    if mode:
        current_mode = __salt__[chassis_cmd]('get_general', cfg_tuning, mode_cmd)
        if mode != current_mode:
            ret['changes'].update({'Management Mode':
                                  {'Old': current_mode,
                                   'New': mode}})

    if idrac_launch:
        current_launch_method = __salt__[chassis_cmd]('get_general', cfg_tuning, launch_cmd)
        if idrac_launch != current_launch_method:
            ret['changes'].update({'iDrac Launch Method':
                                  {'Old': current_launch_method,
                                   'New': idrac_launch}})

    if slot_names:
        current_slot_names = __salt__[chassis_cmd]('list_slotnames')
        for key, val in slot_names:
            current_slot_name = current_slot_names.get(key).get('slotname')
            if current_slot_name != val:
                old = {key: current_slot_name}
                new = {key: val}
                if ret['changes'].get('Slot Names') is None:
                    ret['changes'].update({'Slot Names':
                                          {'Old': {},
                                           'New': {}}})
                ret['changes']['Slot Names']['Old'].update(old)
                ret['changes']['Slot Names']['New'].update(new)

    # TODO: Refactor this and make DRY - can probable farm this out to a new funciton
    if blade_power_states:
        # TODO: Get the power state list working
        current_power_states = 'get a list of current power states'
        for key, val in blade_power_states:
            # TODO: Get the correct state infos
            current_power_state = current_power_states.get(key).get('state')
            # TODO: Don't just compare values, check if True should be "on" or "off" etc
            if current_power_state != val:
                old = {key: current_power_state}
                new = {key: val}
                if ret['changes'].get('Blade Power States') is None:
                    ret['changes'].update({'Blade Power States':
                                          {'Old': {},
                                           'New': {}}})
                ret['changes']['Blade Power States']['Old'].update(old)
                ret['changes']['Blade Power States']['New'].update(new)

    if ret['changes'] == {}:
        ret['comment'] = 'Dell chassis is already in the desired state.'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Dell chassis configuration will change.'
        return ret

    # Finally, set the necessary configurations on the chassis.
    name = __salt__[chassis_cmd]('set_chassis_name', name)
    if location:
        location = __salt__[chassis_cmd]('set_chassis_location', location)
    if mode:
        mode = __salt__[chassis_cmd]('set_general', cfg_tuning, mode_cmd, mode)
    if idrac_launch:
        idrac_launch = __salt__[chassis_cmd]('set_general', cfg_tuning, launch_cmd, idrac_launch)
    if slot_names:
        slot_rets = []
        for key, val in slot_names.iteritems():
            slot_name = val.get('slotname')
            slot_rets.append(__salt__[chassis_cmd]('set_slotname', key, slot_name))
        if any(slot_rets) is False:
            slot_names = False
        else:
            slot_names = True

    if any([name, location, mode, idrac_launch, slot_names]) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the Dell chassis.'

    ret['comment'] = 'Dell chassis was updated.'
    return ret


def dell_switch(name, ip=None, netmask=None, gateway=None, dhcp=None,
                password=None, snmp=None):
    '''
    Manage switches in a Dell Chassis.

    name
        The switch designation (e.g. switch-1, switch-2)

    ip
        The Static IP Address of the switch

    netmask
        The netmask for the static IP

    gateway
        The gateway for the static IP

    dhcp
        True: Enable DHCP
        False: Do not change DHCP setup
        (disabling DHCP is automatic when a static IP is set)

    password
        The access (root) password for the switch

    snmp
        The SNMP community string for the switch

    Example:

    .. code-block:: yaml

        my-dell-chassis:
          chassis.dell_switch:
            - switch: switch-1
            - ip: 192.168.1.1
            - netmask: 255.255.255.0
            - gateway: 192.168.1.254
            - dhcp: True
            - password: secret
            - snmp: public

    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    current_nic = __salt__['chassis.cmd']('network_info', module=name)
    if current_nic.get('retcode', 0) != 0:
        ret['result'] = False
        ret['comment'] = current_nic['stdout']
        return ret

    if ip or netmask or gateway:
        if not ip:
            ip = current_nic['Network']['IP Address']
        if not netmask:
            ip = current_nic['Network']['Subnet Mask']
        if not gateway:
            ip = current_nic['Network']['Gateway']

    if current_nic['Network']['DHCP Enabled'] == '0' and dhcp:
        ret['changes'].update({'DHCP': {'Old': {'DHCP Enabled': current_nic['Network']['DHCP Enabled']},
                                        'New': {'DHCP Enabled': dhcp}}})

    if ((ip or netmask or gateway) and not dhcp and (ip != current_nic['Network']['IP Address'] or
                                                             netmask != current_nic['Network']['Subnet Mask'] or
                                                             gateway != current_nic['Network']['Gateway'])):
        ret['changes'].update({'IP': {'Old': current_nic['Network'],
                                      'New': {'IP Address': ip,
                                              'Subnet Mask': netmask,
                                              'Gateway': gateway}}})

    if password:
        if 'New' not in ret['changes']:
            ret['changes']['New'] = {}
        ret['changes']['New'].update({'Password': '*****'})

    if snmp:
        if 'New' not in ret['changes']:
            ret['changes']['New'] = {}
        ret['changes']['New'].update({'SNMP': '*****'})

    if ret['changes'] == {}:
        ret['comment'] = 'Switch ' + name + ' is already in desired state'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Switch ' + name + ' configuration will change'
        return ret

    # Finally, set the necessary configurations on the chassis.
    dhcp_ret = net_ret = password_ret = snmp_ret = True
    if dhcp:
        dhcp_ret = __salt__['chassis.cmd']('set_niccfg', module=name, dhcp=dhcp)
    if ip or netmask or gateway:
        net_ret = __salt__['chassis.cmd']('set_niccfg', ip, netmask, gateway, module=name)
    if password:
        password_ret = __salt__['chassis.cmd']('deploy_password', 'root', password, module=name)

    if snmp:
        snmp_ret = __salt__['chassis.cmd']('deploy_snmp', password, module=name)

    if any([password_ret, snmp_ret, net_ret, dhcp_ret]) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the switch {0}.'.format(name)

    ret['comment'] = 'Dell chassis switch {0} was updated.'.format(name)
    return ret
