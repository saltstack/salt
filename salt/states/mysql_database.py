# -*- coding: utf-8 -*-
"""
Management of MySQL databases (schemas)
=======================================

:depends:   - MySQLdb Python module
:configuration: See :py:mod:`salt.modules.mysql` for setup instructions.

The mysql_database module is used to create and manage MySQL databases.
Databases can be set as either absent or present.

.. code-block:: yaml

    frank:
      mysql_database.present
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging
import sys

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the mysql module is available in __salt__
    """
    return "mysql.db_exists" in __salt__


def _get_mysql_error():
    """
    Look in module context for a MySQL error. Eventually we should make a less
    ugly way of doing this.
    """
    return sys.modules[__salt__["test.ping"].__module__].__context__.pop(
        "mysql.error", None
    )


def present(name, character_set=None, collate=None, **connection_args):
    """
    Ensure that the named database is present with the specified properties

    name
        The name of the database to manage
    """
    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "Database {0} is already present".format(name),
    }
    # check if database exists
    existing = __salt__["mysql.db_get"](name, **connection_args)
    if existing:
        alter = False
        if character_set and character_set != existing.get("character_set"):
            log.debug(
                "character set differes from %s : %s",
                character_set,
                existing.get("character_set"),
            )
            alter = True
        if collate and collate != existing.get("collate"):
            log.debug(
                "collate set differs from %s : %s", collate, existing.get("collate")
            )
            alter = True
        if alter:
            __salt__["mysql.alter_db"](
                name, character_set=character_set, collate=collate, **connection_args
            )
        current = __salt__["mysql.db_get"](name, **connection_args)
        if existing.get("collate", None) != current.get("collate", None):
            ret["changes"].update(
                {
                    "collate": {
                        "before": existing.get("collate", None),
                        "now": current.get("collate", None),
                    }
                }
            )
        if existing.get("character_set", None) != current.get("character_set", None):
            ret["changes"].update(
                {
                    "character_set": {
                        "before": existing.get("character_set", None),
                        "now": current.get("character_set", None),
                    }
                }
            )
        return ret
    else:
        err = _get_mysql_error()
        if err is not None:
            ret["comment"] = err
            ret["result"] = False
            return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = ("Database {0} is not present and needs to be created").format(
            name
        )
        return ret
    # The database is not present, make it!
    if __salt__["mysql.db_create"](
        name, character_set=character_set, collate=collate, **connection_args
    ):
        ret["comment"] = "The database {0} has been created".format(name)
        ret["changes"][name] = "Present"
    else:
        ret["comment"] = "Failed to create database {0}".format(name)
        err = _get_mysql_error()
        if err is not None:
            ret["comment"] += " ({0})".format(err)
        ret["result"] = False

    return ret


def absent(name, **connection_args):
    """
    Ensure that the named database is absent

    name
        The name of the database to remove
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    # check if db exists and remove it
    if __salt__["mysql.db_exists"](name, **connection_args):
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Database {0} is present and needs to be removed".format(
                name
            )
            return ret
        if __salt__["mysql.db_remove"](name, **connection_args):
            ret["comment"] = "Database {0} has been removed".format(name)
            ret["changes"][name] = "Absent"
            return ret
        else:
            err = _get_mysql_error()
            if err is not None:
                ret["comment"] = "Unable to remove database {0} " "({1})".format(
                    name, err
                )
                ret["result"] = False
                return ret
    else:
        err = _get_mysql_error()
        if err is not None:
            ret["comment"] = err
            ret["result"] = False
            return ret

    # fallback
    ret["comment"] = ("Database {0} is not present, so it cannot be removed").format(
        name
    )
    return ret
