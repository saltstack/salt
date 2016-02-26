# -*- coding: utf-8 -*-
'''
Vault SDB Module

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
import logging
import salt.utils.vault

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    '''
    This module has no external dependencies
    '''
    return True


def set_(key, value, profile=None):
    '''
    Set a key/value pair in the vault service
    '''
    comps = key.split('?')
    path = comps[0]
    key = comps[1]
    return salt.utils.vault.write_(path, key, value, profile=profile)


def get(key, profile=None):
    '''
    Get a value from the vault service
    '''
    comps = key.split('?')
    path = comps[0]
    key = comps[1]
    return salt.utils.vault.read_(path, key, profile=profile)
