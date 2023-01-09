"""
Manage the Vault database secret engine.

Configuration instructions are documented in the :ref:`vault execution module docs <vault-setup>`.

.. versionadded:: 3007.0
"""

import logging

import salt.utils.vault as vault
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


def connection_present(
    name,
    plugin,
    version=None,
    verify=True,
    allowed_roles=None,
    root_rotation_statements=None,
    password_policy=None,
    rotate=True,
    force=False,
    mount="database",
    **kwargs,
):
    """
    Ensure a database connection is present as specified.

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

    force
        When the plugin changes, this state fails to protect from accidental errors.
        Set force to True to delete existing connections with the same name and a
        different plugin type. Defaults to False.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.

    kwargs
        Different plugins require different parameters. You need to make sure that you pass them
        as supplemental keyword arguments. For known plugins, the required arguments will
        be checked.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}

    def _diff_params(current):
        nonlocal version, allowed_roles, root_rotation_statements, password_policy, kwargs
        diff_params = (
            ("plugin_version", version),
            ("allowed_roles", allowed_roles),
            ("root_credentials_rotate_statements", root_rotation_statements),
            ("password_policy", password_policy),
        )
        changed = {}
        for param, arg in diff_params:
            if arg is None:
                continue
            if param not in current or current[param] != arg:
                changed.update({param: {"old": current.get(param), "new": arg}})
        for param, val in kwargs.items():
            if param == "password":
                # password is not reported
                continue
            if (
                param not in current["connection_details"]
                or current["connection_details"][param] != val
            ):
                changed.update({param: {"old": current.get(param), "new": val}})
        return changed

    try:
        current = __salt__["vault_db.fetch_connection"](name, mount=mount)
        changes = {}

        if current:
            if current["plugin_name"] != __salt__["vault_db.get_plugin_name"](plugin):
                if not force:
                    raise CommandExecutionError(
                        "Cannot change plugin type without deleting the existing connection. "
                        "Set force: true to override."
                    )
                if not __opts__["test"]:
                    __salt__["vault_db.delete_connection"](name, mount=mount)
                ret["changes"]["deleted for plugin change"] = name
                current = None
            else:
                changes = _diff_params(current)
                if not changes:
                    ret["comment"] = "Connection is present as specified"
                    return ret

        if __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = f"Connection `{name}` would have been {'updated' if current else 'created'}"
            ret["changes"].update(changes)
            if not current:
                ret["changes"]["created"] = name
            return ret

        if current and "password" in kwargs:
            kwargs.pop("password")

        __salt__["vault_db.write_connection"](
            name,
            plugin,
            version=version,
            verify=verify,
            allowed_roles=allowed_roles,
            root_rotation_statements=root_rotation_statements,
            password_policy=password_policy,
            rotate=rotate,
            mount=mount,
            **kwargs,
        )
        new = __salt__["vault_db.fetch_connection"](name, mount=mount)

        if new is None:
            raise CommandExecutionError(
                "There were no errors during role management, but it is reported as absent."
            )
        if not current:
            ret["changes"]["created"] = name

        new_diff = _diff_params(new)
        if new_diff:
            ret["result"] = False
            ret["comment"] = (
                "There were no errors during connection management, but "
                f"the reported parameters do not match: {new_diff}"
            )
            return ret
        ret["changes"].update(changes)

    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        # do not reset changes

    return ret


def connection_absent(name, mount="database"):
    """
    Ensure a database connection is absent.

    name
        The name of the connection.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        current = __salt__["vault_db.fetch_connection"](name, mount=mount)

        if current is None:
            ret["comment"] = f"Connection `{name}` is already absent."
            return ret

        ret["changes"]["deleted"] = name

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Connection `{name}` would have been deleted."
            return ret

        __salt__["vault_db.delete_connection"](name, mount=mount)

        if __salt__["vault_db.fetch_connection"](name, mount=mount) is not None:
            raise CommandExecutionError(
                "There were no errors during connection deletion, "
                "but it is still reported as present."
            )
        ret["comment"] = f"Connection `{name}` has been deleted."

    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}

    return ret


def role_present(
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
    """
    Ensure a regular database role is present as specified.

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
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if not isinstance(creation_statements, list):
        creation_statements = [creation_statements]
    if revocation_statements and not isinstance(revocation_statements, list):
        revocation_statements = [revocation_statements]
    if rollback_statements and not isinstance(rollback_statements, list):
        rollback_statements = [rollback_statements]
    if renew_statements and not isinstance(renew_statements, list):
        renew_statements = [renew_statements]

    def _diff_params(current):
        nonlocal connection, creation_statements, default_ttl, max_ttl, revocation_statements
        nonlocal rollback_statements, renew_statements, credential_type, credential_config

        diff_params = (
            ("db_name", connection),
            ("creation_statements", creation_statements),
            ("default_ttl", vault.timestring_map(default_ttl)),
            ("max_ttl", vault.timestring_map(max_ttl)),
            ("revocation_statements", revocation_statements),
            ("rollback_statements", rollback_statements),
            ("renew_statements", renew_statements),
            ("credential_type", credential_type),
            ("credential_config", credential_config),
        )
        changed = {}
        for param, arg in diff_params:
            if arg is None:
                continue
            if param not in current or current[param] != arg:
                changed.update({param: {"old": current.get(param), "new": arg}})
        return changed

    try:
        current = __salt__["vault_db.fetch_role"](name, static=False, mount=mount)

        if current:
            changed = _diff_params(current)
            if not changed:
                ret["comment"] = "Role is present as specified"
                return ret
            ret["changes"].update(changed)

        if __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = f"Role `{name}` would have been {'updated' if current else 'created'}"
            if not current:
                ret["changes"]["created"] = name
            return ret

        __salt__["vault_db.write_role"](
            name,
            connection,
            creation_statements,
            default_ttl=default_ttl,
            max_ttl=max_ttl,
            revocation_statements=revocation_statements,
            rollback_statements=rollback_statements,
            renew_statements=renew_statements,
            credential_type=credential_type,
            credential_config=credential_config,
            mount=mount,
        )
        new = __salt__["vault_db.fetch_role"](name, static=False, mount=mount)

        if new is None:
            raise CommandExecutionError(
                "There were no errors during role management, but it is reported as absent."
            )

        if not current:
            ret["changes"]["created"] = name

        new_diff = _diff_params(new)
        if new_diff:
            ret["result"] = False
            ret["comment"] = (
                "There were no errors during role management, but "
                f"the reported parameters do not match: {new_diff}"
            )
            return ret

    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}

    return ret


def role_absent(name, static=False, mount="database"):
    """
    Ensure a database role is absent.

    name
        The name of the role.

    static
        Whether this role is static. Defaults to False.

    mount
        The mount path the database backend is mounted to. Defaults to ``database``.
    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    try:
        current = __salt__["vault_db.fetch_role"](name, static=static, mount=mount)

        if current is None:
            ret["comment"] = f"Role `{name}` is already absent."
            return ret

        ret["changes"]["deleted"] = name

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Role `{name}` would have been deleted."
            return ret

        __salt__["vault_db.delete_role"](name, static=static, mount=mount)

        if (
            __salt__["vault_db.fetch_role"](name, static=static, mount=mount)
            is not None
        ):
            raise CommandExecutionError(
                "There were no errors during role deletion, but it is still reported as present."
            )
        ret["comment"] = f"Role `{name}` has been deleted."

    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}

    return ret


def static_role_present(
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
    Ensure a database Static Role is present as specified.

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
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if rotation_statements and not isinstance(rotation_statements, list):
        rotation_statements = [rotation_statements]

    def _diff_params(current):
        nonlocal connection, username, rotation_period, rotation_statements, credential_type, credential_config
        diff_params = (
            ("db_name", connection),
            ("username", username),
            ("rotation_period", vault.timestring_map(rotation_period)),
            ("rotation_statements", rotation_statements),
            ("credential_type", credential_type),
            ("credential_config", credential_config),
        )
        changed = {}
        for param, arg in diff_params:
            if arg is None:
                continue
            if param not in current or current[param] != arg:
                changed.update({param: {"old": current.get(param), "new": arg}})
        return changed

    try:
        current = __salt__["vault_db.fetch_role"](name, static=True, mount=mount)

        if current:
            changed = _diff_params(current)
            if not changed:
                ret["comment"] = "Role is present as specified"
                return ret
            ret["changes"].update(changed)

        if __opts__["test"]:
            ret["result"] = None
            ret[
                "comment"
            ] = f"Role `{name}` would have been {'updated' if current else 'created'}"
            if not current:
                ret["changes"]["created"] = name
            return ret

        __salt__["vault_db.write_static_role"](
            name,
            connection,
            username,
            rotation_period,
            rotation_statements=None,
            credential_type=credential_type,
            credential_config=credential_config,
            mount=mount,
        )
        new = __salt__["vault_db.fetch_role"](name, static=True, mount=mount)

        if new is None:
            raise CommandExecutionError(
                "There were no errors during role management, but it is reported as absent."
            )

        if not current:
            ret["changes"]["created"] = name

        new_diff = _diff_params(new)
        if new_diff:
            ret["result"] = False
            ret["comment"] = (
                "There were no errors during role management, but "
                f"the reported parameters do not match: {new_diff}"
            )
            return ret

    except (CommandExecutionError, SaltInvocationError) as err:
        ret["result"] = False
        ret["comment"] = str(err)
        ret["changes"] = {}

    return ret
