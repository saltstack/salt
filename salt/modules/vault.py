"""
Functions to interact with Hashicorp Vault.

:maintainer:    SaltStack
:maturity:      new
:platform:      all


:note: If you see the following error, you'll need to upgrade ``requests`` to at least 2.4.2

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
            namespace:  vault_enterprice_namespace
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
        https://requests.readthedocs.io/en/master/user/advanced/#ssl-cert-verification

        .. versionadded:: 2018.3.0

    namespaces
        Optional Vault Namespace. Used with Vault enterprice

        For detail please see:
        https://www.vaultproject.io/docs/enterprise/namespaces

        .. versionadded:: 3004

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

        Configuration keys ``uses`` or ``ttl`` may also be specified under ``auth``
        to configure the tokens generated on behalf of minions to be reused for the
        defined number of uses or length of time in seconds. These settings may also be configured
        on the minion when ``allow_minion_override`` is set to ``True`` in the master
        config.

        Defining ``uses`` will cause the salt master to generate a token with that number of uses rather
        than a single use token. This multi-use token will be cached on the minion. The type of minion
        cache can be specified with ``token_backend: session`` or ``token_backend: disk``. The value of
        ``session`` is the default, and will store the vault information in memory only for that session.
        The value of ``disk`` will write to an on disk file, and persist between state runs (most
        helpful for multi-use tokens).

        .. code-block:: bash

          vault:
            auth:
              method: token
              token: xxxxxx
              uses: 10
              ttl: 43200
              allow_minion_override: True
              token_backend: disk

            .. versionchanged:: 3001

    policies
        Policies that are assigned to minions when requesting a token. These
        can either be static, eg ``saltstack/minions``, or templated with grain
        values, eg ``my-policies/{grains[os]}``. ``{minion}`` is shorthand for
        ``grains[id]``, eg ``saltstack/minion/{minion}``.

        .. important::

            See :ref:`Is Targeting using Grain Data Secure?
            <faq-grain-security>` for important security information. In short,
            everything except ``grains[id]`` is minion-controlled.

        If a template contains a grain which evaluates to a list, it will be
        expanded into multiple policies. For example, given the template
        ``saltstack/by-role/{grains[roles]}``, and a minion having these grains:

        .. code-block:: yaml

            grains:
                roles:
                    - web
                    - database

        The minion will have the policies ``saltstack/by-role/web`` and
        ``saltstack/by-role/database``.

        .. note::

            List members which do not have simple string representations,
            such as dictionaries or objects, do not work and will
            throw an exception. Strings and numbers are examples of
            types which work well.

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
import logging
import os

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def read_secret(path, key=None, metadata=False, default=CommandExecutionError):
    """
    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    Return the value of key at path in vault, or entire secret

    :param metadata: Optional - If using KV v2 backend, display full results, including metadata

        .. versionadded:: 3001

    Jinja Example:

    .. code-block:: jinja

        my-secret: {{ salt['vault'].read_secret('secret/my/secret', 'some-key') }}

        {{ salt['vault'].read_secret('/secret/my/secret', 'some-key', metadata=True)['data'] }}

    .. code-block:: jinja

        {% set supersecret = salt['vault'].read_secret('secret/my/secret') %}
        secrets:
            first: {{ supersecret.first }}
            second: {{ supersecret.second }}
    """
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]
    log.debug("Reading Vault secret for %s at %s", __grains__["id"], path)
    try:
        url = "v1/{}".format(path)
        response = __utils__["vault.make_request"]("GET", url)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()["data"]

        # Return data of subkey if requested
        if key is not None:
            if version2["v2"]:
                return data["data"][key]
            else:
                return data[key]
        # Just return data from KV V2 if metadata isn't needed
        if version2["v2"]:
            if not metadata:
                return data["data"]

        return data
    except Exception as err:  # pylint: disable=broad-except
        if default is CommandExecutionError:
            raise CommandExecutionError(
                "Failed to read secret! {}: {}".format(type(err).__name__, err)
            )
        return default


def write_secret(path, **kwargs):
    """
    Set secret at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.write_secret "secret/my/secret" user="foo" password="bar"
    """
    log.debug("Writing vault secrets for %s at %s", __grains__["id"], path)
    data = {x: y for x, y in kwargs.items() if not x.startswith("__")}
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]
        data = {"data": data}
    try:
        url = "v1/{}".format(path)
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
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]
        raw = {"data": raw}
    try:
        url = "v1/{}".format(path)
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
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["data"]
    try:
        url = "v1/{}".format(path)
        response = __utils__["vault.make_request"]("DELETE", url)
        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to delete secret! %s: %s", type(err).__name__, err)
        return False


def destroy_secret(path, *args):
    """
    .. versionadded:: 3001

    Destroy specified secret version at the path in vault. The vault policy
    used must allow this. Only supported on Vault KV version 2

    CLI Example:

    .. code-block:: bash

        salt '*' vault.destroy_secret "secret/my/secret" 1 2
    """
    log.debug("Destroying vault secrets for %s in %s", __grains__["id"], path)
    data = {"versions": list(args)}
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["destroy"]
    else:
        log.error("Destroy operation is only supported on KV version 2")
        return False
    try:
        url = "v1/{}".format(path)
        response = __utils__["vault.make_request"]("POST", url, json=data)
        if response.status_code != 204:
            response.raise_for_status()
        return True
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to delete secret! %s: %s", type(err).__name__, err)
        return False


def list_secrets(path, default=CommandExecutionError):
    """
    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    List secret keys at the path in vault. The vault policy used must allow this.
    The path should end with a trailing slash.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.list_secrets "secret/my/"
    """
    log.debug("Listing vault secret keys for %s in %s", __grains__["id"], path)
    version2 = __utils__["vault.is_v2"](path)
    if version2["v2"]:
        path = version2["metadata"]
    try:
        url = "v1/{}".format(path)
        response = __utils__["vault.make_request"]("LIST", url)
        if response.status_code != 200:
            response.raise_for_status()
        return response.json()["data"]
    except Exception as err:  # pylint: disable=broad-except
        if default is CommandExecutionError:
            raise CommandExecutionError(
                "Failed to list secrets! {}: {}".format(type(err).__name__, err)
            )
        return default


def clear_token_cache():
    """
    .. versionchanged:: 3001

    Delete minion Vault token cache file

    CLI Example:

    .. code-block:: bash

            salt '*' vault.clear_token_cache
    """
    log.debug("Deleting cache file")
    cache_file = os.path.join(__opts__["cachedir"], "salt_vault_token")

    if os.path.exists(cache_file):
        os.remove(cache_file)
        return True
    else:
        log.info("Attempted to delete vault cache file, but it does not exist.")
        return False
