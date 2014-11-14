# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# Copyright (C) 2014 SUSE LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

'''
Run-time utilities
'''

import os
import re
import time
import logging

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _verify_run(out, cmd=None):
    '''
    Crash to the log if command execution was not successful.
    '''
    if out.get("retcode", 0) and out['stderr']:
        if cmd:
            log.debug('Command: "{0}"'.format(cmd))

        log.debug('Return code: {0}'.format(out.get('retcode')))
        log.debug('Error output:\n{0}'.format(out.get('stderr', "N/A")))

        raise CommandExecutionError(out['stderr'])


def _get_mounts(fs_type):
    '''
    List mounted filesystems.
    '''
    mounts = {}
    for line in open("/proc/mounts").readlines():
        device, mntpnt, fstype, options, fs_freq, fs_passno = line.strip().split(" ")
        if fstype != fs_type:
            continue
        if mounts.get(device) is None:
            mounts[device] = []

        mounts[device].append({
            'mount_point': mntpnt,
            'options': options.split(",")
        })

    return mounts


def _blkid_output(out, fs_type=None):
    '''
    Parse blkid output.
    '''
    flt = lambda data: [el for el in data if el.strip()]
    data = {}
    for dev_meta in flt(out.split("\n\n")):
        dev = {}
        for items in flt(dev_meta.strip().split("\n")):
            key, val = items.split("=", 1)
            dev[key.lower()] = val
        if fs_type and dev.get("type", '') == fs_type or not fs_type:
            if dev.has_key("type"):
                dev.pop("type")
            dev['label'] = dev.get('label')
            data[dev.pop("devname")] = dev

    if fs_type:
        mounts = _get_mounts(fs_type)
        for device in mounts.keys():
            if data.get(device):
                data[device]['mounts'] = mounts[device]

    return data


def _is_device(path):
    '''
    Return True if path is a physical device.
    '''
    out = __salt__['cmd.run_all']("file -i {0}".format(path))
    _verify_run(out)

    # Always [device, mime, charset]. See (file --help)
    return re.split(r"\s+", out['stdout'])[1][:-1] == "inode/blockdevice"
