"""
Writing/reading defaults from a macOS minion
============================================

"""

import logging

import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "macdefaults"


def __virtual__():
    """
    Only work on Mac OS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return (False, "Only supported on Mac OS")


def write(name, domain, value, vtype="string", user=None):
    """
    Write a default to the system

    name
        The key of the given domain to write to

    domain
        The name of the domain to write to

    value
        The value to write to the given key

    vtype
        The type of value to be written, valid types are string, data, int[eger],
        float, bool[ean], date, array, array-add, dict, dict-add

    user
        The user to write the defaults to


    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    def safe_cast(val, to_type, default=None):
        try:
            return to_type(val)
        except ValueError:
            return default

    current_value = __salt__["macdefaults.read"](domain, name, user)

    if (vtype in ["bool", "boolean"]) and (
        (value in [True, "TRUE", "YES"] and current_value == "1")
        or (value in [False, "FALSE", "NO"] and current_value == "0")
    ):
        ret["comment"] += f"{domain} {name} is already set to {value}"
    elif vtype in ["int", "integer"] and safe_cast(current_value, int) == safe_cast(
        value, int
    ):
        ret["comment"] += f"{domain} {name} is already set to {value}"
    elif current_value == value:
        ret["comment"] += f"{domain} {name} is already set to {value}"
    else:
        out = __salt__["macdefaults.write"](domain, name, value, vtype, user)
        if out["retcode"] != 0:
            ret["result"] = False
            ret["comment"] = "Failed to write default. {}".format(out["stdout"])
        else:
            ret["changes"]["written"] = f"{domain} {name} is set to {value}"

    return ret


def absent(name, domain, user=None):
    """
    Make sure the defaults value is absent

    name
        The key of the given domain to remove

    domain
        The name of the domain to remove from

    user
        The user to write the defaults to


    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    out = __salt__["macdefaults.delete"](domain, name, user)

    if out["retcode"] != 0:
        ret["comment"] += f"{domain} {name} is already absent"
    else:
        ret["changes"]["absent"] = f"{domain} {name} is now absent"

    return ret
