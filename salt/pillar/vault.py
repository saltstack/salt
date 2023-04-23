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

.. code-block:: yaml

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
      - vault: path=secret/roles/{pillar[roles]}/pass

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

.. code-block:: text

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

.. versionadded:: 3006.0

    Pillar values from previously rendered pillars can be used to template
    vault ext_pillar paths.

Using pillar values to template vault pillar paths requires them to be defined
before the vault ext_pillar is called. Especially consider the significancy
of :conf_master:`ext_pillar_first <ext_pillar_first>` master config setting.

If a pillar pattern matches multiple paths, the results are merged according to
the master configuration values :conf_master:`pillar_source_merging_strategy <pillar_source_merging_strategy>`
and :conf_master:`pillar_merge_lists <pillar_merge_lists>` by default.

If the optional nesting_key was defined, the merged result will be nested below.
There is currently no way to nest multiple results under different keys.

You can override the merging behavior per defined ext_pillar:

.. code-block:: yaml

    ext_pillar:
      - vault:
           conf: path=secret/roles/{pillar[roles]}
           merge_strategy: smart
           merge_lists: false
"""


import logging

from requests.exceptions import HTTPError

import salt.utils.dictupdate

log = logging.getLogger(__name__)


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
    merge_strategy=None,
    merge_lists=None,
    extra_minion_data=None,
):
    """
    Get pillar data from Vault for the configuration ``conf``.
    """
    extra_minion_data = extra_minion_data or {}
    if extra_minion_data.get("_vault_runner_is_compiling_pillar_templates"):
        # Disable vault ext_pillar while compiling pillar for vault policy templates
        return {}

    comps = conf.split()

    paths = [comp for comp in comps if comp.startswith("path=")]
    if not paths:
        log.error('"%s" is not a valid Vault ext_pillar config', conf)
        return {}

    merge_strategy = merge_strategy or __opts__.get(
        "pillar_source_merging_strategy", "smart"
    )
    merge_lists = merge_lists or __opts__.get("pillar_merge_lists", False)
    vault_pillar = {}

    path_pattern = paths[0].replace("path=", "")
    for path in _get_paths(path_pattern, minion_id, pillar):
        try:
            version2 = __utils__["vault.is_v2"](path)
            if version2["v2"]:
                path = version2["data"]

            url = "v1/{}".format(path)
            response = __utils__["vault.make_request"]("GET", url)
            response.raise_for_status()
            vault_pillar_single = response.json().get("data", {})

            if vault_pillar_single and version2["v2"]:
                vault_pillar_single = vault_pillar_single["data"]

            vault_pillar = salt.utils.dictupdate.merge(
                vault_pillar,
                vault_pillar_single,
                strategy=merge_strategy,
                merge_lists=merge_lists,
            )
        except HTTPError:
            log.info("Vault secret not found for: %s", path)

    if nesting_key:
        vault_pillar = {nesting_key: vault_pillar}
    return vault_pillar


def _get_paths(path_pattern, minion_id, pillar):
    """
    Get the paths that should be merged into the pillar dict
    """
    mappings = {"minion": minion_id, "pillar": pillar}

    paths = []
    try:
        for expanded_pattern in __utils__["vault.expand_pattern_lists"](
            path_pattern, **mappings
        ):
            paths.append(expanded_pattern.format(**mappings))
    except KeyError:
        log.warning("Could not resolve pillar path pattern %s", path_pattern)

    log.debug(f"{minion_id} vault pillar paths: {paths}")
    return paths
