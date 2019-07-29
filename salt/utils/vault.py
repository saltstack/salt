# -*- coding: utf-8 -*-
'''
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Utilities supporting modules for Hashicorp Vault. Configuration instructions are
documented in the execution module docs.
'''

from __future__ import absolute_import, print_function, unicode_literals
import base64
import logging
import requests

import salt.crypt
import salt.exceptions
import salt.utils.versions

log = logging.getLogger(__name__)
logging.getLogger("requests").setLevel(logging.WARNING)


# Load the __salt__ dunder if not already loaded (when called from utils-module)
__salt__ = None


def __virtual__():  # pylint: disable=expected-2-blank-lines-found-0
    try:
        global __salt__  # pylint: disable=global-statement
        if not __salt__:
            __salt__ = salt.loader.minion_mods(__opts__)
            return True
    except Exception as e:
        log.error("Could not load __salt__: %s", e)
        return False


def _get_token_and_url_from_master():
    '''
    Get a token with correct policies for the minion, and the url to the Vault
    service
    '''
    minion_id = __grains__['id']
    pki_dir = __opts__['pki_dir']

    # When rendering pillars, the module executes on the master, but the token
    # should be issued for the minion, so that the correct policies are applied
    if __opts__.get('__role', 'minion') == 'minion':
        private_key = '{0}/minion.pem'.format(pki_dir)
        log.debug('Running on minion, signing token request with key %s',
                  private_key)
        signature = base64.b64encode(salt.crypt.sign_message(
            private_key,
            minion_id
        ))
        result = __salt__['publish.runner'](
            'vault.generate_token',
            arg=[minion_id, signature]
        )
    else:
        private_key = '{0}/master.pem'.format(pki_dir)
        log.debug('Running on master, signing token request for %s with key %s',
                  minion_id, private_key)
        signature = base64.b64encode(salt.crypt.sign_message(
            private_key,
            minion_id
        ))
        result = __salt__['saltutil.runner'](
            'vault.generate_token',
            minion_id=minion_id,
            signature=signature,
            impersonated_by_master=True
        )

    if not result:
        log.error('Failed to get token from master! No result returned - '
                  'is the peer publish configuration correct?')
        raise salt.exceptions.CommandExecutionError(result)
    if not isinstance(result, dict):
        log.error('Failed to get token from master! '
                  'Response is not a dict: %s', result)
        raise salt.exceptions.CommandExecutionError(result)
    if 'error' in result:
        log.error('Failed to get token from master! '
                  'An error was returned: %s', result['error'])
        raise salt.exceptions.CommandExecutionError(result)
    return {
        'url': result['url'],
        'token': result['token'],
        'verify': result.get('verify', None),
    }


def get_vault_connection():
    '''
    Get the connection details for calling Vault, from local configuration if
    it exists, or from the master otherwise
    '''
    def _use_local_config():
        log.debug('Using Vault connection details from local config')
        try:
            if __opts__['vault']['auth']['method'] == 'approle':
                verify = __opts__['vault'].get('verify', None)
                if _selftoken_expired():
                    log.debug('Vault token expired. Recreating one')
                    # Requesting a short ttl token
                    url = '{0}/v1/auth/approle/login'.format(__opts__['vault']['url'])
                    payload = {'role_id': __opts__['vault']['auth']['role_id']}
                    if 'secret_id' in __opts__['vault']['auth']:
                        payload['secret_id'] = __opts__['vault']['auth']['secret_id']
                    response = requests.post(url, json=payload, verify=verify)
                    if response.status_code != 200:
                        errmsg = 'An error occured while getting a token from approle'
                        raise salt.exceptions.CommandExecutionError(errmsg)
                    __opts__['vault']['auth']['token'] = response.json()['auth']['client_token']
            if __opts__['vault']['auth']['method'] == 'wrapped_token':
                verify = __opts__['vault'].get('verify', None)
                if _wrapped_token_valid():
                    url = '{0}/v1/sys/wrapping/unwrap'.format(__opts__['vault']['url'])
                    headers = {'X-Vault-Token': __opts__['vault']['auth']['token']}
                    response = requests.post(url, headers=headers, verify=verify)
                    if response.status_code != 200:
                        errmsg = 'An error occured while unwrapping vault token'
                        raise salt.exceptions.CommandExecutionError(errmsg)
                    __opts__['vault']['auth']['token'] = response.json()['auth']['client_token']
            return {
                'url': __opts__['vault']['url'],
                'token': __opts__['vault']['auth']['token'],
                'verify': __opts__['vault'].get('verify', None)
            }
        except KeyError as err:
            errmsg = 'Minion has "vault" config section, but could not find key "{0}" within'.format(err.message)
            raise salt.exceptions.CommandExecutionError(errmsg)

    if 'vault' in __opts__ and __opts__.get('__role', 'minion') == 'master':
        if 'id' in __grains__:
            log.debug('Contacting master for Vault connection details')
            return _get_token_and_url_from_master()
        else:
            return _use_local_config()
    elif any((__opts__['local'], __opts__['file_client'] == 'local', __opts__['master_type'] == 'disable')):
        return _use_local_config()
    else:
        log.debug('Contacting master for Vault connection details')
        return _get_token_and_url_from_master()


def make_request(method, resource, token=None, vault_url=None, get_token_url=False, **args):
    '''
    Make a request to Vault
    '''
    if not token or not vault_url:
        connection = get_vault_connection()
        token, vault_url = connection['token'], connection['url']
        if 'verify' not in args:
            args['verify'] = connection['verify']

    url = "{0}/{1}".format(vault_url, resource)
    headers = {'X-Vault-Token': token, 'Content-Type': 'application/json'}
    response = requests.request(method, url, headers=headers, **args)

    if get_token_url:
        return response, token, vault_url
    else:
        return response


def _selftoken_expired():
    '''
    Validate the current token exists and is still valid
    '''
    try:
        verify = __opts__['vault'].get('verify', None)
        url = '{0}/v1/auth/token/lookup-self'.format(__opts__['vault']['url'])
        if 'token' not in __opts__['vault']['auth']:
            return True
        headers = {'X-Vault-Token': __opts__['vault']['auth']['token']}
        response = requests.get(url, headers=headers, verify=verify)
        if response.status_code != 200:
            return True
        return False
    except Exception as e:
        raise salt.exceptions.CommandExecutionError(
            'Error while looking up self token : {0}'.format(e)
        )


def _wrapped_token_valid():
    '''
    Validate the wrapped token exists and is still valid
    '''
    try:
        verify = __opts__['vault'].get('verify', None)
        url = '{0}/v1/sys/wrapping/lookup'.format(__opts__['vault']['url'])
        if 'token' not in __opts__['vault']['auth']:
            return False
        headers = {'X-Vault-Token': __opts__['vault']['auth']['token']}
        response = requests.post(url, headers=headers, verify=verify)
        if response.status_code != 200:
            return False
        return True
    except Exception as e:
        raise salt.exceptions.CommandExecutionError(
            'Error while looking up wrapped token : {0}'.format(e)
        )


def is_v2(path):
    '''
    Determines if a given secret path is kv version 1 or 2

    CLI Example:

    .. code-block:: bash

        salt '*' vault.is_v2 "secret/my/secret"
    '''
    ret = {'v2': False, 'data': path, 'metadata': path, 'type': None}
    path_metadata = _get_secret_path_metadata(path)
    ret['type'] = path_metadata.get('type', 'kv')
    if ret['type'] == 'kv' and path_metadata.get('options', {}).get('version', '1') in ['2']:
        ret['v2'] = True
        ret['data'] = _v2_the_path(path, path_metadata.get('path', path))
        ret['metadata'] = _v2_the_path(path, path_metadata.get('path', path), 'metadata')
    return ret


def _v2_the_path(path, pfilter, ptype='data'):
    '''
    Given a path, a filter, and a path type, properly inject 'data' or 'metadata' into the path

    CLI Example:

    .. code-block:: python

        _v2_the_path('dev/secrets/fu/bar', 'dev/secrets', 'data') => 'dev/secrets/data/fu/bar'
    '''
    possible_types = ['data', 'metadata']
    assert ptype in possible_types
    msg = "Path {} already contains {} in the right place - saltstack duct tape?".format(path, ptype)

    path = path.rstrip('/').lstrip('/')
    pfilter = pfilter.rstrip('/').lstrip('/')

    together = pfilter + '/' + ptype

    otype = possible_types[0] if possible_types[0] != ptype else possible_types[1]
    other = pfilter + '/' + otype
    if path.startswith(other):
        path = path.replace(other, together, 1)
        msg = 'Path is a "{}" type but "{}" type requested - Flipping: {}'.format(otype, ptype, path)
    elif not path.startswith(together):
        msg = "Converting path to v2 {} => {}".format(path, path.replace(pfilter, together, 1))
        path = path.replace(pfilter, together, 1)

    log.debug(msg)
    return path


def _get_secret_path_metadata(path):
    '''
    Given a path query vault to determine where the mount point is, it's type and version

    CLI Example:

    .. code-block:: python

        _get_secret_path_metadata('dev/secrets/fu/bar')
    '''
    ckey = 'vault_secret_path_metadata'
    if ckey not in __context__:
        __context__[ckey] = {}

    ret = None
    if path.startswith(tuple(__context__[ckey].keys())):
        log.debug('Found cached metadata for %s in %s', __grains__['id'], path)
        ret = next(v for k, v in __context__[ckey].items() if path.startswith(k))
    else:
        log.debug('Fetching metadata for %s in %s', __grains__['id'], path)
        try:
            url = 'v1/sys/internal/ui/mounts/{0}'.format(path)
            response = make_request('GET', url)
            if response.ok:
                response.raise_for_status()
            if response.json().get('data', False):
                log.debug('Got metadata for %s in %s', __grains__['id'], path)
                ret = response.json()['data']
                __context__[ckey][path] = ret
            else:
                raise response.json()
        except Exception as err:
            log.error('Failed to list secrets! %s: %s', type(err).__name__, err)
    return ret
