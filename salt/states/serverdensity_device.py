# -*- coding: utf-8 -*-
'''
Monitor Server with Server Density
========================

`Server Density <https://www.serverdensity.com/>`_
Is a hosted monitoring service.

.. warning::

    This state module is beta. It might be changed later to include more or less automation.

.. note::
    This state modules requires a pillar for authentication with Server Density:
      .. code-block:: yaml

    serverdensity:
        api_token: "b97da80a41c4f61bff05975ee51eb1aa"
        account_url: "https://your-account.serverdensity.io"

.. note::
    Although Server Density allows duplicate device names in its database,
    this module will raise exception if you try monitoring devices with the same name.
    It is easier to managed this way and adds some `saltiness` to the module.


.. to-do::
    Add a plugin support.
    Add notification support

Available Functions
-------------------

- monitored

  .. code-block:: yaml
        'server_name':
          serverdensity_device.monitored

'''

import logging

log = logging.getLogger(__name__)


def get_salt_params():
    '''
    Try to get all sort of parameters for Server Density server info.
    Ref: https://apidocs.serverdensity.com/Inventory/Devices/Creating
    Note:
        Missing publicDNS and publicIPs parameters.
        There might be way of getting them with salt-cloud.
    '''
    all_stats = __salt__['status.all_status']()
    all_grains = __salt__['grains.items']()
    params = {}
    try:
        params['name'] = all_grains['id']
        params['hostname'] = all_grains['host']
        params['os'] = all_grains['os']
        params['cpuCores'] = all_stats['cpuinfo']['cpu cores']
        params['installedRAM'] = str(int(all_stats['meminfo']['MemTotal']['value']) / 1024)
        params['swapSpace'] = str(int(all_stats['meminfo']['SwapTotal']['value']) / 1024)
        params['privateIPs'] = all_grains['fqdn_ip4']
        params['privateDNS'] = all_grains['fqdn']
    except:
        pass

    return params


def monitored(name, group=None, salt_name=True, salt_params=True, **params):
    '''
    Device is monitored with Server Density.

    name
        Device name in Server Density.

    salt_name
        True (default): take name from grains['id'].
        False: use name provided.

    group
        Group name under with device will appear in Server Density dashboard.
        Default - `None`.

    salt_params
        True (default): will take some parameters from grains and status.all_status execution module.
        False: will not take any parameters.

    params
        Add parameters that you want to appear in the Server Density dashboard.
        Will overwrite the `salt_params` parameters.
        Ref: `https://apidocs.serverdensity.com/Inventory/Devices/Creating`

    Usage example

        .. code-block:: yaml
            'server_name':
              serverdensity_device.monitored

        .. code-block:: yaml
            'server_name':
              serverdensity_device.monitored:
                - group: web-servers

        .. code-block:: yaml
            'my_special_server':
              serverdensity_device.monitored:
                - salt_name: False
                - group: web-servers
                - cpuCores: 2
                - os: CentOS

    '''
    ret = {'name': name, 'changes': {}, 'result': None, 'comment': ''}
    params_from_salt = get_salt_params()

    if salt_name:
        name = params_from_salt.pop('name')
        ret['name'] = name

    if group:
        params['group'] = group

    # override salt_params with given params,
    if salt_params:
        for k, v in params.items():
            params_from_salt[k] = v
        params_to_use = params_from_salt
    else:
        params_to_use = params

    device_in_sd = True if __salt__['serverdensity_devices.ls'](name=name) else False
    sd_agent_installed = True if 'sd-agent' in __salt__['pkg.list_pkgs']() else False

    if device_in_sd and sd_agent_installed:
        ret['result'] = True
        ret['comment'] = 'Such server name already exists in this Server Density account. And sd-agent is installed'
        ret['changes'] = {}
        return ret

    if not device_in_sd:
        device = __salt__['serverdensity_devices.create'](name, **params_from_salt)
        agent_key = device['agentKey']
        ret['comment'] = 'Device created in Server Density db.'
        ret['changes'] = {'device_created': device}
    elif device_in_sd:
        device = __salt__['serverdensity_devices.ls'](name=name)[0]
        agent_key = device['agentKey']
        ret['comment'] = 'Device was already in Server Density db.'
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to create device in Server Density DB and this device does not exist in db either.'
        ret['changes'] = {}
        return ret

    installed_agent = __salt__['serverdensity_devices.install_agent'](agent_key) 

    ret['result'] = True
    ret['comment'] = 'Successfully installed agent and created device in Server Density db.'
    ret['changes'] = {'created_device': device, 'installed_agent': installed_agent}
    return ret

