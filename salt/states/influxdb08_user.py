"""
Management of InfluxDB 0.8 users
================================

(compatible with InfluxDB version 0.5-0.8)

.. versionadded:: 2014.7.0

"""


def __virtual__():
    """
    Only load if the influxdb08 module is available
    """
    if "influxdb08.db_exists" in __salt__:
        return "influxdb08_user"
    return (False, "influxdb08 module could not be loaded")


def present(
    name, passwd, database=None, user=None, password=None, host=None, port=None
):
    """
    Ensure that the cluster admin or database user is present.

    name
        The name of the user to manage

    passwd
        The password of the user

    database
        The database to create the user in

    user
        The user to connect as (must be able to create the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # check if db does not exist
    if database and not __salt__["influxdb08.db_exists"](
        database, user, password, host, port
    ):
        ret["result"] = False
        ret["comment"] = f"Database {database} does not exist"
        return ret

    # check if user exists
    if not __salt__["influxdb08.user_exists"](
        name, database, user, password, host, port
    ):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "User {} is not present and needs to be created".format(
                name
            )
            return ret
        # The user is not present, make it!
        if __salt__["influxdb08.user_create"](
            name, passwd, database, user, password, host, port
        ):
            ret["comment"] = f"User {name} has been created"
            ret["changes"][name] = "Present"
            return ret
        else:
            ret["comment"] = f"Failed to create user {name}"
            ret["result"] = False
            return ret

    # fallback
    ret["comment"] = f"User {name} is already present"
    return ret


def absent(name, database=None, user=None, password=None, host=None, port=None):
    """
    Ensure that the named cluster admin or database user is absent.

    name
        The name of the user to remove

    database
        The database to remove the user from

    user
        The user to connect as (must be able to remove the user)

    password
        The password of the user

    host
        The host to connect to

    port
        The port to connect to

    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # check if user exists and remove it
    if __salt__["influxdb08.user_exists"](name, database, user, password, host, port):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"User {name} is present and needs to be removed"
            return ret
        if __salt__["influxdb08.user_remove"](
            name, database, user, password, host, port
        ):
            ret["comment"] = f"User {name} has been removed"
            ret["changes"][name] = "Absent"
            return ret
        else:
            ret["comment"] = f"Failed to remove user {name}"
            ret["result"] = False
            return ret

    # fallback
    ret["comment"] = f"User {name} is not present, so it cannot be removed"
    return ret
