"""
Detect LVM Volumes
"""

import logging

import salt.modules.cmdmod
import salt.utils.files
import salt.utils.path
import salt.utils.platform

__salt__ = {
    "cmd.run": salt.modules.cmdmod._run_quiet,
    "cmd.run_all": salt.modules.cmdmod._run_all_quiet,
}

log = logging.getLogger(__name__)


def lvm():
    """
    Return list of LVM devices
    """
    if salt.utils.platform.is_linux():
        return _linux_lvm()
    elif salt.utils.platform.is_aix():
        return _aix_lvm()
    else:
        log.trace("LVM grain does not support this OS")


def _linux_lvm():
    ret = {}
    cmd = salt.utils.path.which("lvm")
    if cmd:
        vgs = __salt__["cmd.run"]("{} vgs -o vg_name --noheadings".format(cmd))

        for vg in vgs.splitlines():
            vg = vg.strip()
            ret[vg] = []
            lvs = __salt__["cmd.run"](
                "{} lvs -o lv_name --noheadings {}".format(cmd, vg)
            )
            for lv in lvs.splitlines():
                ret[vg].append(lv.strip())

        return {"lvm": ret}
    else:
        log.trace("No LVM installed")


def _aix_lvm():
    ret = {}
    cmd = salt.utils.path.which("lsvg")
    vgs = __salt__["cmd.run"]("{}".format(cmd))

    for vg in vgs.splitlines():
        ret[vg] = []
        lvs = __salt__["cmd.run"]("{} -l {}".format(cmd, vg))
        for lvline in lvs.splitlines()[2:]:
            lv = lvline.split(" ", 1)[0]
            ret[vg].append(lv)

    return {"lvm": ret}
