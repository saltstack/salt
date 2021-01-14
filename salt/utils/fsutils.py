# -*- coding: utf-8 -*-
"""
Run-time utilities
"""
#
# Copyright (C) 2014 SUSE LLC


# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

# Import Salt libs
import salt.utils.files
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def _verify_run(out, cmd=None):
    """
    Crash to the log if command execution was not successful.
    """
    if out.get("retcode", 0) and out["stderr"]:
        if cmd:
            log.debug("Command: '%s'", cmd)

        log.debug("Return code: %s", out.get("retcode"))
        log.debug("Error output:\n%s", out.get("stderr", "N/A"))

        raise CommandExecutionError(out["stderr"])


def _get_mounts(fs_type=None):
    """
    List mounted filesystems.
    """
    mounts = {}
    with salt.utils.files.fopen("/proc/mounts") as fhr:
        for line in fhr.readlines():
            line = salt.utils.stringutils.to_unicode(line)
            device, mntpnt, fstype, options, fs_freq, fs_passno = line.strip().split(
                " "
            )
            if fs_type and fstype != fs_type:
                continue
            if mounts.get(device) is None:
                mounts[device] = []

            data = {"mount_point": mntpnt, "options": options.split(",")}
            if not fs_type:
                data["type"] = fstype
            mounts[device].append(data)
    return mounts


# TODO: Due to "blkid -o export" strongly differs from system to system, this must go away in favor of _blkid() below!
def _blkid_output(out, fs_type=None):
    """
    Parse blkid output.
    """
    flt = lambda data: [el for el in data if el.strip()]
    data = {}
    for dev_meta in flt(out.split("\n\n")):
        dev = {}
        for items in flt(dev_meta.strip().split("\n")):
            key, val = items.split("=", 1)
            dev[key.lower()] = val
        if fs_type and dev.get("type", "") == fs_type or not fs_type:
            if "type" in dev and fs_type:
                dev.pop("type")
            data[dev.pop("devname")] = dev

    if fs_type:
        mounts = _get_mounts(fs_type)
        for device in six.iterkeys(mounts):
            if data.get(device):
                data[device]["mounts"] = mounts[device]

    return data


def _blkid(fs_type=None):
    """
    Return available media devices.

    :param fs_type: Filter only devices that are formatted by that file system.
    """
    flt = lambda data: [el for el in data if el.strip()]
    data = dict()
    for dev_meta in flt(
        os.popen("blkid -o full").read().split(os.linesep)
    ):  # No __salt__ around at this point.
        dev_meta = dev_meta.strip()
        if not dev_meta:
            continue
        device = dev_meta.split(" ")
        dev_name = device.pop(0)[:-1]
        data[dev_name] = dict()
        for k_set in device:
            ks_key, ks_value = [elm.replace('"', "") for elm in k_set.split("=")]
            data[dev_name][ks_key.lower()] = ks_value

    if fs_type:
        mounts = _get_mounts(fs_type)
        for device in six.iterkeys(mounts):
            if data.get(device):
                data[device]["mounts"] = mounts[device]

    return data


def _is_device(path):
    """
    Return True if path is a physical device.
    """
    out = __salt__["cmd.run_all"]("file -i {0}".format(path))
    _verify_run(out)

    # Always [device, mime, charset]. See (file --help)
    return re.split(r"\s+", out["stdout"])[1][:-1] == "inode/blockdevice"
