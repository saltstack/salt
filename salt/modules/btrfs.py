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
Module for managing BTRFS file systems.
'''

import os
import re
import time
import logging

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.is_windows() and __grains__.get('kernel') == 'Linux'


def version():
    '''
    Return BTRFS version.
    '''
    out = __salt__['cmd.run_all']("btrfs --version")
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'])
    return {'version': out['stdout'].split(" ", 1)[-1]}


def _parse_btrfs_info(data):
    '''
    Parse BTRFS device info data.
    '''
    info = {}
    for line in [line for line in data.split("\n") if line][:-1]:
        if line.startswith("Label:"):
            line = re.sub(r"Label:\s+", "", line)
            label, uuid = [tkn.strip() for tkn in line.split("uuid:")]
            info['label'] = label != 'none' and label or None
            info['uuid'] = uuid
            continue

        if line.startswith("\tdevid"):
            dev_data = re.split(r"\s+", line.strip())
            dev_id = dev_data[-1]
            info[dev_id] = {
                'device_id': dev_data[1],
                'size': dev_data[3],
                'used': dev_data[5],
                }

    return info


def info(device):
    '''
    Get BTRFS filesystem information.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.info /dev/sda1
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem show {0}".format(device))
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'].replace("xfs_info:", "").strip())
    return _parse_btrfs_info(out['stdout'])


def devices():
    '''
    Get known BTRFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.devices
    '''
    out = __salt__['cmd.run_all']("blkid -o export")
    fsutils._verify_run(out)

    return fsutils._blkid_output(out['stdout'], fs_type='btrfs')

