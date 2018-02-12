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
import os
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
            'verify': result['verify'],
           }


def _get_vault_connection():
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
            return {
                'url': __opts__['vault']['url'],
                'token': __opts__['vault']['auth']['token'],
                'verify': __opts__['vault'].get('verify', None)
            }
        except KeyError as err:
            errmsg = 'Minion has "vault" config section, but could not find key "{0}" within'.format(err.message)
            raise salt.exceptions.CommandExecutionError(errmsg)

    if 'vault' in __opts__ and __opts__.get('__role', 'minion') == 'master':
        return _use_local_config()
    elif any((__opts__['local'], __opts__['file_client'] == 'local', __opts__['master_type'] == 'disable')):
        return _use_local_config()
    else:
        log.debug('Contacting master for Vault connection details')
        return _get_token_and_url_from_master()


def make_request(method, resource, profile=None, **args):
    '''
    Make a request to Vault
    '''
    if profile is not None and profile.keys().remove('driver') is not None:
        # Deprecated code path
        return make_request_with_profile(method, resource, profile, **args)

    connection = _get_vault_connection()
    token, vault_url = connection['token'], connection['url']
    if 'verify' not in args:
        args['verify'] = connection['verify']

    url = "{0}/{1}".format(vault_url, resource)
    headers = {'X-Vault-Token': token, 'Content-Type': 'application/json'}
    response = requests.request(method, url, headers=headers, **args)

    return response


def make_request_with_profile(method, resource, profile, **args):
    '''
    DEPRECATED! Make a request to Vault, with a profile including connection
    details.
    '''
    salt.utils.versions.warn_until(
        'Fluorine',
        'Specifying Vault connection data within a \'profile\' has been '
        'deprecated. Please see the documentation for details on the new '
        'configuration schema. Support for this function will be removed '
        'in Salt Fluorine.'
    )
    url = '{0}://{1}:{2}/v1/{3}'.format(
        profile.get('vault.scheme', 'https'),
        profile.get('vault.host'),
        profile.get('vault.port'),
        resource,
    )
    token = os.environ.get('VAULT_TOKEN', profile.get('vault.token'))
    if token is None:
        raise salt.exceptions.CommandExecutionError('A token was not configured')

    headers = {'X-Vault-Token': token, 'Content-Type': 'application/json'}
    response = requests.request(method, url, headers=headers, **args)

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
