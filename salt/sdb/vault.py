# -*- coding: utf-8 -*-
'''
Vault Database Module

:maintainer:    SaltStack
:maturity:      New
:depends:       vault (Hashicorp)
:platform:      all

.. versionadded:: Carbon

This module allows access to Hashicorp Vault using an ``sdb://`` URI.

Like all sdb modules, the vault module requires a configuration profile to
be configured in either the minion or master configuration file. This profile
requires very little. In the example:

.. code-block:: yaml

    myvault:
      driver: vault
      vault.host: 127.0.0.1
      vault.port: 8200
      vault.scheme: http  # Default is https
      vault.token: 012356789abcdef  # Optional

The ``driver`` refers to the ``vault`` module, ``vault.host`` refers to the host
that is hosting vault and ``vault.port`` refers to the port on that host. A
vault token is also required. It may be set statically, as above, or as an
environment variable:

    export VAULT_TOKEN=0123456789abcdef

Once configured you can access data using a URL such as:

.. code-block:: yaml

    password: sdb://myvault/secret/passwords?mypassword

In this URL, ``myvault`` refers to the configuration profile,
``secret/passwords`` is the path where the data resides, and ``mypassword`` is
the key of the data to return.

The above URI is analogous to running the following vault command:

.. code-block:: bash

    $ vault read -field=mypassword secret/passwords
'''

# import python libs
from __future__ import absolute_import
import os
import logging
import json
import salt.utils.http
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    '''
    This module has no external dependencies
    '''
    return True


def _get_token(profile):
    '''
    Get a token and raise an error if it can't be found
    '''
    token = os.environ.get('VAULT_TOKEN', profile.get('vault.token'))
    if token is None:
        raise CommandExecutionError('A token was not configured')
    return token


def set_(key, value, profile=None):
    '''
    Set a key/value pair in the vault service
    '''
    token = _get_token(profile)

    comps = key.split('?')
    url = '{0}://{1}:{2}/v1/{3}'.format(
        profile.get('vault.scheme', 'https'),
        profile.get('vault.host'),
        profile.get('vault.port'),
        comps[0],
    )

    result = _query(
        url,
        'POST',
        _get_token(profile),
        data=json.dumps({comps[1]: value})
    )

    return get(key, profile)


def get(key, profile=None):
    '''
    Get a value from the vault service
    '''
    comps = key.split('?')
    url = '{0}://{1}:{2}/v1/{3}'.format(
        profile.get('vault.scheme', 'https'),
        profile.get('vault.host'),
        profile.get('vault.port'),
        comps[0],
    )

    result = _query(
        url,
        'GET',
        _get_token(profile),
        decode=True,
        decode_type='json',
    )

    value = result['dict'].get('data', {}).get(comps[1])
    if value is None:
        log.error('The key was not found')
    return value


def _query(url, method, token, **kwargs):
    '''
    Perform a query to Vault
    '''
    headers = {'X-Vault-Token': token}

    result = salt.utils.http.query(
        url,
        header_dict=headers,
        status=True,
        **kwargs
    )

    if result['status'] != 200:
        error = result.get(
            'error',
            'There was an error: status {0} returned'.format(result['status'])
        )
        log.error(error)
        raise CommandExecutionError(error)

    return result
