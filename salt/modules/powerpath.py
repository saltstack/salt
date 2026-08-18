"""
powerpath support.

Assumes RedHat

"""

import os
import re

POLICY_MAP_DICT = {
    "Adaptive": "ad",
    "CLAROpt": "co",
    "LeastBlocks": "lb",
    "LeastIos": "li",
    "REquest": "re",
    "RoundRobin": "rr",
    "StreamIo": "si",
    "SymmOpt": "so",
}

POLICY_RE = re.compile(".*policy=([^;]+)")


def has_powerpath():
    if os.path.exists("/sbin/emcpreg"):
        return True

    return False


def __virtual__():
    """
    Provide this only on Linux systems until proven to
    work elsewhere.
    """
    try:
        kernel_grain = __grains__["kernel"]
    except Exception:  # pylint: disable=broad-except
        return (
            False,
            "The powerpath execution module cannot be loaded: unable to detect kernel"
            " grain.",
        )

    if not has_powerpath():
        return (
            False,
            "The powerpath execution module cannot be loaded: the emcpreg binary is not"
            " available.",
        )

    if kernel_grain == "Linux":
        return "powerpath"

    return (
        False,
        "The powerpath execution module cannot be loaded: only available on Linux.",
    )


def list_licenses():
    """
    returns a list of applied powerpath license keys
    """
    KEY_PATTERN = re.compile("Key (.*)")

    keys = []
    out = __salt__["cmd.run"]("/sbin/emcpreg -list")
    for line in out.splitlines():
        match = KEY_PATTERN.match(line)

        if not match:
            continue

        keys.append({"key": match.group(1)})

    return keys


def add_license(key):
    """
    Add a license
    """
    result = {"result": False, "retcode": -1, "output": ""}

    if not has_powerpath():
        result["output"] = "PowerPath is not installed"
        return result

    cmd = f"/sbin/emcpreg -add {key}"
    ret = __salt__["cmd.run_all"](cmd, python_shell=True)

    result["retcode"] = ret["retcode"]

    if ret["retcode"] != 0:
        result["output"] = ret["stderr"]
    else:
        result["output"] = ret["stdout"]
        result["result"] = True

    return result


def remove_license(key):
    """
    Remove a license
    """
    result = {"result": False, "retcode": -1, "output": ""}

    if not has_powerpath():
        result["output"] = "PowerPath is not installed"
        return result

    cmd = f"/sbin/emcpreg -remove {key}"
    ret = __salt__["cmd.run_all"](cmd, python_shell=True)

    result["retcode"] = ret["retcode"]

    if ret["retcode"] != 0:
        result["output"] = ret["stderr"]
    else:
        result["output"] = ret["stdout"]
        result["result"] = True

    return result
