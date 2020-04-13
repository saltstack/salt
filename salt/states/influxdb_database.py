# -*- coding: utf-8 -*-
"""
Management of Influxdb databases
================================

(compatible with InfluxDB version 0.9+)
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the influxdb module is available
    """
    if "influxdb.db_exists" in __salt__:
        return "influxdb_database"
    return False


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
        "comment": "Database {0} is already present".format(name),
    }

    if not __salt__["influxdb.db_exists"](name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Database {0} is absent and will be created".format(name)
            return ret
        if __salt__["influxdb.create_db"](name, **client_args):
            ret["comment"] = "Database {0} has been created".format(name)
            ret["changes"][name] = "Present"
            return ret
        else:
            ret["comment"] = "Failed to create database {0}".format(name)
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
        "comment": "Database {0} is not present".format(name),
    }

    if __salt__["influxdb.db_exists"](name, **client_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Database {0} is present and needs to be removed".format(
                name
            )
            return ret
        if __salt__["influxdb.drop_db"](name, **client_args):
            ret["comment"] = "Database {0} has been removed".format(name)
            ret["changes"][name] = "Absent"
            return ret
        else:
            ret["comment"] = "Failed to remove database {0}".format(name)
            ret["result"] = False
            return ret

    return ret
