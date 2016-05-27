# -*- coding: utf-8 -*-
'''
Vault Pillar Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: Carbon

This module allows pillar data to be stored in Hashicorp Vault.

The vault module requires a configuration profile to be configured in either
the minion or master configuration file. This profile requires very little. In
the example:

.. code-block:: yaml

    myvault:
      vault.host: 127.0.0.1
      vault.port: 8200
      vault.scheme: http  # Optional; default is https
      vault.token: 012356789abcdef  # Required, unless set in environment

``vault.host`` refers to the host that is hosting vault and ``vault.port``
refers to the port on that host. A vault token is also required. It may be set
statically, as above, or as an environment variable:

.. code-block:: bash

    $ export VAULT_TOKEN=0123456789abcdef

After the profile is created, configure the external pillar system to use it.
A path must also be specified so that vault knows where to look.

.. code-block:: yaml

    ext_pillar:
      - vault: my_vault_config path=secret/salt

Using these configuration profiles, multiple vault sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - vault: my_vault_config
      - vault: my_other_vault_config
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


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Check vault for all data
    '''
    comps = conf.split()

    profile = {}
    if comps[0]:
        profile_name = comps[0]
        profile = __opts__.get(profile_name, {})

    path = '/'
    if len(comps) > 1 and comps[1].startswith('path='):
        path = comps[1].replace('path=', '')

    try:
        pillar = salt.utils.vault.read_(path, profile=profile)
    except KeyError:
        log.error('No such path in vault profile {0}: {1}'.format(profile, path))
        pillar = {}

    return pillar
