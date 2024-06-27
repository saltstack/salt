"""
Writing/reading defaults from a macOS minion
============================================

"""

import salt.utils.platform

__virtualname__ = "macdefaults"


def __virtual__():
    """
    Only work on macOS
    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return (False, "Only supported on macOS")


def write(name, domain, value, vtype=None, user=None):
    """
    Write a default to the system

    name
        The key of the given domain to write to.
        It can be a nested key/index separated by dots.

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

    if vtype is not None:
        value = __salt__["macdefaults.cast_value_to_vtype"](value, vtype)

    if _compare_values(value, current_value, vtype):
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
        The key of the given domain to remove.
        It can be a nested key/index separated by dots.

    domain
        The name of the domain to remove from

    user
        The user to write the defaults to

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    out = __salt__["macdefaults.delete"](domain, name, user)

    if out is None or out["retcode"] != 0:
        ret["comment"] += f"{domain} {name} is already absent"
    else:
        ret["changes"]["absent"] = f"{domain} {name} is now absent"

    return ret


def _compare_values(new, current, vtype):
    """
    Compare two values based on their type

    new
        The new value to compare

    current
        The current value to compare

    vtype
        The type of default value to be compared

    """
    if vtype == "array-add":
        if isinstance(new, list):
            return new == current[-len(new) :]
        return new == current[-1]

    if vtype == "dict-add":
        return all(key in current and new[key] == current[key] for key in new.keys())

    return new == current
