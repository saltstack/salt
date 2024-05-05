"""
Writing/reading defaults from a macOS minion
============================================

"""

import logging
import re

import salt.utils.platform

log = logging.getLogger(__name__)

__virtualname__ = "macdefaults"


def __virtual__():
    """
    Only work on macOS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return (False, "Only supported on macOS")


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

    current_value = __salt__["macdefaults.read"](domain, name, user)
    value = _cast_value(value, vtype)

    if _compare_values(value, current_value, strict=re.match(r"-add$", vtype) is None):
        ret["comment"] += f"{domain} {name} is already set to {value}"
    else:
        out = __salt__["macdefaults.write"](domain, name, value, vtype, user)
        if out["retcode"] != 0:
            ret["result"] = False
            ret["comment"] = f"Failed to write default. {out['stdout']}"
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


def _compare_values(new, current, strict=True):
    """
    Compare two values

    new
        The new value to compare

    current
        The current value to compare

    strict
        If True, the values must be exactly the same, if False, the new value
        must be in the current value
    """
    if strict:
        return new == current
    return new in current


def _cast_value(value, vtype):
    def safe_cast(val, to_type, default=None):
        try:
            return to_type(val)
        except ValueError:
            return default

    if vtype in ("bool", "boolean"):
        if value not in [True, "TRUE", "YES", False, "FALSE", "NO"]:
            raise ValueError(f"Invalid value for boolean: {value}")
        return value in [True, "TRUE", "YES"]

    if vtype in ("int", "integer"):
        return safe_cast(value, int)

    if vtype == "float":
        return safe_cast(value, float)

    if vtype in ("dict", "dict-add"):
        return safe_cast(value, dict)

    if vtype in ["array", "array-add"]:
        return safe_cast(value, list)

    return value
