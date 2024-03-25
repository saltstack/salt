"""
Module for Solaris 10's zoneadm

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      OmniOS,OpenIndiana,SmartOS,OpenSolaris,Solaris 10

.. versionadded:: 2017.7.0

.. warning::
    Oracle Solaris 11's zoneadm is not supported by this module!
"""

import logging

import salt.utils.decorators
import salt.utils.path

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "zoneadm"

# Function aliases
__func_alias__ = {"list_zones": "list"}


@salt.utils.decorators.memoize
def _is_globalzone():
    """
    Check if we are running in the globalzone
    """
    if not __grains__["kernel"] == "SunOS":
        return False

    zonename = __salt__["cmd.run_all"]("zonename")
    if zonename["retcode"]:
        return False
    if zonename["stdout"] == "global":
        return True

    return False


def _is_uuid(zone):
    """
    Check if zone is actually a UUID
    """
    return len(zone) == 36 and zone.index("-") == 8


def __virtual__():
    """
    We are available if we are have zoneadm and are the global zone on
    Solaris 10, OmniOS, OpenIndiana, OpenSolaris, or Smartos.
    """
    if _is_globalzone() and salt.utils.path.which("zoneadm"):
        if __grains__["os"] in ["OpenSolaris", "SmartOS", "OmniOS", "OpenIndiana"]:
            return __virtualname__
        elif (
            __grains__["os"] == "Oracle Solaris"
            and int(__grains__["osmajorrelease"]) == 10
        ):
            return __virtualname__
    return (
        False,
        f"{__virtualname__} module can only be loaded in a solaris globalzone.",
    )


def list_zones(verbose=True, installed=False, configured=False, hide_global=True):
    """
    List all zones

    verbose : boolean
        display additional zone information
    installed : boolean
        include installed zones in output
    configured : boolean
        include configured zones in output
    hide_global : boolean
        do not include global zone

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.list
    """
    zones = {}

    ## fetch zones
    header = "zoneid:zonename:state:zonepath:uuid:brand:ip-type".split(":")
    zone_data = __salt__["cmd.run_all"]("zoneadm list -p -c")
    if zone_data["retcode"] == 0:
        for zone in zone_data["stdout"].splitlines():
            zone = zone.split(":")

            # create zone_t
            zone_t = {}
            for num, val in enumerate(header):
                zone_t[val] = zone[num]

            # skip if global and hide_global
            if hide_global and zone_t["zonename"] == "global":
                continue

            # skip installed and configured
            if not installed and zone_t["state"] == "installed":
                continue
            if not configured and zone_t["state"] == "configured":
                continue

            # update dict
            zones[zone_t["zonename"]] = zone_t
            del zones[zone_t["zonename"]]["zonename"]

    return zones if verbose else sorted(zones.keys())


def boot(zone, single=False, altinit=None, smf_options=None):
    """
    Boot (or activate) the specified zone.

    zone : string
        name or uuid of the zone
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.boot clementine
        salt '*' zoneadm.boot maeve single=True
        salt '*' zoneadm.boot teddy single=True smf_options=verbose
    """
    ret = {"status": True}

    ## build boot_options
    boot_options = ""
    if single:
        boot_options = f"-s {boot_options}"
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = f"-i {altinit} {boot_options}"
    if smf_options:
        boot_options = f"-m {smf_options} {boot_options}"
    if boot_options != "":
        boot_options = f" -- {boot_options.strip()}"

    ## execute boot
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} boot{boot_opts}".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
            boot_opts=boot_options,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def reboot(zone, single=False, altinit=None, smf_options=None):
    """
    Restart the zone. This is equivalent to a halt boot sequence.

    zone : string
        name or uuid of the zone
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.reboot dolores
        salt '*' zoneadm.reboot teddy single=True
    """
    ret = {"status": True}

    ## build boot_options
    boot_options = ""
    if single:
        boot_options = f"-s {boot_options}"
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = f"-i {altinit} {boot_options}"
    if smf_options:
        boot_options = f"-m {smf_options} {boot_options}"
    if boot_options != "":
        boot_options = f" -- {boot_options.strip()}"

    ## execute reboot
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} reboot{boot_opts}".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
            boot_opts=boot_options,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def halt(zone):
    """
    Halt the specified zone.

    zone : string
        name or uuid of the zone

    .. note::
        To cleanly shutdown the zone use the shutdown function.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.halt hector
    """
    ret = {"status": True}

    ## halt zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} halt".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def shutdown(zone, reboot=False, single=False, altinit=None, smf_options=None):
    """
    Gracefully shutdown the specified zone.

    zone : string
        name or uuid of the zone
    reboot : boolean
        reboot zone after shutdown (equivalent of shutdown -i6 -g0 -y)
    single : boolean
        boots only to milestone svc:/milestone/single-user:default.
    altinit : string
        valid path to an alternative executable to be the primordial process.
    smf_options : string
        include two categories of options to control booting behavior of
        the service management facility: recovery options and messages options.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.shutdown peter
        salt '*' zoneadm.shutdown armistice reboot=True
    """
    ret = {"status": True}

    ## build boot_options
    boot_options = ""
    if single:
        boot_options = f"-s {boot_options}"
    if altinit:  # note: we cannot validate the path, as this is local to the zonepath.
        boot_options = f"-i {altinit} {boot_options}"
    if smf_options:
        boot_options = f"-m {smf_options} {boot_options}"
    if boot_options != "":
        boot_options = f" -- {boot_options.strip()}"

    ## shutdown zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} shutdown{reboot}{boot_opts}".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
            reboot=" -r" if reboot else "",
            boot_opts=boot_options,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def detach(zone):
    """
    Detach the specified zone.

    zone : string
        name or uuid of the zone

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.detach kissy
    """
    ret = {"status": True}

    ## detach zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} detach".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def attach(zone, force=False, brand_opts=None):
    """
    Attach the specified zone.

    zone : string
        name of the zone
    force : boolean
        force the zone into the "installed" state with no validation
    brand_opts : string
        brand specific options to pass

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.attach lawrence
        salt '*' zoneadm.attach lawrence True
    """
    ret = {"status": True}

    ## attach zone
    res = __salt__["cmd.run_all"](
        "zoneadm -z {zone} attach{force}{brand_opts}".format(
            zone=zone,
            force=" -F" if force else "",
            brand_opts=f" {brand_opts}" if brand_opts else "",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def ready(zone):
    """
    Prepares a zone for running applications.

    zone : string
        name or uuid of the zone

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.ready clementine
    """
    ret = {"status": True}

    ## ready zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} ready".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def verify(zone):
    """
    Check to make sure the configuration of the specified
    zone can safely be installed on the machine.

    zone : string
        name of the zone

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.verify dolores
    """
    ret = {"status": True}

    ## verify zone
    res = __salt__["cmd.run_all"](
        "zoneadm -z {zone} verify".format(
            zone=zone,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def move(zone, zonepath):
    """
    Move zone to new zonepath.

    zone : string
        name or uuid of the zone
    zonepath : string
        new zonepath

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.move meave /sweetwater/meave
    """
    ret = {"status": True}

    ## verify zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} move {path}".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
            path=zonepath,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def uninstall(zone):
    """
    Uninstall the specified zone from the system.

    zone : string
        name or uuid of the zone

    .. warning::
        The -F flag is always used to avoid the prompts when uninstalling.

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.uninstall teddy
    """
    ret = {"status": True}

    ## uninstall zone
    res = __salt__["cmd.run_all"](
        "zoneadm {zone} uninstall -F".format(
            zone=f"-u {zone}" if _is_uuid(zone) else f"-z {zone}",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def install(zone, nodataset=False, brand_opts=None):
    """
    Install the specified zone from the system.

    zone : string
        name of the zone
    nodataset : boolean
        do not create a ZFS file system
    brand_opts : string
        brand specific options to pass

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.install dolores
        salt '*' zoneadm.install teddy True
    """
    ret = {"status": True}

    ## install zone
    res = __salt__["cmd.run_all"](
        "zoneadm -z {zone} install{nodataset}{brand_opts}".format(
            zone=zone,
            nodataset=" -x nodataset" if nodataset else "",
            brand_opts=f" {brand_opts}" if brand_opts else "",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret


def clone(zone, source, snapshot=None):
    """
    Install a zone by copying an existing installed zone.

    zone : string
        name of the zone
    source : string
        zone to clone from
    snapshot : string
        optional name of snapshot to use as source

    CLI Example:

    .. code-block:: bash

        salt '*' zoneadm.clone clementine dolores
    """
    ret = {"status": True}

    ## install zone
    res = __salt__["cmd.run_all"](
        "zoneadm -z {zone} clone {snapshot}{source}".format(
            zone=zone,
            source=source,
            snapshot=f"-s {snapshot} " if snapshot else "",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    ret["message"] = ret["message"].replace("zoneadm: ", "")
    if ret["message"] == "":
        del ret["message"]

    return ret
