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
        return _is_subarray(new, current)
    if vtype == "dict-add":
        return all(key in current and new[key] == current[key] for key in new.keys())

    return new == current


def _is_subarray(new, current):
    """
    Check if new is a subarray of current array.

    This method does not check only whether all elements in new array
    are present in current array, but also whether the elements are in
    the same order.

    new
        The new array to compare

    current
        The current array to compare

    """
    current_len = len(current)
    new_len = len(new)

    if new_len == 0:
        return True
    if new_len > current_len:
        return False

    for i in range(current_len - new_len + 1):
        # Check if the new array is found at this position
        if current[i : i + new_len] == new:
            return True

    return False


def _cast_value(value, vtype):
    """
    Cast the given macOS default value to Python type

    value
        The value to cast from macOS default

    vtype
        The type to cast the value from

    """

    def safe_cast(val, to_type, default=None):
        """
        Auxiliary function to safely cast a value to a given type

        """
        try:
            return to_type(val)
        except ValueError:
            return default

    if vtype in ("bool", "boolean"):
        if value not in [True, 1, "TRUE", "YES", False, 0, "FALSE", "NO"]:
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
