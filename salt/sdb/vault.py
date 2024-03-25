"""
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

    password: sdb://myvault/secret/passwords/mypassword

In this URL, ``myvault`` refers to the configuration profile,
``secret/passwords`` is the path where the data resides, and ``mypassword`` is
the key of the data to return.

The above URI is analogous to running the following vault command:

.. code-block:: bash

    $ vault read -field=mypassword secret/passwords
"""

import logging

import salt.exceptions

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

    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]
        data = {"data": data}

    try:
        url = f"v1/{path}"
        response = __utils__["vault.make_request"]("POST", url, json=data)

        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(e).__name__, e)
        raise salt.exceptions.CommandExecutionError(e)


def get(key, profile=None):
    """
    Get a value from the vault service
    """
    if "?" in key:
        path, key = key.split("?")
    else:
        path, key = key.rsplit("/", 1)

    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]

    try:
        url = f"v1/{path}"
        response = __utils__["vault.make_request"]("GET", url)
        if response.status_code == 404:
            if version2["v2"]:
                path = version2["data"] + "/" + key
                url = f"v1/{path}"
                response = __utils__["vault.make_request"]("GET", url)
                if response.status_code == 404:
                    return None
            else:
                return None
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()["data"]

        if version2["v2"]:
            if key in data["data"]:
                return data["data"][key]
            else:
                return data["data"]
        else:
            if key in data:
                return data[key]
        return None
    except Exception as e:  # pylint: disable=broad-except
        log.error("Failed to read secret! %s: %s", type(e).__name__, e)
        raise salt.exceptions.CommandExecutionError(e)
