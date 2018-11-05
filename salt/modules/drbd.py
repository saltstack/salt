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


def _count_spaces_startswith(line):
    if line.split("#")[0].strip() == "":
        return None

    spaces = 0
    for i in line:
        if i.isspace():
            spaces += 1
        else:
            return spaces


def _analyse_status_type(line):
    spaces = _count_spaces_startswith(line)

    if spaces is None:
        return None
    elif spaces == 0:
        return "RESOURCE"
    elif spaces == 2:
        if " disk:" in line:
            return "LOCALDISK"
        elif " role:" in line or " connection:" in line:
            return "PEERNODE"
        else:
            return "UNKNOWN"
    elif spaces == 4:
        if " peer-disk:" in line:
            return "PEERDISK"
        else:
            return "UNKNOWN"
    else:
        return "UNKNOWN"


def overview():
    """
    Show status of the DRBD devices, support two nodes only.
    drbd-overview is removed since drbd-utils-9.6.0,
    use status instead.

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


def status(name=""):
    """
    Using drbdadm to show status of the DRBD devices,
        available in the latest drbd9.
    Support multiple nodes and/or multiple volumes.

    :type name: str
    :param name:
        Resource name.

    :return: drbd status of resource.
    :rtype: list(dict(res))

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.status
        salt '*' drbd.status name=<resource name>
    """

    cmd = ["drbdadm", "status"]
    if len(name) != 0:
        cmd.append(name)

    ret = []
    resource = {}

    # One possible output: (number of resource/node/vol are flexible)
    # resource role:Secondary
    #  volume:0 disk:Inconsistent
    #  volume:1 disk:Inconsistent
    #  drbd-node1 role:Primary
    #    volume:0 replication:SyncTarget peer-disk:UpToDate done:10.17
    #    volume:1 replication:SyncTarget peer-disk:UpToDate done:74.08
    #  drbd-node2 role:Secondary
    #    volume:0 peer-disk:Inconsistent resync-suspended:peer
    #    volume:1 peer-disk:Inconsistent resync-suspended:peer
    for line in __salt__["cmd.run"](cmd).splitlines():
        section = _analyse_status_type(line)
        fields = line.strip().split()

        if section is None:
            continue

        elif section == "RESOURCE":
            if resource:
                ret.append(resource)
                resource = {}

            resource["resource name"] = fields[0]
            resource["local role"] = fields[1].split(":")[1]
            resource["local volumes"] = []
            resource["peer nodes"] = []

        elif section == "LOCALDISK":
            volume = {}
            for field in fields:
                volume[field.split(":")[0]] = field.split(":")[1]
            resource["local volumes"].append(volume)

        elif section == "PEERNODE":
            peernode = {}
            peernode["peernode name"] = fields[0]
            # Could be "role:" or "connection:", depends on connect state
            peernode[fields[1].split(":")[0]] = fields[1].split(":")[1]
            peernode["peer volumes"] = []
            lastpnodevolumes = peernode["peer volumes"]
            resource["peer nodes"].append(peernode)

        elif section == "PEERDISK":
            volume = {}
            for field in fields:
                volume[field.split(":")[0]] = field.split(":")[1]
            lastpnodevolumes.append(volume)

        else:
            ret = {"UNKNOWN parser": line}
            return ret

    if resource:
        ret.append(resource)

    return ret
