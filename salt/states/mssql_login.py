"""
Management of Microsoft SQLServer Logins
========================================

The mssql_login module is used to create
and manage SQL Server Logins

.. code-block:: yaml

    frank:
      mssql_login.present
        - domain: mydomain
"""

import collections


def __virtual__():
    """
    Only load if the mssql module is present
    """
    if "mssql.version" in __salt__:
        return True
    return (False, "mssql module could not be loaded")


def _normalize_options(options):
    if type(options) in [dict, collections.OrderedDict]:
        return [f"{k}={v}" for k, v in options.items()]
    if type(options) is list and (not options or type(options[0]) is str):
        return options
    # Invalid options
    if type(options) is not list or type(options[0]) not in [
        dict,
        collections.OrderedDict,
    ]:
        return []
    return [o for d in options for o in _normalize_options(d)]


def present(
    name, password=None, domain=None, server_roles=None, options=None, **kwargs
):
    """
    Checks existence of the named login.
    If not present, creates the login with the specified roles and options.

    name
        The name of the login to manage
    password
        Creates a SQL Server authentication login
        Since hashed passwords are varbinary values, if the
        new_login_password is 'long', it will be considered
        to be HASHED.
    domain
        Creates a Windows authentication login.
        Needs to be NetBIOS domain or hostname
    server_roles
        Add this login to all the server roles in the list
    options
        Can be a list of strings, a dictionary, or a list of dictionaries
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if bool(password) == bool(domain):
        ret["result"] = False
        ret["comment"] = "One and only one of password and domain should be specifies"
        return ret
    if __salt__["mssql.login_exists"](name, domain=domain, **kwargs):
        ret["comment"] = (
            "Login {} is already present (Not going to try to set its password)".format(
                name
            )
        )
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Login {name} is set to be added"
        return ret

    login_created = __salt__["mssql.login_create"](
        name,
        new_login_password=password,
        new_login_domain=domain,
        new_login_roles=server_roles,
        new_login_options=_normalize_options(options),
        **kwargs,
    )
    # Non-empty strings are also evaluated to True, so we cannot use if not login_created:
    if login_created is not True:
        ret["result"] = False
        ret["comment"] = f"Login {name} failed to be added: {login_created}"
        return ret
    ret["comment"] = f"Login {name} has been added. "
    ret["changes"][name] = "Present"
    return ret


def absent(name, **kwargs):
    """
    Ensure that the named login is absent

    name
        The name of the login to remove
    """
    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    if not __salt__["mssql.login_exists"](name):
        ret["comment"] = f"Login {name} is not present"
        return ret
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Login {name} is set to be removed"
        return ret
    if __salt__["mssql.login_remove"](name, **kwargs):
        ret["comment"] = f"Login {name} has been removed"
        ret["changes"][name] = "Absent"
        return ret
    # else:
    ret["result"] = False
    ret["comment"] = f"Login {name} failed to be removed"
    return ret
