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

In addition to the module configuration, it is required for the Salt master
to be configured to allow peer runs in order to use the Vault integration.

.. versionchanged:: 3007.0

    The ``vault`` configuration structure has changed significantly to account
    for many new features. If found, the old structure will be automatically
    translated to the new one.

    **Please update your peer_run configuration** to take full advantage of the
    updated modules. The old endpoint (``vault.generate_token``) will continue
    to work, but result in unnecessary roundtrips once your minions have been
    updated.

To allow minions to pull configuration and credentials from the Salt master,
add this segment to the master configuration file:

.. code-block:: yaml

    peer_run:
        .*:
            - vault.get_config          # always
            - vault.generate_new_token  # relevant when `token` == `issue:type`
            - vault.generate_secret_id  # relevant when `approle` == `issue:type`

Minimally required configuration:

.. code-block:: yaml

    vault:
      auth:
        token: abcdefg-hijklmnop-qrstuvw
      server:
        url: https://vault.example.com:8200

A sensible example configuration, e.g. in ``/etc/salt/master.d/vault.conf``:

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
            explicit_max_ttl: 30
            num_uses: 10
      policies:
        assign:
          - salt_minion
          - salt_role_{pillar[roles]}
      server:
        url: https://vault.example.com:8200

The above configuration requires the following policies for the master:

.. code-block:: vaultpolicy

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
    ext_pillar:
      - vault: path=salt/minions/{minion}
      - vault: path=salt/roles/{pillar[role]}

The above configuration requires the following policies for the master:

.. code-block:: vaultpolicy

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

.. code-block:: vaultpolicy

    path "salt/data/minions/{{identity.entity.metadata.minion-id}}" {
        capabilities = ["read"]
    }

    path "salt/data/roles/{{identity.entity.metadata.role}}" {
        capabilities = ["read"]
    }

.. note::

    AppRole policies and entity metadata are generally not updated
    automatically. After a change, you will need to synchronize
    them by running :py:func:`vault.sync_approles <salt.runners.vault.sync_approles>`
    or :py:func:`vault.sync_entities <salt.runners.vault.sync_entities>` respectively.

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
        token_lifecycle:
          minimum_ttl: 10
          renew_increment: null
      cache:
        backend: session
        config: 3600
        kv_metadata: connection
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
            secret_id_bound_cidrs: null
            token_ttl: null
            token_max_ttl: null
            token_no_default_policy: false
            token_period: null
            token_bound_cidrs: null
        token:
          role_name: null
          params:
            explicit_max_ttl: null
            num_uses: 1
            ttl: null
            period: null
            no_default_policy: false
            renewable: true
        wrap: 30s
      keys: []
      metadata:
        entity:
          minion-id: '{minion}'
        secret:
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
    .. versionadded:: 3007.0

    The name of the AppRole authentication mount point. Defaults to ``approle``.

approle_name
    .. versionadded:: 3007.0

    The name of the AppRole. Defaults to ``salt-master``.

    .. note::

        Only relevant when a locally configured role_id/secret_id uses
        response wrapping.

method
    Currently only ``token`` and ``approle`` auth types are supported.
    Defaults to ``token``.

    AppRole is the preferred way to authenticate with Vault as it provides
    some advanced options to control the authentication process.
    Please see the `Vault documentation <https://www.vaultproject.io/docs/auth/approle.html>`_
    for more information.

role_id
    The role ID of the AppRole. Required if ``auth:method`` == ``approle``.

    .. versionchanged:: 3007.0

        In addition to a plain string, this can also be specified as a
        dictionary that includes ``wrap_info``, i.e. the return payload
        of a wrapping request.

secret_id
    The secret ID of the AppRole.
    Only required if the configured AppRole requires it.

    .. versionchanged:: 3007.0

        In addition to a plain string, this can also be specified as a
        dictionary that includes ``wrap_info``, i.e. the return payload
        of a wrapping request.

token
    Token to authenticate to Vault with. Required if ``auth:method`` == ``token``.

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

    .. versionchanged:: 3007.0

        In addition to a plain string, this can also be specified as a
        dictionary that includes ``wrap_info``, i.e. the return payload
        of a wrapping request.

token_lifecycle
    Token renewal settings.

    .. note::

        This setting can be specified inside a minion's configuration as well
        and will override the master's default for the minion.

        Token lifecycle settings have significancy for any authentication method,
        not just ``token``.

    ``minimum_ttl`` specifies the time (in seconds or as a time string like ``24h``)
    an in-use token should be valid for. If the current validity period is less
    than this and the token is renewable, a renewal will be attempted. If it is
    not renewable or a renewal does not extend the ttl beyond the specified minimum,
    a new token will be generated.

    .. note::

        Since leases like database credentials are tied to a token, setting this to
        a much higher value than the default can be necessary, depending on your
        specific use case and configuration.

    ``renew_increment`` specifies the amount of time the token's validity should
    be requested to be renewed for when renewing a token. When unset, will extend
    the token's validity by its default ttl.
    Set this to ``false`` to disable token renewals.

    .. note::

        The Vault server is allowed to disregard this request.

``cache``
~~~~~~~~~
Configures token/lease and metadata cache (for KV secrets) on all hosts
as well as configuration cache on minions that receive issued credentials.

backend
    .. versionchanged:: 3007.0

        This used to be found in ``auth:token_backend``.

    The cache backend in use. Defaults to ``session``, which will store the
    Vault configuration in memory only for that specific Salt run.
    ``disk``/``file``/``localfs`` will force using the localfs driver, regardless
    of configured minion data cache.
    Setting this to anything else will use the default configured cache for
    minion data (:conf_master:`cache <cache>`), by default the local filesystem
    as well.

clear_attempt_revocation
    .. versionadded:: 3007.0

    When flushing still valid cached tokens and leases, attempt to have them
    revoked after a (short) delay. Defaults to ``60``.
    Set this to false to disable revocation (not recommended).

clear_on_unauthorized
    .. versionadded:: 3007.0

    When encountering an ``Unauthorized`` response with an otherwise valid token,
    flush the cache and request new credentials. Defaults to true.
    If your policies are relatively stable, disabling this will prevent
    a lot of unnecessary overhead, with the tradeoff that once they change,
    you might have to clear the cache manually or wait for the token to expire.

config
    .. versionadded:: 3007.0

    The time in seconds to cache queried configuration from the master.
    Defaults to ``3600`` (one hour). Set this to ``null`` to disable
    cache expiration. Changed ``server`` configuration on the master will
    still be recognized, but changes in ``auth`` and ``cache`` will need
    a manual update using ``vault.update_config`` or cache clearance
    using ``vault.clear_cache``.

    .. note::

        Expiring the configuration will also clear cached authentication
        credentials and leases.

expire_events
    .. versionadded:: 3007.0

    Fire an event when the session cache containing leases is cleared
    (``vault/cache/<scope>/clear``) or cached leases have expired
    (``vault/lease/<cache_key>/expire``).
    A reactor can be employed to ensure fresh leases are issued.
    Defaults to false.

kv_metadata
    .. versionadded:: 3007.0

    The time in seconds to cache KV metadata used to determine if a path
    is using version 1/2 for. Defaults to ``connection``, which will clear
    the metadata cache once a new configuration is requested from the
    master. Setting this to ``null`` will keep the information
    indefinitely until the cache is cleared manually using
    ``vault.clear_cache`` with ``connection=false``.

secret
    .. versionadded:: 3007.0

    The time in seconds to cache tokens/secret IDs for. Defaults to ``ttl``,
    which caches the secret for as long as it is valid, unless a new configuration
    is requested from the master.

``issue``
~~~~~~~~~
Configures authentication data issued by the master to minions.

type
    .. versionadded:: 3007.0

    The type of authentication to issue to minions. Can be ``token`` or ``approle``.
    Defaults to ``token``.

    To be able to issue AppRoles to minions, the master needs to be able to
    create new AppRoles on the configured auth mount (see policy example above).
    It is strongly encouraged to create a separate mount dedicated to minions.

approle
    .. versionadded:: 3007.0

    Configuration regarding issued AppRoles.

    ``mount`` specifies the name of the auth mount the master manages.
    Defaults to ``salt-minions``. This mount should be exclusively dedicated
    to the Salt master.

    ``params`` configures the AppRole the master creates for minions. See the
    `Vault AppRole API docs <https://www.vaultproject.io/api-docs/auth/approle#create-update-approle>`_
    for details. If you update these params, you can update the minion AppRoles
    manually using the vault runner: ``salt-run vault.sync_approles``, but they
    will be updated automatically during a request by a minion as well.

token
    .. versionadded:: 3007.0

    Configuration regarding issued tokens.

    ``role_name`` specifies the role name for minion tokens created. Optional.

    .. versionchanged:: 3007.0

        This used to be found in ``role_name``.

    If omitted, minion tokens will be created without any role, thus being able
    to inherit any master token policy (including token creation capabilities).

    Example configuration:
    https://www.nomadproject.io/docs/vault-integration/index.html#vault-token-role-configuration

    ``params`` configures the tokens the master issues to minions.

    .. versionchanged:: 3007.0

        This used to be found in ``auth:ttl`` and ``auth:uses``.
        The possible parameters were synchronized with the Vault nomenclature:

          * ``ttl`` previously was mapped to ``explicit_max_ttl`` on Vault, not ``ttl``.
            For the same behavior as before, you will need to set ``explicit_max_ttl`` now.
          * ``uses`` is now called ``num_uses``.

    See the `Vault token API docs <https://developer.hashicorp.com/vault/api-docs/auth/token#create-token>`_
    for details. To make full use of multi-use tokens, you should configure a cache
    that survives a single session (e.g. ``disk``).

    .. note::

        If unset, the master issues single-use tokens to minions, which can be quite expensive.


allow_minion_override_params
    .. versionchanged:: 3007.0

        This used to be found in ``auth:allow_minion_override``.

    Whether to allow minions to request to override parameters for issuing credentials.
    See ``issue_params`` below.

wrap
    .. versionadded:: 3007.0

    The time a minion has to unwrap a wrapped secret issued by the master.
    Set this to false to disable wrapping, otherwise a time string like ``30s``
    can be used. Defaults to ``30s``.

``keys``
~~~~~~~~
    List of keys to use to unseal vault server with the ``vault.unseal`` runner.

``metadata``
~~~~~~~~~~~~
.. versionadded:: 3007.0

Configures metadata for the issued entities/secrets. Values have to be strings
and can be templated with the following variables:

- ``{jid}`` Salt job ID that issued the secret.
- ``{minion}`` The minion ID the secret was issued for.
- ``{user}`` The user the Salt daemon issuing the secret was running as.
- ``{pillar[<var>]}`` A minion pillar value that does not depend on Vault.
- ``{grains[<var>]}`` A minion grain value.

.. note::

    Values have to be strings, hence templated variables that resolve to lists
    will be concatenated to a lexicographically sorted comma-separated list
    (Python ``list.sort()``).

entity
    Configures the metadata associated with the minion entity inside Vault.
    Entities are only created when issuing AppRoles to minions.

secret
    Configures the metadata associated with issued tokens/secret IDs. They
    are logged in plaintext to the Vault audit log.

``policies``
~~~~~~~~~~~~
.. versionchanged:: 3007.0

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

    .. versionadded:: 3006.0

        Policies can be templated with pillar values as well: ``salt_role_{pillar[roles]}``.
        Make sure to only reference pillars that are not sourced from Vault since the latter
        ones might be unavailable during policy rendering. If you use the Vault
        integration in one of your pillar ``sls`` files, all values from that file
        will be absent during policy rendering, even the ones that do not depend on Vault.

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
    .. versionadded:: 3007.0

    Number of seconds compiled templated policies are cached on the master.
    This is important when using pillar values in templates, since compiling
    the pillar is an expensive operation.

    .. note::

        Only effective when issuing tokens to minions. Token policies
        need to be compiled every time a token is requested, while AppRole-associated
        policies are written to Vault configuration the first time authentication data
        is requested (they can be refreshed on demand by running
        ``salt-run vault.sync_approles``).

        They will also be refreshed in case other issuance parameters are changed
        (such as uses/ttl), either on the master or the minion
        (if allow_minion_override_params is True).

refresh_pillar
    .. versionadded:: 3007.0

    Whether to refresh the minion pillar when compiling templated policies
    that contain pillar variables.
    Only effective when issuing tokens to minions (see note on cache_time above).

    - ``null`` (default) only compiles the pillar when no cached pillar is found.
    - ``false`` never compiles the pillar. This means templated policies that
      contain pillar values are skipped if no cached pillar is found.
    - ``true`` always compiles the pillar. This can cause additional strain
      on the master since the compilation is costly.

    .. note::

        Hardcoded to True when issuing AppRoles.

        Using cached pillar data only (refresh_pillar=False) might cause the policies
        to be out of sync. If there is no cached pillar data available for the minion,
        pillar templates will fail to render at all.

        If you use pillar values for templating policies and do not disable
        refreshing pillar data, make sure the relevant values are not sourced
        from Vault (ext_pillar, sdb) or from a pillar sls file that uses the vault
        execution/sdb module. Although this will often work when cached pillar data is
        available, if the master needs to compile the pillar data during policy rendering,
        all Vault modules will be broken to prevent an infinite loop.

``server``
~~~~~~~~~~
.. versionchanged:: 3007.0

    The values found in here were found in the ``vault`` root namespace previously.

Configures Vault server details.

url
    URL of your Vault installation. Required.

verify
    Configures certificate verification behavior when issuing requests to the
    Vault server. If unset, requests will use the CA certificates bundled with ``certifi``.

    For details, please see `the requests documentation <https://requests.readthedocs.io/en/master/user/advanced/#ssl-cert-verification>`_.

    .. versionadded:: 2018.3.0

    .. versionchanged:: 3007.0

        Minions again respect the master configuration value, which was changed
        implicitly in v3001. If this value is set in the minion configuration
        as well, it will take precedence.

        In addition, this value can now be set to a PEM-encoded CA certificate
        to use as the sole trust anchor for certificate chain verification.

namespace
    Optional Vault namespace. Used with Vault Enterprise.

    For details please see:
    https://www.vaultproject.io/docs/enterprise/namespaces

    .. versionadded:: 3004


Minion configuration (optional):

``config_location``
~~~~~~~~~~~~~~~~~~~
    Where to get the connection details for calling vault. By default,
    vault will try to determine if it needs to request the connection
    details from the master or from the local config. This optional option
    will force vault to use the connection details from the master or the
    local config. Can only be either ``master`` or ``local``.

  .. versionadded:: 3006.0

``issue_params``
~~~~~~~~~~~~~~~~
    Request overrides for token/AppRole issuance. This needs to be allowed
    on the master by setting ``issue:allow_minion_override_params`` to true.
    See the master configuration ``issue:token:params`` or ``issue:approle:params``
    for reference.

    .. versionchanged:: 3007.0

        For token issuance, this used to be found in ``auth:ttl`` and ``auth:uses``.
        Mind that the parameter names have been synchronized with Vault, see notes
        above (TLDR: ``ttl`` => ``explicit_max_ttl``, ``uses`` => ``num_uses``.

.. note::

    ``auth:token_lifecycle`` and ``server:verify`` can be set on the minion as well.

.. _vault-setup:
"""

import logging

import salt.utils.vault as vault
from salt.defaults import NOT_SET
from salt.exceptions import CommandExecutionError, SaltException, SaltInvocationError

log = logging.getLogger(__name__)

__deprecated__ = (
    3009,
    "vault",
    "https://github.com/salt-extensions/saltext-vault",
)


def read_secret(path, key=None, metadata=False, default=NOT_SET):
    """
    Return the value of <key> at <path> in vault, or entire secret.

    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.read_secret salt/kv/secret

    Required policy:

    .. code-block:: vaultpolicy

        path "<mount>/<secret>" {
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
                f"Failed to read secret! {type(err).__name__}: {err}"
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

    .. code-block:: vaultpolicy

        path "<mount>/<secret>" {
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
    Set raw data at <path>. The vault policy used must allow this.

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

    .. note::

        This works even for older Vault versions, KV v1 and with missing
        ``patch`` capability, but will use more than one request to simulate
        the functionality by issuing a read and update request.

        For proper, single-request patching, requires versions of KV v2 that
        support the ``patch`` capability and the ``patch`` capability to be available
        for the path.

    .. note::

        This uses JSON Merge Patch format internally.
        Keys set to ``null`` (JSON/YAML)/``None`` (Python) will be deleted.

    CLI Example:

    .. code-block:: bash

            salt '*' vault.patch_secret "secret/my/secret" password="baz"

    Required policy:

    .. code-block:: vaultpolicy

        # Proper patching
        path "<mount>/data/<secret>" {
            capabilities = ["patch"]
        }

        # OR (!), for older KV v2 setups:

        path "<mount>/data/<secret>" {
            capabilities = ["read", "update"]
        }

        # OR (!), for KV v1 setups:

        path "<mount>/<secret>" {
            capabilities = ["read", "update"]
        }

    path
        The path to the secret, including mount.
    """
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
    Delete secret at <path>. The vault policy used must allow this.
    If <path> is on KV v2, the secret will be soft-deleted.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.delete_secret "secret/my/secret"
        salt '*' vault.delete_secret "secret/my/secret" 1 2 3

    Required policy:

    .. code-block:: vaultpolicy

        path "<mount>/<secret>" {
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

    .. versionadded:: 3007.0

        For KV v2, you can specify versions to soft-delete as supplemental
        positional arguments.
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

    Destroy specified secret versions <path>. The vault policy
    used must allow this. Only supported on Vault KV version 2.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.destroy_secret "secret/my/secret" 1 2

    Required policy:

    .. code-block:: vaultpolicy

        path "<mount>/destroy/<secret>" {
            capabilities = ["update"]
        }

    path
        The path to the secret, including mount.

    You can specify versions to destroy as supplemental positional arguments.
    At least one is required.
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
    List secret keys at <path>. The vault policy used must allow this.
    The path should end with a trailing slash.

    .. versionchanged:: 3001
        The ``default`` argument has been added. When the path or path/key
        combination is not found, an exception will be raised, unless a default
        is provided.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.list_secrets "secret/my/"

    Required policy:

    .. code-block:: vaultpolicy

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
        .. versionadded:: 3007.0

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
                f"Failed to list secrets! {type(err).__name__}: {err}"
            ) from err
        return default


def clear_cache(connection=True, session=False):
    """
    .. versionadded:: 3007.0

    Delete Vault caches. Will ensure the current token and associated leases
    are revoked by default.

    The cache is organized in a hierarchy: ``/vault/connection/session/leases``.
    (*italics* mark data that is only cached when receiving configuration from a master)

    ``connection`` contains KV metadata (by default), *configuration* and *(AppRole) auth credentials*.
    ``session`` contains the currently active token.
    ``leases`` contains leases issued to the currently active token like database credentials.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.clear_cache
        salt '*' vault.clear_cache session=True

    connection
        Only clear the cached data scoped to a connection. This includes
        configuration, auth credentials, the currently active auth token
        as well as leases and KV metadata (by default). Defaults to true.
        Set this to false to clear all Vault caches.

    session
        Only clear the cached data scoped to a session. This only includes
        leases and the currently active auth token, but not configuration
        or (AppRole) auth credentials. Defaults to false.
        Setting this to true will keep the connection cache, regardless
        of ``connection``.
    """
    return vault.clear_cache(
        __opts__, __context__, connection=connection, session=session
    )


def clear_token_cache():
    """
    .. versionchanged:: 3001
    .. versionchanged:: 3007.0

        This is now an alias for ``vault.clear_cache`` with ``connection=True``.

    Delete minion Vault token cache.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.clear_token_cache
    """
    log.debug("Deleting vault connection cache.")
    return clear_cache(connection=True, session=False)


def policy_fetch(policy):
    """
    .. versionadded:: 3007.0

    Fetch the rules associated with an ACL policy. Returns None if the policy
    does not exist.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_fetch salt_minion

    Required policy:

    .. code-block:: vaultpolicy

        path "sys/policy/<policy>" {
            capabilities = ["read"]
        }

    policy
        The name of the policy to fetch.
    """
    # there is also "sys/policies/acl/{policy}"
    endpoint = f"sys/policy/{policy}"

    try:
        data = vault.query("GET", endpoint, __opts__, __context__)
        return data["rules"]

    except vault.VaultNotFoundError:
        return None
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err


def policy_write(policy, rules):
    r"""
    .. versionadded:: 3007.0

    Create or update an ACL policy.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_write salt_minion 'path "secret/foo" {...}'

    Required policy:

    .. code-block:: vaultpolicy

        path "sys/policy/<policy>" {
            capabilities = ["create", "update"]
        }

    policy
        The name of the policy to create/update.

    rules
        Rules to write, formatted as in-line HCL.
    """
    endpoint = f"sys/policy/{policy}"
    payload = {"policy": rules}
    try:
        return vault.query("POST", endpoint, __opts__, __context__, payload=payload)
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err


def policy_delete(policy):
    """
    .. versionadded:: 3007.0

    Delete an ACL policy. Returns False if the policy did not exist.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policy_delete salt_minion

    Required policy:

    .. code-block:: vaultpolicy

        path "sys/policy/<policy>" {
            capabilities = ["delete"]
        }

    policy
        The name of the policy to delete.
    """
    endpoint = f"sys/policy/{policy}"

    try:
        return vault.query("DELETE", endpoint, __opts__, __context__)
    except vault.VaultNotFoundError:
        return False
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err


def policies_list():
    """
    .. versionadded:: 3007.0

    List all ACL policies.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.policies_list

    Required policy:

    .. code-block:: vaultpolicy

        path "sys/policy" {
            capabilities = ["read"]
        }
    """
    try:
        return vault.query("GET", "sys/policy", __opts__, __context__)["policies"]
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err


def query(method, endpoint, payload=None):
    """
    .. versionadded:: 3007.0

    Issue arbitrary queries against the Vault API.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.query GET auth/token/lookup-self

    Required policy: Depends on the query.

    You can ask the vault CLI to output the necessary policy:

    .. code-block:: bash

        vault read -output-policy auth/token/lookup-self

    method
        HTTP method to use.

    endpoint
        Vault API endpoint to issue the request against. Do not include ``/v1/``.

    payload
        Optional dictionary to use as JSON payload.
    """
    try:
        return vault.query(method, endpoint, __opts__, __context__, payload=payload)
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err


def update_config(keep_session=False):
    """
    .. versionadded:: 3007.0

    Attempt to update the cached configuration without clearing the
    currently active Vault session.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.update_config

    keep_session
        Only update configuration that can be updated without
        creating a new login session.
        If this is false, still tries to keep the active session,
        but might clear it if the server configuration has changed
        significantly.
        Defaults to False.
    """
    return vault.update_config(__opts__, __context__, keep_session=keep_session)


def get_server_config():
    """
    .. versionadded:: 3007.0

    Return the server connection configuration that's currently in use by Salt.
    Contains ``url``, ``verify`` and ``namespace``.

    CLI Example:

    .. code-block:: bash

        salt '*' vault.get_server_config
    """
    try:
        client = vault.get_authd_client(__opts__, __context__)
        return client.get_config()
    except SaltException as err:
        raise CommandExecutionError(f"{type(err).__name__}: {err}") from err
