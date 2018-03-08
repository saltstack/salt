# -*- coding: utf-8 -*-
'''
Vault SDB Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2016.11.0

This module allows access to Hashicorp Vault using an ``sdb://`` URI.

Base configuration instructions are documented in the execution module docs.
Below are noted extra configuration required for the sdb module, but the base
configuration must also be completed.

Like all sdb modules, the vault module requires a configuration profile to
be configured in either the minion configuration file or a pillar. This profile
requires only setting the ``driver`` parameter to ``vault``:

.. code-block:: yaml

    myvault:
      driver: vault

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
from __future__ import absolute_import, print_function, unicode_literals
import logging
import salt.exceptions

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def set_(key, value, profile=None):
    '''
    Set a key/value pair in the vault service
    '''
    comps = key.split('?')
    path = comps[0]
    key = comps[1]

    try:
        url = 'v1/{0}'.format(path)
        data = {key: value}
        response = __utils__['vault.make_request'](
            'POST',
            url,
            profile,
            json=data)

        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as e:
        log.error('Failed to write secret! %s: %s', type(e).__name__, e)
        raise salt.exceptions.CommandExecutionError(e)


def get(key, profile=None):
    '''
    Get a value from the vault service
    '''
    comps = key.split('?')
    path = comps[0]
    key = comps[1]

    try:
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('GET', url, profile)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()['data']

        return data[key]
    except Exception as e:
        log.error('Failed to read secret! %s: %s', type(e).__name__, e)
        raise salt.exceptions.CommandExecutionError(e)
