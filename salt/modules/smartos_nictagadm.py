"""
Module for running nictagadm command on SmartOS
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       nictagadm binary, dladm binary
:platform:      smartos

.. versionadded:: 2016.11.0

"""

import logging

import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {"list_nictags": "list"}

# Define the module's virtual name
__virtualname__ = "nictagadm"


def __virtual__():
    """
    Provides nictagadm on SmartOS
    """
    if (
        salt.utils.platform.is_smartos_globalzone()
        and salt.utils.path.which("dladm")
        and salt.utils.path.which("nictagadm")
    ):
        return __virtualname__
    return (
        False,
        "{} module can only be loaded on SmartOS compute nodes".format(__virtualname__),
    )


def list_nictags(include_etherstubs=True):
    """
    List all nictags

    include_etherstubs : boolean
        toggle include of etherstubs

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.list
    """
    ret = {}
    cmd = 'nictagadm list -d "|" -p{}'.format(" -L" if not include_etherstubs else "")
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = (
            res["stderr"] if "stderr" in res else "Failed to get list of nictags."
        )
    else:
        header = ["name", "macaddress", "link", "type"]
        for nictag in res["stdout"].splitlines():
            nictag = nictag.split("|")
            nictag_data = {}
            for field in header:
                nictag_data[field] = nictag[header.index(field)]
            ret[nictag_data["name"]] = nictag_data
            del ret[nictag_data["name"]]["name"]
    return ret


def vms(nictag):
    """
    List all vms connect to nictag

    nictag : string
        name of nictag

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.vms admin
    """
    ret = {}
    cmd = "nictagadm vms {}".format(nictag)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = (
            res["stderr"] if "stderr" in res else "Failed to get list of vms."
        )
    else:
        ret = res["stdout"].splitlines()
    return ret


def exists(*nictag, **kwargs):
    """
    Check if nictags exists

    nictag : string
        one or more nictags to check
    verbose : boolean
        return list of nictags

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.exists admin
    """
    ret = {}
    if not nictag:
        return {"Error": "Please provide at least one nictag to check."}

    cmd = "nictagadm exists -l {}".format(" ".join(nictag))
    res = __salt__["cmd.run_all"](cmd)

    if not kwargs.get("verbose", False):
        ret = res["retcode"] == 0
    else:
        missing = res["stderr"].splitlines()
        for nt in nictag:
            ret[nt] = nt not in missing

    return ret


def add(name, mac, mtu=1500):
    """
    Add a new nictag

    name : string
        name of new nictag
    mac : string
        mac of parent interface or 'etherstub' to create a ether stub
    mtu : int
        MTU (ignored for etherstubs)

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.add storage0 etherstub
        salt '*' nictagadm.add trunk0 'DE:AD:OO:OO:BE:EF' 9000
    """
    ret = {}

    if mtu > 9000 or mtu < 1500:
        return {"Error": "mtu must be a value between 1500 and 9000."}
    if mac != "etherstub":
        cmd = "dladm show-phys -m -p -o address"
        res = __salt__["cmd.run_all"](cmd)
        # dladm prints '00' as '0', so account for that.
        if mac.replace("00", "0") not in res["stdout"].splitlines():
            return {"Error": "{} is not present on this system.".format(mac)}

    if mac == "etherstub":
        cmd = "nictagadm add -l {}".format(name)
        res = __salt__["cmd.run_all"](cmd)
    else:
        cmd = "nictagadm add -p mtu={},mac={} {}".format(mtu, mac, name)
        res = __salt__["cmd.run_all"](cmd)

    if res["retcode"] == 0:
        return True
    else:
        return {
            "Error": "failed to create nictag."
            if "stderr" not in res and res["stderr"] == ""
            else res["stderr"]
        }


def update(name, mac=None, mtu=None):
    """
    Update a nictag

    name : string
        name of nictag
    mac : string
        optional new mac for nictag
    mtu : int
        optional new MTU for nictag

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.update trunk mtu=9000
    """
    ret = {}

    if name not in list_nictags():
        return {"Error": "nictag {} does not exists.".format(name)}
    if not mtu and not mac:
        return {"Error": "please provide either mac or/and mtu."}
    if mtu:
        if mtu > 9000 or mtu < 1500:
            return {"Error": "mtu must be a value between 1500 and 9000."}
    if mac:
        if mac == "etherstub":
            return {"Error": 'cannot update a nic with "etherstub".'}
        else:
            cmd = "dladm show-phys -m -p -o address"
            res = __salt__["cmd.run_all"](cmd)
            # dladm prints '00' as '0', so account for that.
            if mac.replace("00", "0") not in res["stdout"].splitlines():
                return {"Error": "{} is not present on this system.".format(mac)}

    if mac and mtu:
        properties = "mtu={},mac={}".format(mtu, mac)
    elif mac:
        properties = "mac={}".format(mac) if mac else ""
    elif mtu:
        properties = "mtu={}".format(mtu) if mtu else ""

    cmd = "nictagadm update -p {} {}".format(properties, name)
    res = __salt__["cmd.run_all"](cmd)

    if res["retcode"] == 0:
        return True
    else:
        return {
            "Error": "failed to update nictag."
            if "stderr" not in res and res["stderr"] == ""
            else res["stderr"]
        }


def delete(name, force=False):
    """
    Delete nictag

    name : string
        nictag to delete
    force : boolean
        force delete even if vms attached

    CLI Example:

    .. code-block:: bash

        salt '*' nictagadm.exists admin
    """
    ret = {}

    if name not in list_nictags():
        return True

    cmd = "nictagadm delete {}{}".format("-f " if force else "", name)
    res = __salt__["cmd.run_all"](cmd)

    if res["retcode"] == 0:
        return True
    else:
        return {
            "Error": "failed to delete nictag."
            if "stderr" not in res and res["stderr"] == ""
            else res["stderr"]
        }


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
