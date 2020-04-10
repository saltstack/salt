# -*- coding: utf-8 -*-
"""
Management of Microsoft SQLServer Databases
===========================================

The mssql_role module is used to create
and manage SQL Server Roles

.. code-block:: yaml

    yolo:
      mssql_role.present
"""
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    """
    Only load if the mssql module is present
    """
    return "mssql.version" in __salt__


def present(name, owner=None, grants=None, **kwargs):
    """
    Ensure that the named database is present with the specified options

    name
        The name of the database to manage
    owner
        Adds owner using AUTHORIZATION option
    Grants
        Can only be a list of strings
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if __salt__["mssql.role_exists"](name, **kwargs):
        ret[
            "comment"
        ] = "Role {0} is already present (Not going to try to set its grants)".format(
            name
        )
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Role {0} is set to be added".format(name)
        return ret

    role_created = __salt__["mssql.role_create"](
        name, owner=owner, grants=grants, **kwargs
    )
    if (
        role_created is not True
    ):  # Non-empty strings are also evaluated to True, so we cannot use if not role_created:
        ret["result"] = False
        ret["comment"] += "Role {0} failed to be created: {1}".format(
            name, role_created
        )
        return ret
    ret["comment"] += "Role {0} has been added".format(name)
    ret["changes"][name] = "Present"
    return ret


def absent(name, **kwargs):
    """
    Ensure that the named database is absent

    name
        The name of the database to remove
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not __salt__["mssql.role_exists"](name):
        ret["comment"] = "Role {0} is not present".format(name)
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = "Role {0} is set to be removed".format(name)
        return ret
    if __salt__["mssql.role_remove"](name, **kwargs):
        ret["comment"] = "Role {0} has been removed".format(name)
        ret["changes"][name] = "Absent"
        return ret
    # else:
    ret["result"] = False
    ret["comment"] = "Role {0} failed to be removed".format(name)
    return ret
