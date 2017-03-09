# -*- coding: utf-8 -*-
'''
Vault Pillar Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2016.11.0

This module allows pillar data to be stored in Hashicorp Vault.

Base configuration instructions are documented in the execution module docs.
Below are noted extra configuration required for the pillar module, but the base
configuration must also be completed.

After the base Vault configuration is created, add the configuration below to
the ext_pillar section in the Salt master configuration.

.. code-block:: yaml

    ext_pillar:
      - vault: path=secret/salt

Each key needs to have all the key-value pairs with the names you
require. Avoid naming every key 'password' as you they will collide:

.. code-block:: bash

    $ vault write secret/salt auth=my_password master=127.0.0.1

The above will result in two pillars being available, ``auth`` and ``master``.

You can then use normal pillar requests to get each key pair directly from
pillar root. Example:

.. code-block:: bash

    $ salt-ssh '*' pillar.get auth

Multiple Vault sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - vault: path=secret/salt
      - vault: path=secret/root
'''

# import python libs
from __future__ import absolute_import
import logging
import salt.utils

log = logging.getLogger(__name__)

__func_alias__ = {
    'set_': 'set'
}


def __virtual__():
    '''
    This module has no external dependencies
    '''
    return True


def ext_pillar(minion_id,  # pylint: disable=W0613
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Get pillar data from Vault for the configuration ``conf``.
    '''
    comps = conf.split()

    if not comps[0].startswith('path='):
        salt.utils.warn_until(
            'Oxygen',
            'The \'profile\' argument has been deprecated. Any parts up until '
            'and following the first "path=" are discarded'
        )
    paths = [comp for comp in comps if comp.startswith('path=')]
    if not paths:
        log.error('"{0}" is not a valid Vault ext_pillar config'.format(conf))
        return {}

    try:
        path = paths[0].replace('path=', '')
        url = 'v1/{0}'.format(path)
        response = __utils__['vault.make_request']('GET', url)
        if response.status_code != 200:
            response.raise_for_status()
        vault_pillar = response.json()['data']
    except KeyError:
        log.error('No such path in Vault: {0}'.format(path))
        vault_pillar = {}

    return vault_pillar
