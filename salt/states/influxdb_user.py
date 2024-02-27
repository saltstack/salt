"""
Management of InfluxDB users
============================

(compatible with InfluxDB version 0.9+)
"""


def __virtual__():
    """
    Only load if the influxdb module is available
    """
    if "influxdb.db_exists" in __salt__:
        return "influxdb_user"
    return (False, "influxdb module could not be loaded")


def present(name, passwd, admin=False, grants=None, **client_args):
    """
    Ensure that given user is present.

    name
        Name of the user to manage

    passwd
        Password of the user

    admin : False
        Whether the user should have cluster administration
        privileges or not.

    grants
        Optional - Dict of database:privilege items associated with
        the user. Example:

        grants:
          foo_db: read
          bar_db: all

    **Example:**

    .. code-block:: yaml

        example user present in influxdb:
          influxdb_user.present:
            - name: example
            - passwd: somepassword
            - admin: False
            - grants:
                foo_db: read
                bar_db: all
    """
    create = False
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"User {name} is present and up to date",
    }

    if not __salt__["influxdb.user_exists"](name, **client_args):
        create = True
        if __opts__["test"]:
            ret["comment"] = f"User {name} will be created"
            ret["result"] = None
            return ret
        else:
            if not __salt__["influxdb.create_user"](
                name, passwd, admin=admin, **client_args
            ):
                ret["comment"] = f"Failed to create user {name}"
                ret["result"] = False
                return ret
    else:
        user = __salt__["influxdb.user_info"](name, **client_args)

        if user["admin"] != admin:
            if not __opts__["test"]:
                if admin:
                    __salt__["influxdb.grant_admin_privileges"](name, **client_args)
                else:
                    __salt__["influxdb.revoke_admin_privileges"](name, **client_args)

                if (
                    admin
                    != __salt__["influxdb.user_info"](name, **client_args)["admin"]
                ):
                    ret["comment"] = "Failed to set admin privilege to user {}".format(
                        name
                    )
                    ret["result"] = False
                    return ret
            ret["changes"]["Admin privileges"] = admin

    if grants:
        db_privileges = __salt__["influxdb.list_privileges"](name, **client_args)
        for database, privilege in grants.items():
            privilege = privilege.lower()
            if privilege != db_privileges.get(database, privilege):
                if not __opts__["test"]:
                    __salt__["influxdb.revoke_privilege"](
                        database, "all", name, **client_args
                    )
                del db_privileges[database]
            if database not in db_privileges:
                ret["changes"][
                    f"Grant on database {database} to user {name}"
                ] = privilege
                if not __opts__["test"]:
                    __salt__["influxdb.grant_privilege"](
                        database, privilege, name, **client_args
                    )

    if ret["changes"]:
        if create:
            ret["comment"] = f"Created user {name}"
            ret["changes"][name] = "User created"
        else:
            if __opts__["test"]:
                ret["result"] = None
                ret["comment"] = (
                    f"User {name} will be updated with the following changes:"
                )
                for k, v in ret["changes"].items():
                    ret["comment"] += f"\n{k} => {v}"
                ret["changes"] = {}
            else:
                ret["comment"] = f"Updated user {name}"

    return ret


def absent(name, **client_args):
    """
    Ensure that given user is absent.

    name
        The name of the user to manage
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"User {name} is not present",
    }

    if __salt__["influxdb.user_exists"](name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"User {name} will be removed"
            return ret
        else:
            if __salt__["influxdb.remove_user"](name, **client_args):
                ret["comment"] = f"Removed user {name}"
                ret["changes"][name] = "removed"
                return ret
            else:
                ret["comment"] = f"Failed to remove user {name}"
                ret["result"] = False
                return ret
    return ret
