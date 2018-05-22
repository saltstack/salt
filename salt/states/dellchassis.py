# -*- coding: utf-8 -*-
'''
Manage chassis via Salt Proxies.

.. versionadded:: 2015.8.2

Below is an example state that sets basic parameters:

.. code-block:: yaml

    my-dell-chassis:
      dellchassis.chassis:
        - chassis_name: my-dell-chassis
        - datacenter: dc-1-us
        - location: my-location
        - mode: 2
        - idrac_launch: 1
        - slot_names:
          - server-1: my-slot-name
          - server-2: my-other-slot-name
        - blade_power_states:
          - server-1: on
          - server-2: off
          - server-3: powercycle

However, it is possible to place the entire set of chassis configuration
data in pillar. Here's an example pillar structure:

.. code-block:: yaml

    proxy:
      host: 10.27.20.18
      admin_username: root
      fallback_admin_username: root
      passwords:
        - super-secret
        - old-secret
      proxytype: fx2

      chassis:
        name: fx2-1
        username: root
        password: saltstack1
        datacenter: london
        location: rack-1-shelf-3
        management_mode: 2
        idrac_launch: 0
        slot_names:
          - 'server-1': blade1
          - 'server-2': blade2

        servers:
          server-1:
            idrac_password: saltstack1
            ipmi_over_lan: True
            ip: 172.17.17.132
            netmask: 255.255.0.0
            gateway: 172.17.17.1
          server-2:
            idrac_password: saltstack1
            ipmi_over_lan: True
            ip: 172.17.17.2
            netmask: 255.255.0.0
            gateway: 172.17.17.1
          server-3:
            idrac_password: saltstack1
            ipmi_over_lan: True
            ip: 172.17.17.20
            netmask: 255.255.0.0
            gateway: 172.17.17.1
          server-4:
            idrac_password: saltstack1
            ipmi_over_lan: True
            ip: 172.17.17.2
            netmask: 255.255.0.0
            gateway: 172.17.17.1

        switches:
          switch-1:
            ip: 192.168.1.2
            netmask: 255.255.255.0
            gateway: 192.168.1.1
            snmp: nonpublic
            password: saltstack1
          switch-2:
            ip: 192.168.1.3
            netmask: 255.255.255.0
            gateway: 192.168.1.1
            snmp: nonpublic
            password: saltstack1

And to go with it, here's an example state that pulls the data from the
pillar stated above:

.. code-block:: yaml

    {% set details = pillar.get('proxy:chassis', {}) %}
    standup-step1:
      dellchassis.chassis:
        - name: {{ details['name'] }}
        - location: {{ details['location'] }}
        - mode: {{ details['management_mode'] }}
        - idrac_launch: {{ details['idrac_launch'] }}
        - slot_names:
          {% for entry details['slot_names'] %}
            - {{ entry.keys()[0] }}: {{ entry[entry.keys()[0]]  }}
          {% endfor %}

    blade_powercycle:
      dellchassis.chassis:
        - blade_power_states:
          - server-1: powercycle
          - server-2: powercycle
          - server-3: powercycle
          - server-4: powercycle

    # Set idrac_passwords for blades.  racadm needs them to be called 'server-x'
    {% for k, v in details['servers'].iteritems() %}
    {{ k }}:
      dellchassis.blade_idrac:
        - idrac_password: {{ v['idrac_password'] }}
    {% endfor %}

    # Set management ip addresses, passwords, and snmp strings for switches
    {% for k, v in details['switches'].iteritems() %}
    {{ k }}-switch-setup:
      dellchassis.switch:
        - name: {{ k }}
        - ip: {{ v['ip'] }}
        - netmask: {{ v['netmask'] }}
        - gateway: {{ v['gateway'] }}
        - password: {{ v['password'] }}
        - snmp: {{ v['snmp'] }}
    {% endfor %}

.. note::

    This state module relies on the dracr.py execution module, which runs racadm commands on
    the chassis, blades, etc. The racadm command runs very slowly and, depending on your state,
    the proxy minion return might timeout before the racadm commands have completed. If you
    are repeatedly seeing minions timeout after state calls, please use the ``-t`` CLI argument
    to increase the timeout variable.

    For example:

    .. code-block:: bash

        salt '*' state.sls my-dell-chasis-state-name -t 60

.. note::

    The Dell CMC units perform adequately but many iDRACs are **excruciatingly**
    slow.  Some functions can take minutes to execute.

'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging
import os

# Import Salt lobs
from salt.ext import six
from salt.exceptions import CommandExecutionError

# Get logging started
log = logging.getLogger(__name__)


def __virtual__():
    return 'chassis.cmd' in __salt__


def blade_idrac(name, idrac_password=None, idrac_ipmi=None,
                idrac_ip=None, idrac_netmask=None, idrac_gateway=None,
                idrac_dnsname=None,
                idrac_dhcp=None):
    '''
    Set parameters for iDRAC in a blade.

    :param idrac_password: Password to use to connect to the iDRACs directly
    (idrac_ipmi and idrac_dnsname must be set directly on the iDRAC.  They
    can't be set through the CMC.  If this password is present, use it
    instead of the CMC password)
    :param idrac_ipmi: Enable/Disable IPMI over LAN
    :param idrac_ip: Set IP address for iDRAC
    :param idrac_netmask: Set netmask for iDRAC
    :param idrac_gateway: Set gateway for iDRAC
    :param idrac_dhcp: Turn on DHCP for iDRAC (True turns on, False does nothing
      becaause setting a static IP will disable DHCP).
    :return: A standard Salt changes dictionary

    NOTE: If any of the IP address settings is configured, all of ip, netmask,
    and gateway must be present
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    if not idrac_password:
        (username, password) = __salt__['chassis.chassis_credentials']()
    else:
        password = idrac_password

    module_network = __salt__['chassis.cmd']('network_info', module=name)
    current_idrac_ip = module_network['Network']['IP Address']

    if idrac_ipmi is not None:
        if idrac_ipmi is True or idrac_ipmi == 1:
            idrac_ipmi = '1'
        if idrac_ipmi is False or idrac_ipmi == 0:
            idrac_ipmi = '0'
        current_ipmi = __salt__['dracr.get_general']('cfgIpmiLan', 'cfgIpmiLanEnable',
                                                     host=current_idrac_ip, admin_username='root',
                                                     admin_password=password)

        if current_ipmi != idrac_ipmi:
            ch = {'Old': current_ipmi, 'New': idrac_ipmi}
            ret['changes']['IPMI'] = ch

    if idrac_dnsname is not None:
        dnsret = __salt__['dracr.get_dns_dracname'](host=current_idrac_ip,
                                                    admin_username='root',
                                                    admin_password=password)
        current_dnsname = dnsret['[Key=iDRAC.Embedded.1#NIC.1]']['DNSRacName']
        if current_dnsname != idrac_dnsname:
            ch = {'Old': current_dnsname,
                  'New': idrac_dnsname}
            ret['changes']['DNSRacName'] = ch

    if idrac_dhcp is not None or idrac_ip or idrac_netmask or idrac_gateway:
        if idrac_dhcp is True or idrac_dhcp == 1:
            idrac_dhcp = 1
        else:
            idrac_dhcp = 0
        if six.text_type(module_network['Network']['DHCP Enabled']) == '0' and idrac_dhcp == 1:
            ch = {'Old': module_network['Network']['DHCP Enabled'],
                  'New': idrac_dhcp}
            ret['changes']['DRAC DHCP'] = ch

        if idrac_dhcp == 0 and all([idrac_ip, idrac_netmask, idrac_netmask]):
            current_network = __salt__['chassis.cmd']('network_info',
                                                      module=name)
            old_ipv4 = {}
            new_ipv4 = {}
            if current_network['Network']['IP Address'] != idrac_ip:
                old_ipv4['ip'] = current_network['Network']['IP Address']
                new_ipv4['ip'] = idrac_ip
            if current_network['Network']['Subnet Mask'] != idrac_netmask:
                old_ipv4['netmask'] = current_network['Network']['Subnet Mask']
                new_ipv4['netmask'] = idrac_netmask
            if current_network['Network']['Gateway'] != idrac_gateway:
                old_ipv4['gateway'] = current_network['Network']['Gateway']
                new_ipv4['gateway'] = idrac_gateway

            if new_ipv4 != {}:
                ret['changes']['Network'] = {}
                ret['changes']['Network']['Old'] = old_ipv4
                ret['changes']['Network']['New'] = new_ipv4

    if ret['changes'] == {}:
        ret['comment'] = 'iDRAC on blade is already in the desired state.'
        return ret

    if __opts__['test'] and ret['changes'] != {}:
        ret['result'] = None
        ret['comment'] = 'iDRAC on blade will change.'
        return ret

    if 'IPMI' in ret['changes']:
        ipmi_result = __salt__['dracr.set_general']('cfgIpmiLan',
                                                    'cfgIpmiLanEnable',
                                                    idrac_ipmi,
                                                    host=current_idrac_ip,
                                                    admin_username='root',
                                                    admin_password=password)
        if not ipmi_result:
            ret['result'] = False
            ret['changes']['IPMI']['success'] = False

    if 'DNSRacName' in ret['changes']:
        dnsracname_result = __salt__['dracr.set_dns_dracname'](idrac_dnsname,
            host=current_idrac_ip,
            admin_username='root',
            admin_password=password)
        if dnsracname_result['retcode'] == 0:
            ret['changes']['DNSRacName']['success'] = True
        else:
            ret['result'] = False
            ret['changes']['DNSRacName']['success'] = False
            ret['changes']['DNSRacName']['return'] = dnsracname_result

    if 'DRAC DHCP' in ret['changes']:
        dhcp_result = __salt__['chassis.cmd']('set_niccfg', dhcp=idrac_dhcp)
        if dhcp_result['retcode']:
            ret['changes']['DRAC DHCP']['success'] = True
        else:
            ret['result'] = False
            ret['changes']['DRAC DHCP']['success'] = False
            ret['changes']['DRAC DHCP']['return'] = dhcp_result

    if 'Network' in ret['changes']:
        network_result = __salt__['chassis.cmd']('set_niccfg', ip=idrac_ip,
                                                 netmask=idrac_netmask,
                                                 gateway=idrac_gateway,
                                                 module=name)
        if network_result['retcode'] == 0:
            ret['changes']['Network']['success'] = True
        else:
            ret['result'] = False
            ret['changes']['Network']['success'] = False
            ret['changes']['Network']['return'] = network_result

    return ret


def chassis(name, chassis_name=None, password=None, datacenter=None,
            location=None, mode=None, idrac_launch=None, slot_names=None,
            blade_power_states=None):
    '''
    Manage a Dell Chassis.

    chassis_name
        The name of the chassis.

    datacenter
        The datacenter in which the chassis is located

    location
        The location of the chassis.

    password
        Password for the chassis. Note: If this password is set for the chassis,
        the current implementation of this state will set this password both on
        the chassis and the iDrac passwords on any configured blades. If the
        password for the blades should be distinct, they should be set separately
        with the blade_idrac function.

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
        The names of the slots, provided as a list identified by
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
          dellchassis.chassis:
            - chassis_name: my-dell-chassis
            - location: my-location
            - datacenter: london
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
    ret = {'name': chassis_name,
           'chassis_name': chassis_name,
           'result': True,
           'changes': {},
           'comment': ''}

    chassis_cmd = 'chassis.cmd'
    cfg_tuning = 'cfgRacTuning'
    mode_cmd = 'cfgRacTuneChassisMgmtAtServer'
    launch_cmd = 'cfgRacTuneIdracDNSLaunchEnable'

    inventory = __salt__[chassis_cmd]('inventory')

    if idrac_launch:
        idrac_launch = six.text_type(idrac_launch)

    current_name = __salt__[chassis_cmd]('get_chassis_name')
    if chassis_name != current_name:
        ret['changes'].update({'Name':
                              {'Old': current_name,
                               'New': chassis_name}})

    current_dc = __salt__[chassis_cmd]('get_chassis_datacenter')
    if datacenter and datacenter != current_dc:
        ret['changes'].update({'Datacenter':
                                   {'Old': current_dc,
                                    'New': datacenter}})

    if password:
        ret['changes'].update({'Password':
                                   {'Old': '******',
                                     'New': '******'}})
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
        for s in slot_names:
            key = s.keys()[0]
            new_name = s[key]
            if key.startswith('slot-'):
                key = key[5:]

            current_slot_name = current_slot_names.get(key).get('slotname')
            if current_slot_name != new_name:
                old = {key: current_slot_name}
                new = {key: new_name}
                if ret['changes'].get('Slot Names') is None:
                    ret['changes'].update({'Slot Names':
                                          {'Old': {},
                                           'New': {}}})
                ret['changes']['Slot Names']['Old'].update(old)
                ret['changes']['Slot Names']['New'].update(new)

    current_power_states = {}
    target_power_states = {}
    if blade_power_states:
        for b in blade_power_states:
            key = b.keys()[0]
            status = __salt__[chassis_cmd]('server_powerstatus', module=key)
            current_power_states[key] = status.get('status', -1)
            if b[key] == 'powerdown':
                if current_power_states[key] != -1 and current_power_states[key]:
                    target_power_states[key] = 'powerdown'
            if b[key] == 'powerup':
                if current_power_states[key] != -1 and not current_power_states[key]:
                    target_power_states[key] = 'powerup'
            if b[key] == 'powercycle':
                if current_power_states[key] != -1 and not current_power_states[key]:
                    target_power_states[key] = 'powerup'
                if current_power_states[key] != -1 and current_power_states[key]:
                    target_power_states[key] = 'powercycle'
        for k, v in six.iteritems(target_power_states):
            old = {k: current_power_states[k]}
            new = {k: v}
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
    name = __salt__[chassis_cmd]('set_chassis_name', chassis_name)
    if location:
        location = __salt__[chassis_cmd]('set_chassis_location', location)
    pw_result = True
    if password:
        pw_single = True
        if __salt__[chassis_cmd]('change_password', username='root', uid=1,
                                   password=password):
            for blade in inventory['server']:
                pw_single = __salt__[chassis_cmd]('deploy_password',
                                                  username='root',
                                                  password=password,
                                                  module=blade)
                if not pw_single:
                    pw_result = False
        else:
            pw_result = False

    if datacenter:
        datacenter_result = __salt__[chassis_cmd]('set_chassis_datacenter',
                                                  datacenter)
    if mode:
        mode = __salt__[chassis_cmd]('set_general', cfg_tuning, mode_cmd, mode)
    if idrac_launch:
        idrac_launch = __salt__[chassis_cmd]('set_general', cfg_tuning, launch_cmd, idrac_launch)
    if ret['changes'].get('Slot Names') is not None:
        slot_rets = []
        for s in slot_names:
            key = s.keys()[0]
            new_name = s[key]
            if key.startswith('slot-'):
                key = key[5:]
            slot_rets.append(__salt__[chassis_cmd]('set_slotname', key, new_name))

        if any(slot_rets) is False:
            slot_names = False
        else:
            slot_names = True

    powerchange_all_ok = True
    for k, v in six.iteritems(target_power_states):
        powerchange_ok = __salt__[chassis_cmd]('server_power', v, module=k)
        if not powerchange_ok:
            powerchange_all_ok = False

    if any([name, location, mode, idrac_launch,
            slot_names, powerchange_all_ok]) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the Dell chassis.'

    ret['comment'] = 'Dell chassis was updated.'
    return ret


def switch(name, ip=None, netmask=None, gateway=None, dhcp=None,
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
          dellchassis.switch:
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
    try:
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
    except AttributeError:
        ret['changes'] = {}
        ret['comment'] = 'Something went wrong retrieving the switch details'
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
        snmp_ret = __salt__['chassis.cmd']('deploy_snmp', snmp, module=name)

    if any([password_ret, snmp_ret, net_ret, dhcp_ret]) is False:
        ret['result'] = False
        ret['comment'] = 'There was an error setting the switch {0}.'.format(name)

    ret['comment'] = 'Dell chassis switch {0} was updated.'.format(name)
    return ret


def _firmware_update(firmwarefile='', host='',
                     directory=''):
    '''
    Update firmware for a single host
    '''
    dest = os.path.join(directory, firmwarefile[7:])

    __salt__['cp.get_file'](firmwarefile, dest)

    username = __pillar__['proxy']['admin_user']
    password = __pillar__['proxy']['admin_password']
    __salt__['dracr.update_firmware'](dest,
                                      host=host,
                                      admin_username=username,
                                      admin_password=password)


def firmware_update(hosts=None, directory=''):
    '''
        State to update the firmware on host
        using the ``racadm`` command

        firmwarefile
            filename (string) starting with ``salt://``
        host
            string representing the hostname
            supplied to the ``racadm`` command
        directory
            Directory name where firmwarefile
            will be downloaded

    .. code-block:: yaml

        dell-chassis-firmware-update:
          dellchassis.firmware_update:
            hosts:
              cmc:
                salt://firmware_cmc.exe
              server-1:
                salt://firmware.exe
            directory: /opt/firmwares
    '''
    ret = {}
    ret.changes = {}
    success = True
    for host, firmwarefile in hosts:
        try:
            _firmware_update(firmwarefile, host, directory)
            ret['changes'].update({
                'host': {
                    'comment': 'Firmware update submitted for {0}'.format(host),
                    'success': True,
                }
            })
        except CommandExecutionError as err:
            success = False
            ret['changes'].update({
                'host': {
                    'comment': 'FAILED to update firmware for {0}'.format(host),
                    'success': False,
                    'reason': six.text_type(err),
                }
            })
    ret['result'] = success
    return ret
