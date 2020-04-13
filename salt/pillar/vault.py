# -*- coding: utf-8 -*-
"""
Vault Pillar Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2016.11.0

This module allows pillar data to be stored in Hashicorp Vault.

Base configuration instructions are documented in the :ref:`execution module docs <vault-setup>`.
Below are noted extra configuration required for the pillar module, but the base
configuration must also be completed.

After the base Vault configuration is created, add the configuration below to
the ext_pillar section in the Salt master configuration.

.. code-block:: yaml

    ext_pillar:
      - vault: path=secret/salt

Each key needs to have all the key-value pairs with the names you
require. Avoid naming every key 'password' as you they will collide:

If you want to nest results under a nesting_key name use the following format:

    ext_pillar:
      - vault:
          conf: path=secret/salt
          nesting_key: vault_key_name

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
      - vault: path=secret/minions/{minion}/pass

You can also use nesting here as well.  Identical nesting keys will get merged.

.. code-block:: yaml

    ext_pillar:
      - vault:
           conf: path=secret/salt
           nesting_key: keyname1
      - vault:
           conf: path=secret/root
           nesting_key: keyname1
      - vault:
           conf: path=secret/minions/{minion}/pass
           nesting_key: keyname2

The difference between the return with and without the nesting key is shown below.
This example takes the key value pairs returned from vault as follows:

path=secret/salt

Key             Value
---             -----
salt-passwd     badpasswd1

path=secret/root

Key             Value
---             -----
root-passwd     rootbadpasswd1

path=secret/minions/{minion}/pass

Key             Value
---             -----
minion-passwd   minionbadpasswd1


.. code-block:: yaml

    #Nesting Key not defined

    local:
        ----------
        salt-passwd:
            badpasswd1
        root-passwd:
            rootbadpasswd1
        minion-passwd:
            minionbadpasswd1

    #Nesting Key defined

    local:
        ----------
        keyname1:
            ----------
                salt-passwd:
                    badpasswd1
                root-passwd:
                    rootbadpasswd1
        keyname2:
            ----------
                minion-passwd:
                    minionbadpasswd1

"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    This module has no external dependencies
    """
    return True


def ext_pillar(
    minion_id,  # pylint: disable=W0613
    pillar,  # pylint: disable=W0613
    conf,
    nesting_key=None,
):
    """
    Get pillar data from Vault for the configuration ``conf``.
    """
    comps = conf.split()

    paths = [comp for comp in comps if comp.startswith("path=")]
    if not paths:
        log.error('"%s" is not a valid Vault ext_pillar config', conf)
        return {}

    vault_pillar = {}

    try:
        path = paths[0].replace("path=", "")
        path = path.format(**{"minion": minion_id})
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("GET", url)
        if response.status_code == 200:
            vault_pillar = response.json().get("data", {})
        else:
            log.info("Vault secret not found for: %s", path)
    except KeyError:
        log.error("No such path in Vault: %s", path)

    if nesting_key:
        vault_pillar = {nesting_key: vault_pillar}
    return vault_pillar
