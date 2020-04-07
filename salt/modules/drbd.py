# -*- coding: utf-8 -*-
"""
DRBD administration module
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

log = logging.getLogger(__name__)


def _analyse_overview_field(content):
    if "(" in content:
        # Output like "Connected(2*)" or "UpToDate(2*)"
        return content.split("(")[0], content.split("(")[0]
    elif "/" in content:
        # Output like "Primar/Second" or "UpToDa/UpToDa"
        return content.split("/")[0], content.split("/")[1]

    return content, ""


def overview():
    """
    Show status of the DRBD devices, support two nodes only.

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.overview
    """
    cmd = "drbd-overview"
    for line in __salt__["cmd.run"](cmd).splitlines():
        ret = {}
        fields = line.strip().split()
        minnum = fields[0].split(":")[0]
        device = fields[0].split(":")[1]
        connstate, _ = _analyse_overview_field(fields[1])
        localrole, partnerrole = _analyse_overview_field(fields[2])
        localdiskstate, partnerdiskstate = _analyse_overview_field(fields[3])
        if localdiskstate.startswith("UpTo"):
            if partnerdiskstate.startswith("UpTo"):
                if len(fields) >= 5:
                    mountpoint = fields[4]
                    fs_mounted = fields[5]
                    totalsize = fields[6]
                    usedsize = fields[7]
                    remainsize = fields[8]
                    perc = fields[9]
                    ret = {
                        "minor number": minnum,
                        "device": device,
                        "connection state": connstate,
                        "local role": localrole,
                        "partner role": partnerrole,
                        "local disk state": localdiskstate,
                        "partner disk state": partnerdiskstate,
                        "mountpoint": mountpoint,
                        "fs": fs_mounted,
                        "total size": totalsize,
                        "used": usedsize,
                        "remains": remainsize,
                        "percent": perc,
                    }
                else:
                    ret = {
                        "minor number": minnum,
                        "device": device,
                        "connection state": connstate,
                        "local role": localrole,
                        "partner role": partnerrole,
                        "local disk state": localdiskstate,
                        "partner disk state": partnerdiskstate,
                    }
            else:
                syncbar = fields[4]
                synced = fields[6]
                syncedbytes = fields[7]
                sync = synced + syncedbytes
                ret = {
                    "minor number": minnum,
                    "device": device,
                    "connection state": connstate,
                    "local role": localrole,
                    "partner role": partnerrole,
                    "local disk state": localdiskstate,
                    "partner disk state": partnerdiskstate,
                    "synchronisation: ": syncbar,
                    "synched": sync,
                }
    return ret
