"""
Vault SDB Module

:maintainer:    SaltStack
:maturity:      New
:platform:      all

.. versionadded:: 2016.11.0

This module allows access to Hashicorp Vault using an ``sdb://`` URI.

Base configuration instructions are documented in the :ref:`execution module docs <vault-setup>`.
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

    password: sdb://myvault/secret/passwords/mypassword

In this URL, ``myvault`` refers to the configuration profile,
``secret/passwords`` is the path where the data resides, and ``mypassword`` is
the key of the data to return.

The above URI is analogous to running the following vault command:

.. code-block:: bash

    $ vault read -field=mypassword secret/passwords


Further configuration
---------------------
The following options can be set in the profile:

patch
    When writing data, partially update the secret instead of overwriting it completely.
    This is usually the expected behavior, since without this option,
    each secret path can only contain a single mapping key safely.
    Defaults to ``False`` for backwards-compatibility reasons.

    .. versionadded:: 3007.0
"""

import logging

import salt.exceptions
import salt.utils.vault as vault

log = logging.getLogger(__name__)

__func_alias__ = {"set_": "set"}


def set_(key, value, profile=None):
    """
    Set a key/value pair in the vault service
    """
    if "?" in key:
        path, key = key.split("?")
    else:
        path, key = key.rsplit("/", 1)
    data = {key: value}
    curr_data = {}
    profile = profile or {}

    if profile.get("patch"):
        try:
            # Patching only works on existing secrets.
            # Save the current data if patching is enabled
            # to write it back later, if any errors happen in patch_kv.
            # This also checks that the path exists, otherwise patching fails as well.
            curr_data = vault.read_kv(path, __opts__, __context__)
            vault.patch_kv(path, data, __opts__, __context__)
            return True
        except (vault.VaultNotFoundError, vault.VaultPermissionDeniedError):
            pass

    curr_data.update(data)
    try:
        vault.write_kv(path, data, __opts__, __context__)
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(err).__name__, err)
        raise salt.exceptions.CommandExecutionError(err) from err


def get(key, profile=None):
    """
    Get a value from the vault service
    """
    full_path = key
    if "?" in key:
        path, key = key.split("?")
    else:
        path, key = key.rsplit("/", 1)

    try:
        try:
            res = vault.read_kv(path, __opts__, __context__)
            if key in res:
                return res[key]
            return None
        except vault.VaultNotFoundError:
            return vault.read_kv(full_path, __opts__, __context__)
    except vault.VaultNotFoundError:
        return None
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to read secret! %s: %s", type(err).__name__, err)
        raise salt.exceptions.CommandExecutionError(err) from err
