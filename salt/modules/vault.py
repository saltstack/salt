# -*- coding: utf-8 -*-
"""
Functions to interact with Hashicorp Vault.

:maintainer:    SaltStack
:maturity:      new
:platform:      all


:note: If you see the following error, you'll need to upgrade ``requests`` to atleast 2.4.2

.. code-block:: text

    <timestamp> [salt.pillar][CRITICAL][14337] Pillar render error: Failed to load ext_pillar vault: {'error': "request() got an unexpected keyword argument 'json'"}


:configuration: The salt-master must be configured to allow peer-runner
    configuration, as well as configuration for the module.

    Add this segment to the master configuration file, or
    /etc/salt/master.d/vault.conf:

    .. code-block:: yaml

        vault:
            url: https://vault.service.domain:8200
            verify: /etc/ssl/certs/ca-certificates.crt
            role_name: minion_role
            auth:
                method: approle
                role_id: 11111111-2222-3333-4444-1111111111111
                secret_id: 11111111-1111-1111-1111-1111111111111
            policies:
                - saltstack/minions
                - saltstack/minion/{minion}
                .. more policies
            keys:
                - n63/TbrQuL3xaIW7ZZpuXj/tIfnK1/MbVxO4vT3wYD2A
                - S9OwCvMRhErEA4NVVELYBs6w/Me6+urgUr24xGK44Uy3
                - F1j4b7JKq850NS6Kboiy5laJ0xY8dWJvB3fcwA+SraYl
                - 1cYtvjKJNDVam9c7HNqJUfINk4PYyAXIpjkpN/sIuzPv
                - 3pPK5X6vGtwLhNOFv1U2elahECz3HpRUfNXJFYLw6lid

    url
        Url to your Vault installation. Required.

    verify
        For details please see
        http://docs.python-requests.org/en/master/user/advanced/#ssl-cert-verification

        .. versionadded:: 2018.3.0

    role_name
        Role name for minion tokens created. If omitted, minion tokens will be
        created without any role, thus being able to inherit any master token
        policy (including token creation capabilities). Optional.

        For details please see:
        https://www.vaultproject.io/api/auth/token/index.html#create-token
        Example configuration:
        https://www.nomadproject.io/docs/vault-integration/index.html#vault-token-role-configuration

    auth
        Currently only token and approle auth types are supported. Required.

        Approle is the preferred way to authenticate with Vault as it provide
        some advanced options to control authentication process.
        Please visit Vault documentation for more info:
        https://www.vaultproject.io/docs/auth/approle.html

        The token must be able to create tokens with the policies that should be
        assigned to minions.

        You can still use the token auth via a OS environment variable via this
        config example:

        .. code-block:: yaml

           vault:
             url: https://vault.service.domain:8200
             auth:
               method: token
               token: sdb://osenv/VAULT_TOKEN
           osenv:
             driver: env

        And then export the VAULT_TOKEN variable in your OS:

        .. code-block:: bash

           export VAULT_TOKEN=11111111-1111-1111-1111-1111111111111

    policies
        Policies that are assigned to minions when requesting a token. These can
        either be static, eg saltstack/minions, or templated, eg
        ``saltstack/minion/{minion}``. ``{minion}`` is shorthand for grains[id].
        Grains are also available, for example like this:
        ``my-policies/{grains[os]}``

        If a template contains a grain which evaluates to a list, it will be
        expanded into multiple policies. For example, given the template
        ``saltstack/by-role/{grains[roles]}``, and a minion having these grains:

        .. code-block:: yaml

            grains:
                roles:
                    - web
                    - database

        The minion will have the policies ``saltstack/by-role/web`` and
        ``saltstack/by-role/database``. Note however that list members which do
        not have simple string representations, such as dictionaries or objects,
        do not work and will throw an exception. Strings and numbers are
        examples of types which work well.

        Optional. If policies is not configured, ``saltstack/minions`` and
        ``saltstack/{minion}`` are used as defaults.

    keys
        List of keys to use to unseal vault server with the vault.unseal runner.


    Add this segment to the master configuration file, or
    /etc/salt/master.d/peer_run.conf:

    .. code-block:: yaml

        peer_run:
            .*:
                - vault.generate_token

.. _vault-setup:
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

log = logging.getLogger(__name__)


def read_secret(path, key=None):
    """
    Return the value of key at path in vault, or entire secret

    Jinja Example:

    .. code-block:: jinja

        my-secret: {{ salt['vault'].read_secret('secret/my/secret', 'some-key') }}

    .. code-block:: jinja

        {% set supersecret = salt['vault'].read_secret('secret/my/secret') %}
        secrets:
            first: {{ supersecret.first }}
            second: {{ supersecret.second }}
    """
    log.debug("Reading Vault secret for %s at %s", __grains__["id"], path)
    try:
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("GET", url)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()["data"]

        if key is not None:
            return data[key]
        return data
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to read secret! %s: %s", type(err).__name__, err)
        return None


def write_secret(path, **kwargs):
    """
    Set secret at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.write_secret "secret/my/secret" user="foo" password="bar"
    """
    log.debug("Writing vault secrets for %s at %s", __grains__["id"], path)
    data = dict([(x, y) for x, y in kwargs.items() if not x.startswith("__")])
    try:
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("POST", url, json=data)
        if response.status_code == 200:
            return response.json()["data"]
        elif response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(err).__name__, err)
        return False


def write_raw(path, raw):
    """
    Set raw data at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.write_raw "secret/my/secret" '{"user":"foo","password": "bar"}'
    """
    log.debug("Writing vault secrets for %s at %s", __grains__["id"], path)
    try:
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("POST", url, json=raw)
        if response.status_code == 200:
            return response.json()["data"]
        elif response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(err).__name__, err)
        return False


def delete_secret(path):
    """
    Delete secret at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.delete_secret "secret/my/secret"
    """
    log.debug("Deleting vault secrets for %s in %s", __grains__["id"], path)
    try:
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("DELETE", url)
        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to delete secret! %s: %s", type(err).__name__, err)
        return False


def list_secrets(path):
    """
    List secret keys at the path in vault. The vault policy used must allow this.
    The path should end with a trailing slash.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.list_secrets "secret/my/"
    """
    log.debug("Listing vault secret keys for %s in %s", __grains__["id"], path)
    try:
        url = "v1/{0}".format(path)
        response = __utils__["vault.make_request"]("LIST", url)
        if response.status_code != 200:
            response.raise_for_status()
        return response.json()["data"]
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to list secrets! %s: %s", type(err).__name__, err)
        return None
