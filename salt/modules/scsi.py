"""
SCSI administration module
"""

import logging
import os.path

import salt.utils.path

log = logging.getLogger(__name__)

__func_alias__ = {"ls_": "ls"}


def ls_(get_size=True):
    """
    List SCSI devices, with details

    CLI Examples:

    .. code-block:: bash

        salt '*' scsi.ls
        salt '*' scsi.ls get_size=False

    get_size : True
        Get the size information for scsi devices.  This option
        should be set to False for older OS distributions (RHEL6 and older)
        due to lack of support for the '-s' option in lsscsi.

        .. versionadded:: 2015.5.10
    """

    if not salt.utils.path.which("lsscsi"):
        __context__["retcode"] = 1
        return "scsi.ls not available - lsscsi command not found"

    if get_size:
        cmd = "lsscsi -dLsv"
    else:
        cmd = "lsscsi -dLv"

    ret = {}
    res = __salt__["cmd.run_all"](cmd)
    rc = res.get("retcode", -1)
    if rc != 0:
        __context__["retcode"] = rc
        error = res.get("stderr", "").split("\n")[0]
        if error == "lsscsi: invalid option -- 's'":
            return "{} - try get_size=False".format(error)
        return res.get("stderr", "").split("\n")[0]
    data = res.get("stdout", "")

    for line in data.splitlines():
        if line.startswith("["):
            size = None
            major = None
            minor = None
            comps = line.strip().split()
            key = comps[0]
            if get_size:
                size = comps.pop()
            majmin = comps.pop()
            if majmin.startswith("["):
                major, minor = majmin.replace("[", "").replace("]", "").split(":")
            device = comps.pop()
            model = " ".join(comps[3:])
            ret[key] = {
                "lun": key.replace("[", "").replace("]", ""),
                "size": size,
                "major": major,
                "minor": minor,
                "device": device,
                "model": model,
            }
        elif line.startswith(" "):
            if line.strip().startswith("dir"):
                comps = line.strip().split()
                ret[key]["dir"] = [comps[1], comps[2].replace("[", "").replace("]", "")]
            else:
                comps = line.strip().split("=")
                ret[key][comps[0]] = comps[1]
    return ret


def rescan_all(host):
    """
    List scsi devices

    CLI Example:

    .. code-block:: bash

        salt '*' scsi.rescan_all 0
    """
    if os.path.isdir("/sys/class/scsi_host/host{}".format(host)):
        cmd = 'echo "- - -" > /sys/class/scsi_host/host{}/scan'.format(host)
    else:
        return "Host {} does not exist".format(host)
    return __salt__["cmd.run"](cmd).splitlines()
