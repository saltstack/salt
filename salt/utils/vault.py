# -*- coding: utf-8 -*-
'''
Vault Connection Functions

:maintainer:    SaltStack
:maturity:      New
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
      vault.scheme: http  # Optional; default is https
      vault.token: 012356789abcdef  # Required, unless set in environment

The ``driver`` refers to the ``vault`` module, ``vault.host`` refers to the host
that is hosting vault and ``vault.port`` refers to the port on that host. A
vault token is also required. It may be set statically, as above, or as an
environment variable:

.. code-block:: bash

    $ export VAULT_TOKEN=0123456789abcdef

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


def _get_token(profile):
    '''
    Get a token and raise an error if it can't be found
    '''
    token = os.environ.get('VAULT_TOKEN', profile.get('vault.token'))
    if token is None:
        raise CommandExecutionError('A token was not configured')
    return token


def write_(path, key, value, profile=None):
    '''
    Set a key/value pair in the vault service
    '''
    result = _query(
        'POST',
        path,
        profile=profile,
        data=json.dumps({key: value}),
    )

    return read_(path, key, profile)


def read_(path, key=None, profile=None):
    '''
    Get a value from the vault service
    '''
    result = _query(
        'GET',
        path,
        profile=profile,
        decode=True,
        decode_type='json',
    )

    data = result['dict'].get('data', {})
    if key is None:
        return data

    value = data.get(key)
    if value is None:
        log.error('The key was not found')
    return value


def _query(method, path, profile=None, **kwargs):
    '''
    Perform a query to Vault
    '''
    token = _get_token(profile)
    headers = {'X-Vault-Token': token}

    url = '{0}://{1}:{2}/v1/{3}'.format(
        profile.get('vault.scheme', 'https'),
        profile.get('vault.host'),
        profile.get('vault.port'),
        path,
    )

    result = salt.utils.http.query(
        url,
        method,
        header_dict=headers,
        status=True,
        **kwargs
    )

    if not str(result['status']).startswith('2'):
        # This includes 200 and 204, both of which are a success
        error = result.get(
            'error',
            'There was an error: status {0} returned'.format(result['status'])
        )
        log.error(error)
        raise CommandExecutionError(error)

    return result
