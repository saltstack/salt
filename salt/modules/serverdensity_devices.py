# -*- coding: utf-8 -*-
'''
Wrapper around Server Density API
========================
.. versionadded:: Helium
/inventory/devices - end-point
`Server Density API <https://apidocs.serverdensity.com/Inventory/Devices/Creating>`_
'''
import requests
import json
import logging

log = logging.getLogger(__name__)


def get_sd_auth(val, sd_auth_pillar_name='serverdensity'):
    '''
    Returns requested Server Density authentication value from pillar.

    .. versionadded:: Helium
    
    CLI Example:

        salt '*' serverdensity_devices.get_sd_auth <val>
    '''
    sd_pillar = __pillar__.get(sd_auth_pillar_name)
    log.debug('SD Pillar: {0}'.format(sd_pillar))
    if not sd_pillar:
        log.error('Cloud not load {0} pillar'.format(sd_auth_pillar_name))
        raise Exception('{0} pillar is required for authentication'.format(sd_auth_pillar_name))

    try:
        return sd_pillar[val]
    except KeyError:
        log.error('Cloud not find value {0} in pillar'.format(val))
        raise Exception('{0} value was not found in pillar'.format(val))


def _clean_salt_variables(params, variable_prefix="__"):
    '''
    Pops out variables from params which starts with `variable_prefix`.

    .. versionadded:: Helium
    '''
    map(params.pop, [k for k in params if k.startswith(variable_prefix)])
    return params


def create(name, **params):
    '''
    Function to create device in Server Density.
    Ref: https://apidocs.serverdensity.com/Inventory/Devices/Creating

    CLI Example::

        salt '*' serverdensity_devices.create lama
        salt '*' serverdensity_devices.create rich_lama group=lama_band installedRAM=32768

    .. versionadded:: Helium
    '''
    log.info('params: {0}'.format(params))
    params = _clean_salt_variables(params)

    params['name'] = name
    api_response = requests.post('https://api.serverdensity.io/inventory/devices/',
                                 params={'token': get_sd_auth('api_token')},
                                 data=params)
    log.debug('API Response: {0}'.format(api_response))
    log.debug('API Response content: {0}'.format(api_response.content))
    if api_response.status_code == 200:
        try:
            return json.loads(api_response.content)
        except ValueError:
            log.error('Could not parse API Response content: {0}'.format(api_response.content))
            raise Exception('Failed to create, API Response: {0}'.format(api_response))
    else:
        return None


def delete(device_id):
    '''
    Function to delete device from Server Density.
    Ref: https://apidocs.serverdensity.com/Inventory/Devices/Deleting

    CLI Example::

        salt '*' serverdensity_devices.delete 51f7eafcdba4bb235e000ae4

    .. versionadded:: Helium
    '''
    api_response = requests.delete("https://api.serverdensity.io/inventory/devices/" + device_id,
                                   params={'token': get_sd_auth('api_token')})
    log.debug('API Response: {0}'.format(api_response))
    log.debug('API Response content: {0}'.format(api_response.content))
    if api_response.status_code == 200:
        try:
            return json.loads(api_response.content)
        except ValueError:
            log.error('Could not parse API Response content: {0}'.format(api_response.content))
            raise Exception('Failed to create, API Response: {0}'.format(api_response))
    else:
        return None


def ls(**params):
    '''
    Function that lists devices in Server Density.
    If additional params are passed - will filter by those params.
    Ref: https://apidocs.serverdensity.com/Inventory/Devices/Listing
         https://apidocs.serverdensity.com/Inventory/Devices/Searching

    CLI Example::

        salt '*' serverdensity_devices.ls
        salt '*' serverdensity_devices.ls name=lama
        salt '*' serverdensity_devices.ls name=lama group=lama_band installedRAM=32768

    .. versionadded:: Helium
    '''
    params = _clean_salt_variables(params)

    endpoint = 'devices'

    # Change endpoint if there are params to filter by:
    if params:
        endpoint = 'resources'

    # Convert all ints to strings:
    for k, v in params.items():
        params[k] = str(v)

    api_response = requests.get('https://api.serverdensity.io/inventory/{0}'.format(endpoint),
                                params={'token': get_sd_auth('api_token'),
                                        'filter': json.dumps(params)})
    log.debug('API Response: {0}'.format(api_response))
    log.debug('API Response content: {0}'.format(api_response.content))
    if api_response.status_code == 200:
        try:
            return json.loads(api_response.content)
        except ValueError:
            log.error('Could not parse API Response content: {0}'.format(api_response.content))
            raise Exception('Failed to create, API Response: {0}'.format(api_response))
    else:
        return None


def update(device_id, **params):
    '''
    Function that updates device information in Server Density.
    Ref: https://apidocs.serverdensity.com/Inventory/Devices/Updating

    CLI Example::

        salt '*' serverdensity_devices.update 51f7eafcdba4bb235e000ae4 name=lama group=lama_band
        salt '*' serverdensity_devices.update 51f7eafcdba4bb235e000ae4 name=better_lama group=rock_lamas swapSpace=512

    .. versionadded:: Helium
    '''
    params = _clean_salt_variables(params)

    api_response = requests.put("https://api.serverdensity.io/inventory/devices/" + device_id,
                                params={'token': get_sd_auth('api_token')},
                                data=params)
    log.debug('API Response: {0}'.format(api_response))
    log.debug('API Response content: {0}'.format(api_response.content))
    if api_response.status_code == 200:
        try:
            return json.loads(api_response.content)
        except ValueError:
            log.error('Could not parse API Response content: {0}'.format(api_response.content))
            raise Exception('Failed to create, API Response: {0}'.format(api_response))
    else:
        return None


def install_agent(agent_key):
    '''
    Function downloads Server Density installation agent, and installs sd-agent with agent_key.

    CLI Example::

        salt '*' serverdensity_devices.install_agent c2bbdd6689ff46282bdaa07555641498

    .. versionadded:: Helium
    '''
    work_dir = '/tmp/'
    account_url = get_sd_auth('account_url')

    __salt__['cmd.run'](cmd='curl https://www.serverdensity.com/downloads/agent-install.sh > install.sh',
                        cwd=work_dir)
    __salt__['cmd.run'](cmd='chmod +x install.sh',
                        cwd=work_dir)
    return __salt__['cmd.run'](cmd='./install.sh -a {account_url} -k {agent_key}'.format(account_url=account_url,
                                                                                         agent_key=agent_key),
                               cwd=work_dir)
