"""
    Detect disks
"""

import glob
import logging
import re

# Solve the Chicken and egg problem where grains need to run before any
# of the modules are loaded and are generally available for any usage.
import salt.modules.cmdmod
import salt.utils.files
import salt.utils.path
import salt.utils.platform

__salt__ = {
    "cmd.run": salt.modules.cmdmod._run_quiet,
    "cmd.run_all": salt.modules.cmdmod._run_all_quiet,
    "cmd.powershell": salt.modules.cmdmod.powershell,
}

log = logging.getLogger(__name__)


def disks():
    """
    Return list of disk devices
    """
    if salt.utils.platform.is_freebsd():
        return _freebsd_geom()
    elif salt.utils.platform.is_linux():
        return _linux_disks()
    elif salt.utils.platform.is_windows():
        return _windows_disks()
    else:
        log.trace("Disk grain does not support OS")


class _geomconsts:
    GEOMNAME = "Geom name"
    MEDIASIZE = "Mediasize"
    SECTORSIZE = "Sectorsize"
    STRIPESIZE = "Stripesize"
    STRIPEOFFSET = "Stripeoffset"
    DESCR = "descr"  # model
    LUNID = "lunid"
    LUNNAME = "lunname"
    IDENT = "ident"  # serial
    ROTATIONRATE = "rotationrate"  # RPM or 0 for non-rotating

    # Preserve the API where possible with Salt < 2016.3
    _aliases = {
        DESCR: "device_model",
        IDENT: "serial_number",
        ROTATIONRATE: "media_RPM",
        LUNID: "WWN",
    }

    _datatypes = {
        MEDIASIZE: ("re_int", r"(\d+)"),
        SECTORSIZE: "try_int",
        STRIPESIZE: "try_int",
        STRIPEOFFSET: "try_int",
        ROTATIONRATE: "try_int",
    }


def _datavalue(datatype, data):
    if datatype == "try_int":
        try:
            return int(data)
        except ValueError:
            return None
    elif datatype is tuple and datatype[0] == "re_int":
        search = re.search(datatype[1], data)
        if search:
            try:
                return int(search.group(1))
            except ValueError:
                return None
        return None
    else:
        return data


_geom_attribs = [
    _geomconsts.__dict__[key] for key in _geomconsts.__dict__ if not key.startswith("_")
]


def _freebsd_geom():
    geom = salt.utils.path.which("geom")
    ret = {"disks": {}, "ssds": []}

    devices = __salt__["cmd.run"](f"{geom} disk list")
    devices = devices.split("\n\n")

    def parse_geom_attribs(device):
        tmp = {}
        for line in device.split("\n"):
            for attrib in _geom_attribs:
                search = re.search(rf"{attrib}:\s(.*)", line)
                if search:
                    value = _datavalue(
                        _geomconsts._datatypes.get(attrib), search.group(1)
                    )
                    tmp[attrib] = value
                    if attrib in _geomconsts._aliases:
                        tmp[_geomconsts._aliases[attrib]] = value

        name = tmp.pop(_geomconsts.GEOMNAME)
        if name.startswith("cd"):
            return

        ret["disks"][name] = tmp
        if tmp.get(_geomconsts.ROTATIONRATE) == 0:
            log.trace("Device %s reports itself as an SSD", device)
            ret["ssds"].append(name)

    for device in devices:
        parse_geom_attribs(device)

    return ret


def _linux_disks():
    """
    Return list of disk devices and work out if they are SSD or HDD.
    """
    ret = {"disks": [], "ssds": []}

    for entry in glob.glob("/sys/block/*"):
        virtual = salt.utils.path.readlink(entry).startswith("../devices/virtual/")
        try:
            if not virtual:
                with salt.utils.files.fopen(entry + "/queue/rotational") as entry_fp:
                    device = entry.split("/")[3]
                    flag = entry_fp.read(1)
                    if flag == "0":
                        ret["ssds"].append(device)
                        log.trace("Device %s reports itself as an SSD", device)
                    elif flag == "1":
                        ret["disks"].append(device)
                        log.trace("Device %s reports itself as an HDD", device)
                    else:
                        log.trace(
                            "Unable to identify device %s as an SSD or HDD. It does "
                            "not report 0 or 1",
                            device,
                        )
        except OSError:
            pass
    return ret


def _windows_disks():

    cmd = "Get-PhysicalDisk | Select DeviceID, MediaType"
    ret = {"disks": [], "ssds": []}

    drive_info = __salt__["cmd.powershell"](cmd)

    if not drive_info:
        log.trace("No physical discs found")
        return ret

    # We need a list of dict
    if isinstance(drive_info, dict):
        drive_info = [drive_info]

    for drive in drive_info:
        # Make sure we have a valid drive type
        if drive["MediaType"].lower() not in ["hdd", "ssd", "scm", "unspecified"]:
            log.trace(f'Unknown media type: {drive["MediaType"]}')
            continue
        device = rf'\\.\PhysicalDrive{drive["DeviceID"]}'
        ret["disks"].append(device)
        if drive["MediaType"].lower() == "ssd":
            ret["ssds"].append(device)

    return ret
