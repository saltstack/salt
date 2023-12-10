"""
Module for apcupsd
"""

import logging

import salt.utils.decorators as decorators
import salt.utils.path

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "apcups"


@decorators.memoize
def _check_apcaccess():
    """
    Looks to see if apcaccess is present on the system
    """
    return salt.utils.path.which("apcaccess")


def __virtual__():
    """
    Provides apcupsd only if apcaccess is present
    """
    if _check_apcaccess():
        return __virtualname__
    return (
        False,
        "{} module can only be loaded on when apcupsd is installed".format(
            __virtualname__
        ),
    )


def status():
    """
    Return apcaccess output

    CLI Example:

    .. code-block:: bash

        salt '*' apcups.status
    """
    ret = {}
    apcaccess = _check_apcaccess()
    res = __salt__["cmd.run_all"](apcaccess)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = "Something with wrong executing apcaccess, is apcupsd running?"
        return ret

    for line in res["stdout"].splitlines():
        line = line.split(":")
        ret[line[0].strip()] = line[1].strip()

    return ret


def status_load():
    """
    Return load

    CLI Example:

    .. code-block:: bash

        salt '*' apcups.status_load
    """
    data = status()
    if "LOADPCT" in data:
        load = data["LOADPCT"].split()
        if load[1].lower() == "percent":
            return float(load[0])

    return {"Error": "Load not available."}


def status_charge():
    """
    Return battery charge

    CLI Example:

    .. code-block:: bash

        salt '*' apcups.status_charge
    """
    data = status()
    if "BCHARGE" in data:
        charge = data["BCHARGE"].split()
        if charge[1].lower() == "percent":
            return float(charge[0])

    return {"Error": "Load not available."}


def status_battery():
    """
    Return true if running on battery power

    CLI Example:

    .. code-block:: bash

        salt '*' apcups.status_battery
    """
    data = status()
    if "TONBATT" in data:
        return not data["TONBATT"] == "0 Seconds"

    return {"Error": "Battery status not available."}
