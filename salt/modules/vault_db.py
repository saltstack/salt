"""
Manage the Vault database secret engine.

Configuration instructions are documented in the :ref:`vault execution module docs <vault-setup>`.

.. versionadded:: 3007.0
"""

import logging

import salt.utils.vault as vault
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


PLUGINS = {
    "cassandra": {
        "name": "cassandra",
        "required": [
            "hosts",
            "username",
            "password",
        ],
    },
    "couchbase": {
        "name": "couchbase",
        "required": [
            "hosts",
            "username",
            "password",
        ],
    },
    "elasticsearch": {
        "name": "elasticsearch",
        "required": [
            "url",
            "username",
            "password",
        ],
    },
    "influxdb": {
        "name": "influxdb",
        "required": [
            "host",
            "username",
            "password",
        ],
    },
    "hanadb": {
        "name": "hana",
        "required": [
            "connection_url",
        ],
    },
    "mongodb": {
        "name": "mongodb",
        "required": [
            "connection_url",
        ],
    },
    "mongodb_atlas": {
        "name": "mongodbatlas",
        "required": [
            "public_key",
            "private_key",
            "project_id",
        ],
    },
    "mssql": {
        "name": "mssql",
        "required": [
            "connection_url",
        ],
    },
    "mysql": {
        "name": "mysql",
        "required": [
            "connection_url",
        ],
    },
    "oracle": {
        "name": "oracle",
        "required": [
            "connection_url",
        ],
    },
    "postgresql": {
        "name": "postgresql",
        "required": [
            "connection_url",
        ],
    },
    "redis": {
        "name": "redis",
        "required": [
            "host",
            "port",
            "username",
            "password",
        ],
    },
    "redis_elasticache": {
        "name": "redis-elasticache",
        "required": [
            "url",
            "username",
            "password",
        ],
    },
    "redshift": {
        "name": "redshift",
        "required": [
            "connection_url",
        ],
    },
    "snowflake": {
        "name": "snowflake",
        "required": [
            "connection_url",
        ],
    },
    "default": {
        "name": "",
        "required": [],
    },
}


def list_connections(mount="database"):
    """
    List configured database connections.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#list-connections>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.list_connections

    mount
        The mount path the DB backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/config"
    try:
        return vault.query("LIST", endpoint, __opts__, __context__)["data"]["keys"]
    except vault.VaultNotFoundError:
        return []
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def fetch_connection(name, mount="database"):
    """
    Read a configured database connection. Returns None if it does not exist.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#read-connection>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.fetch_connection mydb

    name
        The name of the database connection.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/config/{name}"
    try:
        return vault.query("GET", endpoint, __opts__, __context__)["data"]
    except vault.VaultNotFoundError:
        return None
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def write_connection(
    name,
    plugin,
    version="",
    verify=True,
    allowed_roles=None,
    root_rotation_statements=None,
    password_policy=None,
    rotate=True,
    mount="database",
    **kwargs,
):
    """
    Create/update a configured database connection.

    .. note::

        This endpoint distinguishes between create and update ACL capabilities.

    .. note::

        It is highly recommended to use a Vault-specific user rather than the admin user in the
        database when configuring the plugin. This user will be used to create/update/delete users
        within the database so it will need to have the appropriate permissions to do so.
        If the plugin supports rotating the root credentials, it is highly recommended to perform
        that action after configuring the plugin. This will change the password of the user
        configured in this step. The new password will not be viewable by users.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#configure-connection>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.write_connection mydb elasticsearch \
                url=http://127.0.0.1:9200 username=vault password=hunter2

    name
        The name of the database connection.

    plugin
        The name of the database plugin. Known plugins to this module are:
        ``cassandra``, ``couchbase``, ``elasticsearch``, ``influxdb``, ``hanadb``, ``mongodb``,
        ``mongodb_atlas``, ``mssql``, ``mysql``, ``oracle``, ``postgresql``, ``redis``,
        ``redis_elasticache``, ``redshift``, ``snowflake``.
        If you pass an unknown plugin, make sure its Vault-internal name can be formatted
        as ``{plugin}-database-plugin`` and to pass all required parameters as kwargs.

    version
        Specifies the semantic version of the plugin to use for this connection.

    verify
        Verify the connection during initial configuration. Defaults to True.

    allowed_roles
        List of the roles allowed to use this connection. ``["*"]`` means any role
        can use this connection. Defaults to empty (no role can use it).

    root_rotation_statements
        Specifies the database statements to be executed to rotate the root user's credentials.
        See the plugin's API page for more information on support and formatting for this parameter.

    password_policy
        The name of the password policy to use when generating passwords for this database.
        If not specified, this will use a default policy defined as:
        20 characters with at least 1 uppercase, 1 lowercase, 1 number, and 1 dash character.

    rotate
        Rotate the root credentials after plugin setup. Defaults to True.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.

    kwargs
        Different plugins require different parameters. You need to make sure that you pass them
        as supplemental keyword arguments. For known plugins, the required arguments will
        be checked.
    """
    endpoint = f"{mount}/config/{name}"
    plugin_meta = PLUGINS.get(plugin, "default")
    plugin_name = plugin_meta["name"] or plugin
    payload = {k: v for k, v in kwargs.items() if not k.startswith("_")}

    if fetch_connection(name, mount=mount) is None:
        missing_kwargs = set(plugin_meta["required"]) - set(payload)
        if missing_kwargs:
            raise SaltInvocationError(
                f"The plugin {plugin} requires the following additional kwargs: {missing_kwargs}."
            )

    payload["plugin_name"] = f"{plugin_name}-database-plugin"
    payload["verify_connection"] = verify
    if version is not None:
        payload["plugin_version"] = version
    if allowed_roles is not None:
        payload["allowed_roles"] = allowed_roles
    if root_rotation_statements is not None:
        payload["root_rotation_statements"] = root_rotation_statements
    if password_policy is not None:
        payload["password_policy"] = password_policy

    try:
        vault.query("POST", endpoint, __opts__, __context__, payload=payload)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err

    if not rotate:
        return True
    return rotate_root(name, mount=mount)


def delete_connection(name, mount="database"):
    """
    Delete a configured database connection. Returns None if it does not exist.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#delete-connection>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.delete_connection mydb

    name
        The name of the database connection.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/config/{name}"
    try:
        return vault.query("DELETE", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def reset_connection(name, mount="database"):
    """
    Close a connection and restart its plugin with the configuration stored in the barrier.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#reset-connection>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.reset_connection mydb

    name
        The name of the database connection.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/reset/{name}"
    try:
        return vault.query("POST", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def rotate_root(name, mount="database"):
    """
    Rotate the "root" user credentials stored for the database connection.

    .. warning::

        The rotated password will not be accessible, so it is highly recommended to create
        a dedicated user account as Vault's configured "root".

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#rotate-root-credentials>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.rotate_root mydb

    name
        The name of the database connection.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/rotate-root/{name}"
    try:
        return vault.query("POST", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def list_roles(static=False, mount="database"):
    """
    List configured database roles.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#list-roles>`_.
    `API method docs static <https://www.vaultproject.io/api-docs/secret/databases#list-static-roles>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.list_roles

    static
        Whether to list static roles. Defaults to False.

    mount
        The mount path the DB backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/{'static-' if static else ''}roles"
    try:
        return vault.query("LIST", endpoint, __opts__, __context__)["data"]["keys"]
    except vault.VaultNotFoundError:
        return []
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def fetch_role(name, static=False, mount="database"):
    """
    Read a configured database role. Returns None if it does not exist.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#read-role>`_.
    `API method docs static <https://www.vaultproject.io/api-docs/secret/databases#read-static-role>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.fetch_role myrole

    name
        The name of the database role.

    static
        Whether this role is static. Defaults to False.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/{'static-' if static else ''}roles/{name}"
    try:
        return vault.query("GET", endpoint, __opts__, __context__)["data"]
    except vault.VaultNotFoundError:
        return None
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def write_static_role(
    name,
    connection,
    username,
    rotation_period,
    rotation_statements=None,
    credential_type=None,
    credential_config=None,
    mount="database",
):
    """
    Create/update a database Static Role. Mind that not all databases support Static Roles.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#write-static-role>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.write_static_role myrole mydb myuser 24h

    name
        The name of the database role.

    connection
        The name of the database connection this role applies to.

    username
        The username to manage.

    rotation_period
        Specifies the amount of time Vault should wait before rotating the password.
        The minimum is ``5s``.

    rotation_statements
        Specifies the database statements to be executed to rotate the password for the
        configured database user. Not every plugin type will support this functionality.

    credential_type
        Specifies the type of credential that will be generated for the role.
        Options include: ``password``, ``rsa_private_key``. Defaults to ``password``.
        See the plugin's API page for credential types supported by individual databases.

    credential_config
        Specifies the configuration for the given ``credential_type`` as a mapping.
        For ``password``, only ``password_policy`` can be passed.
        For ``rsa_private_key``, ``key_bits`` (defaults to 2048) and ``format``
        (defaults to ``pkcs8``) are available.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    payload = {
        "username": username,
        "rotation_period": rotation_period,
    }
    if rotation_statements is not None:
        payload["rotation_statements"] = rotation_statements
    return _write_role(
        name,
        connection,
        payload,
        credential_type=credential_type,
        credential_config=credential_config,
        static=True,
        mount=mount,
    )


def write_role(
    name,
    connection,
    creation_statements,
    default_ttl=None,
    max_ttl=None,
    revocation_statements=None,
    rollback_statements=None,
    renew_statements=None,
    credential_type=None,
    credential_config=None,
    mount="database",
):
    r"""
    Create/update a regular database role.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#write-role>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.write_role myrole mydb \
                \["CREATE USER '{{name}}'@'%' IDENTIFIED BY '{{password}}'", "GRANT SELECT ON *.* TO '{{name}}'@'%'"\]

    name
        The name of the database role.

    connection
        The name of the database connection this role applies to.

    creation_statements
        Specifies a list of database statements executed to create and configure a user,
        usually templated with {{name}} and {{password}}. Required.

    default_ttl
        Specifies the TTL for the leases associated with this role. Accepts time suffixed
        strings (1h) or an integer number of seconds. Defaults to system/engine default TTL time.

    max_ttl
        Specifies the maximum TTL for the leases associated with this role. Accepts time suffixed
        strings (1h) or an integer number of seconds. Defaults to sys/mounts's default TTL time;
        this value is allowed to be less than the mount max TTL (or, if not set,
        the system max TTL), but it is not allowed to be longer.

    revocation_statements
        Specifies a list of database statements to be executed to revoke a user.

    rollback_statements
        Specifies a list of database statements to be executed to rollback a create operation
        in the event of an error. Availability and formatting depend on the specific plugin.

    renew_statements
        Specifies a list of database statements to be executed to renew a user.
        Availability and formatting depend on the specific plugin.

    credential_type
        Specifies the type of credential that will be generated for the role.
        Options include: ``password``, ``rsa_private_key``. Defaults to ``password``.
        See the plugin's API page for credential types supported by individual databases.

    credential_config
        Specifies the configuration for the given ``credential_type`` as a mapping.
        For ``password``, only ``password_policy`` can be passed.
        For ``rsa_private_key``, ``key_bits`` (defaults to 2048) and ``format``
        (defaults to ``pkcs8``) are available.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    payload = {
        "creation_statements": creation_statements,
    }
    if default_ttl is not None:
        payload["default_ttl"] = default_ttl
    if max_ttl is not None:
        payload["max_ttl"] = max_ttl
    if revocation_statements is not None:
        payload["revocation_statements"] = revocation_statements
    if rollback_statements is not None:
        payload["rollback_statements"] = rollback_statements
    if renew_statements is not None:
        payload["renew_statements"] = renew_statements
    return _write_role(
        name,
        connection,
        payload,
        credential_type=credential_type,
        credential_config=credential_config,
        static=False,
        mount=mount,
    )


def _write_role(
    name,
    connection,
    payload,
    credential_type=None,
    credential_config=None,
    static=False,
    mount="database",
):
    endpoint = f"{mount}/{'static-' if static else ''}roles/{name}"
    payload["db_name"] = connection
    if credential_type is not None:
        payload["credential_type"] = credential_type
    if credential_config is not None:
        valid_cred_configs = {
            "password": ["password_policy"],
            "rsa_private_key": ["key_bits", "format"],
        }
        credential_type = credential_type or "password"
        if credential_type in valid_cred_configs:
            invalid_configs = set(credential_config) - set(
                valid_cred_configs[credential_type]
            )
            if invalid_configs:
                raise SaltInvocationError(
                    f"The following options are invalid for credential type {credential_type}: {invalid_configs}"
                )
        payload["credential_config"] = credential_config
    try:
        return vault.query("POST", endpoint, __opts__, __context__, payload=payload)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def delete_role(name, static=False, mount="database"):
    """
    Delete a configured database role.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#delete-role>`_.
    `API method docs static <https://www.vaultproject.io/api-docs/secret/databases#delete-static-role>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.delete_role myrole

    name
        The name of the database role.

    static
        Whether this role is static. Defaults to False.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/{'static-' if static else ''}roles/{name}"
    try:
        return vault.query("DELETE", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def get_creds(name, static=False, cache=True, valid_for=0, mount="database"):
    """
    Read credentials based on the named role.

    `API method docs <https://www.vaultproject.io/api-docs/secret/databases#generate-credentials>`_.
    `API method docs static <https://www.vaultproject.io/api-docs/secret/databases#get-static-credentials>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.get_creds myrole

    name
        The name of the database role.

    static
        Whether this role is static. Defaults to False.

    cache
        Whether to use cached credentials local to this minion to avoid
        unnecessary reissuance.
        When ``static`` is false, set this to a string to be able to use multiple
        distinct credentials using the same role on the same minion.
        Set this to false to disable caching.
        Defaults to true.

        .. note::

            This uses the same cache backend as the Vault integration, so make
            sure you configure a persistent backend like ``disk`` if you expect
            the credentials to survive a single run.


    valid_for
        When using cache, ensure the credentials are valid for at least this
        amount of time, otherwise request new ones.
        This can be an integer, which will be interpreted as seconds, or a time string
        using the same format as Vault does:
        Suffix ``s`` for seconds, ``m`` for minuts, ``h`` for hours, ``d`` for days.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/{'static-' if static else ''}creds/{name}"

    if cache:
        ckey = f"db.{mount}.{'static' if static else 'dynamic'}.{name}"
        if not static and isinstance(cache, str):
            ckey += f".{cache}"
        else:
            ckey += ".default"
        creds_cache = vault.get_lease_store(__opts__, __context__)
        cached_creds = creds_cache.get(ckey, valid_for=valid_for)
        if cached_creds:
            return cached_creds.data

    try:
        res = vault.query("GET", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err

    lease = vault.VaultLease(**res)
    if cache:
        creds_cache.store(ckey, lease)
    return lease.data


def rotate_static_role(name, mount="database"):
    """
    Rotate Static Role credentials stored for a given role name.

    `API method docs static <https://www.vaultproject.io/api-docs/secret/databases#rotate-static-role>`_.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.rotate_static_role mystaticrole

    name
        The name of the database role.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    endpoint = f"{mount}/rotate-role/{name}"
    try:
        return vault.query("POST", endpoint, __opts__, __context__)
    except vault.VaultException as err:
        raise CommandExecutionError(f"{err.__class__}: {err}") from err


def get_plugin_name(plugin):
    """
    Get the name of a plugin as rendered by this module. This is a utility for the state
    module primarily and should be in a utils module.

    CLI Example:

    .. code-block:: bash

            salt '*' vault_db.get_plugin_name hanadb

    plugin
        The name of the database plugin.
    """
    plugin_name = PLUGINS.get(plugin, "default")["name"] or plugin
    return f"{plugin_name}-database-plugin"
