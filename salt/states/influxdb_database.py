"""
Management of Influxdb databases
================================

(compatible with InfluxDB version 0.9+)
"""


def __virtual__():
    """
    Only load if the influxdb module is available
    """
    if "influxdb.db_exists" in __salt__:
        return "influxdb_database"
    return (False, "influxdb module could not be loaded")


def present(name, **client_args):
    """
    Ensure that given database is present.

    name
        Name of the database to create.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Database {name} is already present",
    }

    if not __salt__["influxdb.db_exists"](name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = f"Database {name} is absent and will be created"
            return ret
        if __salt__["influxdb.create_db"](name, **client_args):
            ret["comment"] = f"Database {name} has been created"
            ret["changes"][name] = "Present"
            return ret
        else:
            ret["comment"] = f"Failed to create database {name}"
            ret["result"] = False
            return ret

    return ret


def absent(name, **client_args):
    """
    Ensure that given database is absent.

    name
        Name of the database to remove.
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Database {name} is not present",
    }

    if __salt__["influxdb.db_exists"](name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Database {} is present and needs to be removed".format(
                name
            )
            return ret
        if __salt__["influxdb.drop_db"](name, **client_args):
            ret["comment"] = f"Database {name} has been removed"
            ret["changes"][name] = "Absent"
            return ret
        else:
            ret["comment"] = f"Failed to remove database {name}"
            ret["result"] = False
            return ret

    return ret
