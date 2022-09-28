"""
Functions to interact with Hashicorp Vault.
===========================================

:maintainer:    SaltStack
:maturity:      new
:platform:      all


:note: If you see the following error, you'll need to upgrade ``requests`` to at least 2.4.2

.. code-block:: text

    <timestamp> [salt.pillar][CRITICAL][14337] Pillar render error: Failed to load ext_pillar vault: {'error': "request() got an unexpected keyword argument 'json'"}


Configuration
-------------

The salt-master must be configured to allow peer-runner
configuration, as well as configuration for the module.

.. versionchanged:: 3006

    The configuration structure has changed significantly to account for many
    new features. If found, the old configuration structure will be translated
    to the new one automatically.

To allow minions to pull configuration and credentials from the Salt master,
add this segment to the master configuration file:

.. code-block:: yaml

    peer_run:
        .*:
            - vault.get_config
            - vault.generate_new_token  # relevant when ``issue:type`` == ``token``
            - vault.generate_secret_id  # relevant when ``issue:type`` == ``approle``

Minimally required configuration:

.. code-block:: yaml

    vault:
      auth:
        token: abcdefg-hijklmnop-qrstuvw
      server:
        url: https://vault.example.com:8200

A sensible example configuration, e.g. in /etc/salt/master.d/vault.conf:

.. code-block:: yaml

    vault:
      auth:
        method: approle
        role_id: e5a7b66e-5d08-da9c-7075-71984634b882
        secret_id: 841771dc-11c9-bbc7-bcac-6a3945a69cd9
      cache:
        backend: file
      issue:
        token:
          role_name: salt_minion
          params:
            ttl: 30
            uses: 10
      policies:
        assign:
          - salt_minion
          - salt_role_{pillar[roles]}
      server:
        url: https://vault.example.com:8200
        verify: /etc/ssl/cert.pem

The above configuration requires the following policies for the master:

.. code-block:: terraform

    # Issue tokens
    path "auth/token/create" {
      capabilities = ["create", "read", "update"]
    }

    # Issue tokens with token roles
    path "auth/token/create/*" {
      capabilities = ["create", "read", "update"]
    }

A sensible example configuration that issues AppRoles to minions
from a separate authentication endpoint (notice differing mounts):

.. code-block:: yaml

    vault:
      auth:
        method: approle
        mount: approle         # <-- mount the salt master authenticates at
        role_id: e5a7b66e-5d08-da9c-7075-71984634b882
        secret_id: 841771dc-11c9-bbc7-bcac-6a3945a69cd9
      cache:
        backend: file
      issue:
        type: approle
        approle:
          mount: salt-minions  # <-- mount the salt master manages
      metadata:
        entity:
          minion-id: '{minion}'
          role: '{pillar[role]}'
      server:
        url: https://vault.example.com:8200
        verify: /etc/ssl/cert.pem
    ext_pillar:
      - vault: path=salt/minions/{minion}
      - vault: path=salt/roles/{pillar[role]}

The above configuration requires the following policies for the master:

.. code-block:: terraform

    # List existing AppRoles
    path "auth/salt-minions/role" {
      capabilities = ["list"]
    }

    # Manage AppRoles
    path "auth/salt-minions/role/*" {
      capabilities = ["read", "create", "update", "delete"]
    }

    # Lookup mount accessor
    path "sys/auth/salt-minions" {
      capabilities = ["read", "sudo"]
    }

    # Lookup entities by alias name (role-id) and alias mount accessor
    path "identity/lookup/entity" {
      capabilities = ["create", "update"]
      allowed_parameters = {
        "alias_name" = []
        "alias_mount_accessor" = ["auth_approle_0a1b2c3d"]
      }
    }

    # Manage entities with name prefix salt_minion_
    path "identity/entity/name/salt_minion_*" {
      capabilities = ["read", "create", "update", "delete"]
    }

    # Create entity aliases – you can restrict the mount_accessor
    # This might allow privilege escalation in case the salt master
    # is compromised and the attacker knows the entity ID of an
    # entity with relevant policies attached - although you might
    # have other problems at that point.
    path "identity/entity-alias" {
      capabilities = ["create", "update"]
      allowed_parameters = {
        "id" = []
        "canonical_id" = []
        "mount_accessor" = ["auth_approle_0a1b2c3d"]
        "name" = []
      }
    }

This enables you to write templated ACL policies like:

.. code-block:: terraform

    path "salt/data/minions/{{identity.entity.metadata.minion-id}}" {
        capabilities = ["read"]
    }

    path "salt/data/roles/{{identity.entity.metadata.role}}" {
        capabilities = ["read"]
    }


All possible master configuration options with defaults:

.. code-block:: yaml

    vault:
      auth:
        approle_mount: approle
        approle_name: salt-master
        method: token
        role_id: <required if auth:method == approle>
        secret_id: null
        token: <required if auth:method == token>
      cache:
        backend: session
        config: 3600
        secret: ttl
      issue:
        allow_minion_override_params: false
        type: token
        approle:
          mount: salt-minions
          params:
            bind_secret_id: true
            secret_id_num_uses: 1
            secret_id_ttl: 60
            token_explicit_max_ttl: 60
            token_num_uses: 10
        token:
          role_name: null
          params:
            ttl: null
            uses: 1
        wrap: 30s
      keys: []
      metadata:
        entity:
          minion-id: '{minion}'
        token:
          saltstack-jid: '{jid}'
          saltstack-minion: '{minion}'
          saltstack-user: '{user}'
      policies:
        assign:
          - saltstack/minions
          - saltstack/{minion}
        cache_time: 60
        refresh_pillar: null
      server:
        url: <required, e. g. https://vault.example.com:8200>
        namespace: null
        verify: null

``auth``
~~~~~~~~
Contains authentication information for the local machine.

approle_mount
    .. versionadded:: 3006

    The name of the AppRole authentication mount point. Defaults to ``approle``.

approle_name
    .. versionadded:: 3006

    The name of the AppRole. Defaults to ``salt-master``.

method
    Currently only ``token`` and ``approle`` auth types are supported.
    Defaults to ``token``.

    Approle is the preferred way to authenticate with Vault as it provide
    some advanced options to control authentication process.
    Please visit Vault documentation for more info:
    https://www.vaultproject.io/docs/auth/approle.html

role_id
    The role ID of the AppRole. Required if auth:method == ``approle``.

secret_id
    The secret ID of the AppRole.
    Only required if the configured role ID requires it.

token
    Token to authenticate to Vault with. Required if auth:method == ``token``.

    The token must be able to create tokens with the policies that should be
    assigned to minions.
    You can still use the token auth via a OS environment variable via this
    config example:

    .. code-block:: yaml

        vault:
          auth:
            method: token
            token: sdb://osenv/VAULT_TOKEN
          server:
            url: https://vault.service.domain:8200

        osenv:
          driver: env

    And then export the VAULT_TOKEN variable in your OS:

    .. code-block:: bash

       export VAULT_TOKEN=11111111-1111-1111-1111-1111111111111

``cache``
~~~~~~~~~
Configures configuration cache on minions and secret cache on all hosts as well
as metadata cache for KV secrets.

backend
    .. versionchanged:: 3006

        This used to be found in ``auth:token_backend``.

    The cache backend in use. Defaults to ``session``, which will store the
    vault information in memory only for that session. Setting this to anything
    else will use the configured cache for minion data (:conf_master:`cache <cache>`),
    by default the local filesystem.

config
    .. versionadded:: 3006

    The time in seconds to cache queried configuration from the master.
    Defaults to 3600 (1h).

secret
    .. versionadded:: 3006

    The time in seconds to cache tokens/secret-ids for. Defaults to ``ttl``,
    which caches the secret for as long as it is valid.

``issue``
~~~~~~~~~
Configures authentication data issued by the master to minions.

type
    .. versionadded:: 3006

    The type of authentication to issue to minions. Can be ``token`` or ``approle``.
    Defaults to ``token``.

    To be able to issue AppRoles to minions, the master needs to be able to
    create new AppRoles on the configured auth mount (see policy example above).
    It is strongly encouraged to create a separate mount dedicated to minions.

approle
    .. versionadded:: 3006

    Configuration regarding issued AppRoles.

    ``mount`` specifies the name of the auth mount the master manages.
    Defaults to ``salt-minions``. This mount should be exclusively dedicated
    to the Salt master.

    ``params`` configures the AppRole the master creates for minions. See the
    `Vault API docs <https://www.vaultproject.io/api-docs/auth/approle#create-update-approle>`_
    for details. The configuration is only relevant for the first time the
    AppRole is created. If you update these params, you will need to update
    the minion AppRoles manually using the vault runner:
    ``salt-run vault.sync_approles`` .

token
    .. versionadded:: 3006

    Configuration regarding issued tokens.

    ``role_name`` specifies the role name for minion tokens created. Optional.

    .. versionchanged:: 3006

        This used to be found in ``role_name``.

    If omitted, minion tokens will be created without any role, thus being able
    to inherit any master token policy (including token creation capabilities).

    For details please see:
    https://www.vaultproject.io/api/auth/token/index.html#create-token

    Example configuration:
    https://www.nomadproject.io/docs/vault-integration/index.html#vault-token-role-configuration

    ``params`` configures the tokens the master issues to minions.

    .. versionchanged:: 3006

        This used to be found in ``auth:ttl`` and ``auth:uses``.

    This setting currently concerns token reuse only. If unset, the master
    issues single-use tokens to minions, which can be quite expensive. You
    can set ``ttl`` (configuring the explicit_max_ttl for tokens) and ``uses``
    (configuring num_uses, the number of requests a single token is allowed to issue).
    To make full use of multi-use tokens, you should configure a cache that
    survives a single session.


allow_minion_override_params
    .. versionchanged:: 3006

        This used to be found in ``auth:allow_minion_override``.

    Whether to allow minions to request to override parameters for issuing credentials,
    especially ``ttl`` and ``num_uses``. Defaults to false.

    .. note::

        Minion override parameters should be specified in the minion configuration
        under ``vault:issue_params``. ``ttl`` and ``uses`` always refer to
        issued token lifecycle settings. For AppRoles specifically, there
        are more parameters, such as ``secret_id_num_uses`` and ``secret_id_ttl``.
        ``bind_secret_id`` can not be overridden.

wrap
    .. versionadded:: 3006

    The time a minion has to unwrap a wrapped secret issued by the master.
    Set this to false to disable wrapping, otherwise a time string like ``30s``
    can be used. Defaults to 30s.

``keys``
~~~~~~~~
    List of keys to use to unseal vault server with the ``vault.unseal`` runner.

``metadata``
~~~~~~~~~~~~
.. versionadded:: 3006

Configures metadata for the issued secrets. Values have to be strings and can
be templated with the following variables:

- ``{jid}`` Salt job ID that issued the secret.
- ``{minion}`` The minion ID the secret was issued for.
- ``{user}`` The user the Salt daemon issuing the secret was running as.
- ``{pillar[<var>]}`` A minion pillar value that does not depend on Vault.
- ``{grains[<var>]}`` A minion grain value.

.. note::

    Values have to be strings, hence templated variables that resolve to lists
    will be concatenated to an alphabetically sorted comma-separated list.

entity
    Configures the metadata associated with the minion entity inside Vault.
    Entities are only created when issuing AppRoles to minions.

token
    Configures the metadata associated with issued tokens.

``policies``
~~~~~~~~~~~~
.. versionchanged:: 3006

    This used to specify the list of policies associated with a minion token only.
    The equivalent is found in ``assign``.

assign
    List of policies that are assigned to issued minion authentication data,
    either token or AppRole.

    They can be static strings or string templates with

    - ``{minion}`` The minion ID.
    - ``{pillar[<var>]}`` A minion pillar value.
    - ``{grains[<var>]}`` A minion grain value.

    For pillar and grain values, lists are expanded, so ``salt_role_{pillar[roles]}``
    with ``[a, b]`` results in ``salt_role_a`` and ``salt_role_b`` to be issued.

    Defaults to ``[saltstack/minions, saltstack/{minion}]``.

    .. versionadded:: 3006

        Policies can be templated with pillar values as well: ``salt_role_{pillar[roles]}``
        Make sure to only reference pillars that are not sourced from Vault since the latter
        ones might be unavailable during policy rendering.

    .. important::

        See :ref:`Is Targeting using Grain Data Secure?
        <faq-grain-security>` for important security information. In short,
        everything except ``grains[id]`` is minion-controlled.

    .. note::

        List members which do not have simple string representations,
        such as dictionaries or objects, do not work and will
        throw an exception. Strings and numbers are examples of
        types which work well.

cache_time
    .. versionadded:: 3006

    Number of seconds compiled templated policies are cached on the master.
    This is important when using pillar values in templates, since compiling
    the pillar is an expensive operation.

refresh_pillar
    .. versionadded:: 3006

    Whether to refresh the minion pillar when compiling templated policies
    that contain pillar variables.

    - ``null`` (default) only compiles the pillar when no cached pillar is found.
    - ``false`` never compiles the pillar. This means templated policies that
      contain pillar values are skipped if no cached pillar is found.
    - ``true`` always compiles the pillar. This can cause additional strain
      on the master since the compilation is costly.

    .. note::

        Using cached pillar data only (refresh_pillar=False) might cause the policies
        to be out of sync. If there is no cached pillar data available for the minion,
        pillar templates will fail to render at all.

        If you use pillar values for templating policies and do not disable
        refreshing pillar data, make sure the relevant values are not sourced
        from Vault (ext_pillar, sdb) or from a pillar sls file that uses the vault
        execution module. Although this will often work when cached pillar data is
        available, if the master needs to compile the pillar data during policy rendering,
        all Vault modules will be broken to prevent an infinite loop.

``server``
~~~~~~~~~~
.. versionchanged:: 3006

    The values found in here were found in the ``vault`` root namespace previously.

Configures Vault server details.

url
    Url to your Vault installation. Required.

verify
    For details please see
    https://requests.readthedocs.io/en/master/user/advanced/#ssl-cert-verification

    .. versionadded:: 2018.3.0

namespace
    Optional Vault namespace. Used with Vault Enterprise.

    For detail please see:
    https://www.vaultproject.io/docs/enterprise/namespaces

    .. versionadded:: 3004

.. _vault-setup:
"""
import logging

import salt.utils.vault as vault
from salt.defaults import NOT_SET
from salt.exceptions import CommandExecutionError, SaltException, SaltInvocationError

log = logging.getLogger(__name__)


def read_secret(path, key=None, metadata=False, default=NOT_SET):
    """
    Return the value of key at path in vault, or entire secret.

    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.read_secret salt/kv/secret

    Required policy:

    .. code-block:: terraform

        path "<mount/<secret>" {
            capabilities = ["read"]
        }

        # or KV v2
        path "<mount>/data/<secret>" {
            capabilities = ["read"]
        }

    path
        The path to the secret, including mount.

    key
        The data field at <path> to read. If unspecified, returns the
        whole dataset.

    metadata
        .. versionadded:: 3001

        If using KV v2 backend, display full results, including metadata.
        Defaults to False.

    default
        .. versionadded:: 3001

        When the path or path/key combination is not found, an exception will
        be raised, unless a default is provided here.
    """
    if default == NOT_SET:
        default = CommandExecutionError
    if key is not None:
        metadata = False
    log.debug("Reading Vault secret for %s at %s", __grains__.get("id"), path)
    try:
        data = vault.read_kv(path, __opts__, __context__, include_metadata=metadata)
        if key is not None:
            return data[key]
        return data
    except Exception as err:  # pylint: disable=broad-except
        if default is CommandExecutionError:
            raise CommandExecutionError(
                "Failed to read secret! {}: {}".format(type(err).__name__, err)
            ) from err
        return default


def write_secret(path, **kwargs):
    """
    Set secret dataset at <path>. The vault policy used must allow this.
    Fields are specified as arbitrary keyword arguments.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.write_secret "secret/my/secret" user="foo" password="bar"

    Required policy:

    .. code-block:: terraform

        path "<mount/<secret>" {
            capabilities = ["create", "update"]
        }

        # or KV v2
        path "<mount>/data/<secret>" {
            capabilities = ["create", "update"]
        }

    path
        The path to the secret, including mount.
    """
    log.debug("Writing vault secrets for %s at %s", __grains__.get("id"), path)
    data = {x: y for x, y in kwargs.items() if not x.startswith("__")}
    try:
        res = vault.write_kv(path, data, __opts__, __context__)
        if isinstance(res, dict):
            return res["data"]
        return res
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(err).__name__, err)
        return False


def write_raw(path, raw):
    """
    Set raw data at the path in vault. The vault policy used must allow this.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.write_raw "secret/my/secret" '{"user":"foo","password": "bar"}'

    Required policy: see write_secret

    path
        The path to the secret, including mount.

    raw
        Secret data to write to <path>. Has to be a mapping.
    """
    log.debug("Writing vault secrets for %s at %s", __grains__.get("id"), path)
    try:
        res = vault.write_kv(path, raw, __opts__, __context__)
        if isinstance(res, dict):
            return res["data"]
        return res
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to write secret! %s: %s", type(err).__name__, err)
        return False


def patch_secret(path, **kwargs):
    """
    Patch secret dataset at <path>. Fields are specified as arbitrary keyword arguments.
    Requires KV v2 and "patch" capability.

    .. note::

        This uses JSON Merge Patch format internally.
        Keys set to ``null`` (JSON/YAML)/``None`` (Python) will be deleted.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.patch_secret "secret/my/secret" password="baz"

    Required policy:

    .. code-block:: terraform

        path "<mount>/data/<secret>" {
            capabilities = ["patch"]
        }

    path
        The path to the secret, including mount.
    """
    # TODO: patch can be emulated as read, local update and write
    # -> catch VaultPermissionDeniedError and try that way
    log.debug("Patching vault secrets for %s at %s", __grains__.get("id"), path)
    data = {x: y for x, y in kwargs.items() if not x.startswith("__")}
    try:
        res = vault.patch_kv(path, data, __opts__, __context__)
        if isinstance(res, dict):
            return res["data"]
        return res
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to patch secret! %s: %s", type(err).__name__, err)
        return False


def delete_secret(path, *args):
    """
    Delete secret at the path in vault. The vault policy used must allow this.
    If <path> is on KV v2, the secret will be soft-deleted.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.delete_secret "secret/my/secret"
        salt '*' vault.delete_secret "secret/my/secret" 0 1 2 3

    Required policy:

    .. code-block:: terraform

        path "<mount/<secret>" {
            capabilities = ["delete"]
        }

        # or KV v2
        path "<mount>/data/<secret>" {
            capabilities = ["delete"]
        }

        # KV v2 versions
        path "<mount>/delete/<secret>" {
            capabilities = ["update"]
        }

    path
        The path to the secret, including mount.

    .. versionadded:: 3006

        For KV v2, you can specify versions to soft-delete as supplemental arguments.
    """
    log.debug("Deleting vault secrets for %s in %s", __grains__.get("id"), path)
    try:
        return vault.delete_kv(path, __opts__, __context__, versions=list(args) or None)
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to delete secret! %s: %s", type(err).__name__, err)
        return False


def destroy_secret(path, *args):
    """
    .. versionadded:: 3001

    Destroy specified secret versions at the path in vault. The vault policy
    used must allow this. Only supported on Vault KV version 2.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.destroy_secret "secret/my/secret" 1 2

    Required policy:

    .. code-block:: terraform

        path "<mount>/destroy/<secret>" {
            capabilities = ["update"]
        }

    path
        The path to the secret, including mount.

    You can specify versions to destroy as supplemental arguments. At least one
    is required.
    """
    if not args:
        raise SaltInvocationError("Need at least one version to destroy.")
    log.debug("Destroying vault secrets for %s in %s", __grains__.get("id"), path)
    try:
        return vault.destroy_kv(path, list(args), __opts__, __context__)
    except Exception as err:  # pylint: disable=broad-except
        log.error("Failed to destroy secret! %s: %s", type(err).__name__, err)
        return False


def list_secrets(path, default=NOT_SET, keys_only=False):
    """
    List secret keys at the path in vault. The vault policy used must allow this.
    The path should end with a trailing slash.

    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.list_secrets "secret/my/"

    Required policy:

    .. code-block:: terraform

        path "<mount>/<path>" {
            capabilities = ["list"]
        }

        # or KV v2
        path "<mount>/metadata/<path>" {
            capabilities = ["list"]
        }

    path
        The path to the secret, including mount.

    default
        .. versionadded:: 3001

        When the path is not found, an exception will be raised, unless a default
        is provided here.

    keys_only
        .. versionadded:: 3006

        This function used to return a dictionary like ``{"keys": ["some/", "some/key"]}``.
        Setting this to True will only return the list of keys.
        For backwards-compatibility reasons, this defaults to False.
    """
    if default == NOT_SET:
        default = CommandExecutionError
    log.debug("Listing vault secret keys for %s in %s", __grains__.get("id"), path)
    try:
        keys = vault.list_kv(path, __opts__, __context__)
        if keys_only:
            return keys
        # this is the way Salt behaved previously
        return {"keys": keys}
    except Exception as err:  # pylint: disable=broad-except
        if default is CommandExecutionError:
            raise CommandExecutionError(
                "Failed to list secrets! {}: {}".format(type(err).__name__, err)
            ) from err
        return default


def clear_token_cache(connection_only=True):
    """
    .. versionchanged:: 3001

    Delete minion Vault token cache.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.clear_token_cache

    connection_only
        .. versionadded:: 3006

        Only delete cache data scoped to a connection configuration. This is currently
        true for all Vault cache data, but might change in the future.
        Defaults to True.
    """
    log.debug("Deleting vault connection cache.")
    return vault.clear_cache(__opts__, connection=connection_only)


def policy_fetch(policy):
    """
    .. versionadded:: 3006

    Fetch the rules associated with an ACL policy. Returns None if the policy
    does not exist.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_fetch salt_minion

    Required policy:

    .. code-block:: terraform

        path "sys/policy/<policy>" {
            capabilities = ["read"]
        }

    policy
        The name of the policy
    """
    # there is also "sys/policies/acl/{policy}"
    endpoint = f"sys/policy/{policy}"

    try:
        data = vault.query("GET", endpoint, __opts__, __context__)
        return data["rules"]

    except vault.VaultNotFoundError:
        return None
    except SaltException as err:
        raise CommandExecutionError("{}: {}".format(type(err).__name__, err)) from err


def policy_write(policy, rules):
    r"""
    .. versionadded:: 3006

    Create or update an ACL policy.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_write salt_minion "path \"secret/foo\" {..."

    Required policy:

    .. code-block:: terraform

        path "sys/policy/<policy>" {
            capabilities = ["create", "update"]
        }

    policy
        The name of the policy

    rules
        Rules formatted as in-line HCL
    """
    endpoint = f"sys/policy/{policy}"
    payload = {"policy": rules}
    try:
        return vault.query("POST", endpoint, __opts__, __context__, payload=payload)
    except SaltException as err:
        raise CommandExecutionError("{}: {}".format(type(err).__name__, err)) from err


def policy_delete(policy):
    """
    .. versionadded:: 3006

    Delete an ACL policy. Returns False if the policy did not exist.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_delete salt_minion

    Required policy:

    .. code-block:: terraform

        path "sys/policy/<policy>" {
            capabilities = ["delete"]
        }

    policy
        The name of the policy
    """
    endpoint = f"sys/policy/{policy}"

    try:
        return vault.query("DELETE", endpoint, __opts__, __context__)
    except vault.VaultNotFoundError:
        return False
    except SaltException as err:
        raise CommandExecutionError("{}: {}".format(type(err).__name__, err)) from err


def policies_list():
    """
    .. versionadded:: 3006

    List all ACL policies.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policies_list

    Required policy:

    .. code-block:: terraform

        path "sys/policy" {
            capabilities = ["read"]
        }
    """
    try:
        return vault.query("GET", "sys/policy", __opts__, __context__)["policies"]
    except SaltException as err:
        raise CommandExecutionError("{}: {}".format(type(err).__name__, err)) from err


def query(method, endpoint, payload=None):
    """
    .. versionadded:: 3006

    Issue arbitrary queries against the Vault API.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.query GET auth/token/lookup-self

    Required policy: Depends on the query.

    You can ask the vault CLI to output the necessary policy:

    .. code-block:: bash

        vault read -output-policy auth/token/lookup-self

    method
        HTTP method to use

    endpoint
        Vault API endpoint to issue the request against. Do not include ``/v1/``.

    payload
        Optional dictionary to use as JSON payload.
    """
    try:
        return vault.query(method, endpoint, __opts__, __context__, payload=payload)
    except SaltException as err:
        raise CommandExecutionError("{}: {}".format(type(err).__name__, err)) from err
