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
import uuid

import salt.utils
from salt.exceptions import CommandExecutionError

import fsutils

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
    fsutils._verify_run(out)

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


def _defragment_mountpoint(mountpoint):
    '''
    Defragment only one BTRFS mountpoint.
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem defragment -f {0}".format(mountpoint))
    return {
        'mount_point': mountpoint,
        'passed': not out['stderr'],
        'log': out['stderr'] or False,
        'range': False,
    }


def defragment(path):
    '''
    Defragment mounted BTRFS filesystem.
    In order to defragment a filesystem, device should be properly mounted and writable.

    If passed a device name, then defragmented whole filesystem, mounted on in.
    If passed a moun tpoint of the filesystem, then only this mount point is defragmented.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.defragment /dev/sda1
        salt '*' btrfs.defragment /path/on/filesystem
    '''
    is_device = fsutils._is_device(path)
    mounts = fsutils._get_mounts("btrfs")
    if is_device and not mounts.get(path):
        raise CommandExecutionError("Device \"{0}\" is not mounted".format(path))

    result = []
    if is_device:
        for mount_point in mounts[path]:
            result.append(_defragment_mountpoint(mount_point['mount_point']))
    else:
        is_mountpoint = False
        for device, mountpoints in mounts.items():
            for mpnt in mountpoints:
                if path == mpnt['mount_point']:
                    is_mountpoint = True
                    break
        d_res = _defragment_mountpoint(path)
        if not is_mountpoint and not d_res['passed'] and "range ioctl not supported" in d_res['log']:
            d_res['log'] = "Range ioctl defragmentation is not supported in this kernel."

        if not is_mountpoint:
            d_res['mount_point'] = False
            d_res['range'] = os.path.exists(path) and path or False

        result.append(d_res)

    return result


def features():
    '''
    List currently available BTRFS features.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.mkfs_features    
    '''
    out = __salt__['cmd.run_all']("mkfs.btrfs -O list-all")
    fsutils._verify_run(out)

    ret = {}
    for line in [re.sub(r"\s+", " ", line) for line in out['stderr'].split("\n") if " - " in line]:
        option, description = line.split(" - ", 1)
        ret[option] = description

    return ret


def _usage_overall(raw):
    '''
    Parse usage/overall.
    '''
    data = {}
    for line in raw.split("\n")[1:]:
        keyset = [item.strip() for item in re.sub(r"\s+", " ", line).split(":", 1) if item.strip()]
        if len(keyset) == 2:
            key = re.sub(r"[()]", "", keyset[0]).replace(" ", "_").lower()
            if key in ['free_estimated', 'global_reserve']:  # An extra field
                subk = keyset[1].split("(")
                data[key] = subk[0].strip()
                subk = subk[1].replace(")", "").split(": ")
                data["{0}_{1}".format(key, subk[0])] = subk[1]
            else:
                data[key] = keyset[1]

    return data


def _usage_specific(raw):
    '''
    Parse usage/specific.
    '''
    get_key = lambda val: dict([tuple(val.split(":")),])
    raw = raw.split("\n")
    section, size, used = raw[0].split(" ")
    section = section.replace(",", "_").replace(":", "").lower()

    data = {}
    data[section] = {}

    for val in [size, used]:
        data[section].update(get_key(val.replace(",", "")))

    for devices in raw[1:]:
        data[section].update(get_key(re.sub(r"\s+", ":", devices.strip())))
        
    return data


def _usage_unallocated(raw):
    '''
    Parse usage/unallocated.
    '''
    ret = {}
    for line in raw.split("\n")[1:]:
        keyset = re.sub(r"\s+", " ", line.strip()).split(" ")
        if len(keyset) == 2:
            ret[keyset[0]] = keyset[1]

    return ret


def usage(path):
    '''
    Show in which disk the chunks are allocated.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.usage /your/mountpoint
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem usage {0}".format(path))
    fsutils._verify_run(out)

    ret = {}
    for section in out['stdout'].split("\n\n"):
        if section.startswith("Overall:\n"):
            ret['overall'] = _usage_overall(section)
        elif section.startswith("Unallocated:\n"):
            ret['unallocated'] = _usage_unallocated(section)
        else:
            ret.update(_usage_specific(section))

    return ret


def mkfs(*devices, **kwargs):
    '''
    Create a file system on the specified device. By default wipes out with force.

    General options:
    
    * **allocsize**: Specify the BTRFS offset from the start of the device.
    * **bytecount**: Specify the size of the resultant filesystem.
    * **nodesize**: Node size.
    * **leafsize**: Specify the nodesize, the tree block size in which btrfs stores data.
    * **noforce**: Prevent force overwrite when an existing filesystem is detected on the device.
    * **sectorsize**: Specify the sectorsize, the minimum data block allocation unit.
    * **nodiscard**: Do not perform whole device TRIM operation by default.
    * **uuid**: Pass UUID or pass True to generate one.
    

    Options:

    * **dto**: (raid0|raid1|raid5|raid6|raid10|single|dup) Specify how the data must be spanned across the devices specified.
    * **mto**: (raid0|raid1|raid5|raid6|raid10|single|dup) Specify how metadata must be spanned across the devices specified.
    * **fts**: Features (call ``salt <host> btrfs.features`` for full list of available features)

    See the ``mkfs.btrfs(8)`` manpage for a more complete description of corresponding options description.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.mkfs /dev/sda1
        salt '*' btrfs.mkfs /dev/sda1 noforce=True
    '''
    # XXX: check for device availability!


    if not devices:
        raise CommandExecutionError("No devices specified")

    mounts = fsutils._get_mounts("btrfs")
    for device in devices:
        if mounts.get(device):
            raise CommandExecutionError("Device \"{0}\" should not be mounted".format(device))

    cmd = ["mkfs.btrfs"]

    dto = kwargs.get("dto")
    mto = kwargs.get("mto")
    if len(devices) == 1:
        dto and cmd.append("-d single")
        mto and cmd.append("-m single")
    else:
        dto and cmd.append("-d {0}".format(dto))
        mto and cmd.append("-m {0}".format(mto))

    for key, option in [("-l", "leafsize"), ("-L", "label"), ("-O", "fts"),
                        ("-A", "allocsize"), ("-b", "bytecount"), ("-n", "nodesize"),
                        ("-s", "sectorsize")]:
        if option == 'label' and kwargs.has_key(option):
            kwargs['label'] = "'{0}'".format(kwargs["label"])
        kwargs.get(option) and cmd.append("{0} {1}".format(key, kwargs.get(option)))

    if kwargs.get("uuid"):
        cmd.append("-U {0}".format(kwargs.get("uuid") is True and uuid.uuid1() or kwargs.get("uuid")))

    kwargs.get("nodiscard") and cmd.append("-K")
    if not kwargs.get("noforce"):
        cmd.append("-f")

    cmd.extend(devices)

    out = __salt__['cmd.run_all'](' '.join(cmd))
    fsutils._verify_run(out)

    ret = {'log': out['stdout']}
    ret.update(__salt__['btrfs.info'](devices[0]))

    return ret


def resize(mountpoint, size):
    '''
    Resize filesystem.

    General options:
    
    * **mountpoint**: Specify the BTRFS mountpoint to resize.
    * **size**: ([+/-]<newsize>[kKmMgGtTpPeE]|max) Specify the new size of the target.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.resize /mountpoint size=+1g
        salt '*' btrfs.resize /dev/sda1 size=max
    '''

    if size == 'max':
        if not fsutils._is_device(mountpoint):
            raise CommandExecutionError("Mountpoint \"{0}\" should be a valid device".format(mountpoint))
        if not fsutils._get_mounts("btrfs").get(mountpoint):
            raise CommandExecutionError("Device \"{0}\" should be mounted".format(mountpoint))
    elif len(size) < 3 or size[0] not in '-+' \
         or size[-1] not in 'kKmMgGtTpPeE' or re.sub(r"\d", "", size[1:][:-1]):
        raise CommandExecutionError("Unknown size: \"{0}\". Expected: [+/-]<newsize>[kKmMgGtTpPeE]|max".format(size))

    out = __salt__['cmd.run_all']('btrfs filesystem resize {0} {1}'.format(size, mountpoint))
    fsutils._verify_run(out)

    ret = {'log': out['stdout']}
    ret.update(__salt__['btrfs.info'](mountpoint))

    return ret
