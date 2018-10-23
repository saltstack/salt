# -*- coding: utf-8 -*-
#
# Copyright 2014 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
Module for managing BTRFS file systems.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import uuid


# Import Salt libs
import salt.utils.fsutils
import salt.utils.platform
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.platform.is_windows() and __grains__.get('kernel') == 'Linux'


def version():
    '''
    Return BTRFS version.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.version
    '''
    out = __salt__['cmd.run_all']("btrfs --version")
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'])
    return {'version': out['stdout'].split(" ", 1)[-1]}


def _parse_btrfs_info(data):
    '''
    Parse BTRFS device info data.
    '''
    ret = {}
    for line in [line for line in data.split("\n") if line][:-1]:
        if line.startswith("Label:"):
            line = re.sub(r"Label:\s+", "", line)
            label, uuid_ = [tkn.strip() for tkn in line.split("uuid:")]
            ret['label'] = label != 'none' and label or None
            ret['uuid'] = uuid_
            continue

        if line.startswith("\tdevid"):
            dev_data = re.split(r"\s+", line.strip())
            dev_id = dev_data[-1]
            ret[dev_id] = {
                'device_id': dev_data[1],
                'size': dev_data[3],
                'used': dev_data[5],
                }

    return ret


def info(device):
    '''
    Get BTRFS filesystem information.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.info /dev/sda1
    '''
    out = __salt__['cmd.run_all']("btrfs filesystem show {0}".format(device))
    salt.utils.fsutils._verify_run(out)

    return _parse_btrfs_info(out['stdout'])


def devices():
    '''
    Get known BTRFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.devices
    '''
    out = __salt__['cmd.run_all']("blkid -o export")
    salt.utils.fsutils._verify_run(out)

    return salt.utils.fsutils._blkid_output(out['stdout'], fs_type='btrfs')


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
    is_device = salt.utils.fsutils._is_device(path)
    mounts = salt.utils.fsutils._get_mounts("btrfs")
    if is_device and not mounts.get(path):
        raise CommandExecutionError("Device \"{0}\" is not mounted".format(path))

    result = []
    if is_device:
        for mount_point in mounts[path]:
            result.append(_defragment_mountpoint(mount_point['mount_point']))
    else:
        is_mountpoint = False
        for mountpoints in six.itervalues(mounts):
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
    salt.utils.fsutils._verify_run(out)

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
    get_key = lambda val: dict([tuple(val.split(":")), ])
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
    salt.utils.fsutils._verify_run(out)

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

    * **dto**: (raid0|raid1|raid5|raid6|raid10|single|dup)
               Specify how the data must be spanned across the devices specified.
    * **mto**: (raid0|raid1|raid5|raid6|raid10|single|dup)
               Specify how metadata must be spanned across the devices specified.
    * **fts**: Features (call ``salt <host> btrfs.features`` for full list of available features)

    See the ``mkfs.btrfs(8)`` manpage for a more complete description of corresponding options description.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.mkfs /dev/sda1
        salt '*' btrfs.mkfs /dev/sda1 noforce=True
    '''
    if not devices:
        raise CommandExecutionError("No devices specified")

    mounts = salt.utils.fsutils._get_mounts("btrfs")
    for device in devices:
        if mounts.get(device):
            raise CommandExecutionError("Device \"{0}\" should not be mounted".format(device))

    cmd = ["mkfs.btrfs"]

    dto = kwargs.get("dto")
    mto = kwargs.get("mto")
    if len(devices) == 1:
        if dto:
            cmd.append("-d single")
        if mto:
            cmd.append("-m single")
    else:
        if dto:
            cmd.append("-d {0}".format(dto))
        if mto:
            cmd.append("-m {0}".format(mto))

    for key, option in [("-l", "leafsize"), ("-L", "label"), ("-O", "fts"),
                        ("-A", "allocsize"), ("-b", "bytecount"), ("-n", "nodesize"),
                        ("-s", "sectorsize")]:
        if option == 'label' and option in kwargs:
            kwargs['label'] = "'{0}'".format(kwargs["label"])
        if kwargs.get(option):
            cmd.append("{0} {1}".format(key, kwargs.get(option)))

    if kwargs.get("uuid"):
        cmd.append("-U {0}".format(kwargs.get("uuid") is True and uuid.uuid1() or kwargs.get("uuid")))

    if kwargs.get("nodiscard"):
        cmd.append("-K")
    if not kwargs.get("noforce"):
        cmd.append("-f")

    cmd.extend(devices)

    out = __salt__['cmd.run_all'](' '.join(cmd))
    salt.utils.fsutils._verify_run(out)

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
        if not salt.utils.fsutils._is_device(mountpoint):
            raise CommandExecutionError("Mountpoint \"{0}\" should be a valid device".format(mountpoint))
        if not salt.utils.fsutils._get_mounts("btrfs").get(mountpoint):
            raise CommandExecutionError("Device \"{0}\" should be mounted".format(mountpoint))
    elif len(size) < 3 or size[0] not in '-+' \
         or size[-1] not in 'kKmMgGtTpPeE' or re.sub(r"\d", "", size[1:][:-1]):
        raise CommandExecutionError("Unknown size: \"{0}\". Expected: [+/-]<newsize>[kKmMgGtTpPeE]|max".format(size))

    out = __salt__['cmd.run_all']('btrfs filesystem resize {0} {1}'.format(size, mountpoint))
    salt.utils.fsutils._verify_run(out)

    ret = {'log': out['stdout']}
    ret.update(__salt__['btrfs.info'](mountpoint))

    return ret


def _fsck_ext(device):
    '''
    Check an ext2/ext3/ext4 file system.

    This is forced check to determine a filesystem is clean or not.
    NOTE: Maybe this function needs to be moved as a standard method in extfs module in a future.
    '''
    msgs = {
        0: 'No errors',
        1: 'Filesystem errors corrected',
        2: 'System should be rebooted',
        4: 'Filesystem errors left uncorrected',
        8: 'Operational error',
        16: 'Usage or syntax error',
        32: 'Fsck canceled by user request',
        128: 'Shared-library error',
    }

    return msgs.get(__salt__['cmd.run_all']("fsck -f -n {0}".format(device))['retcode'], 'Unknown error')


def convert(device, permanent=False, keeplf=False):
    '''
    Convert ext2/3/4 to BTRFS. Device should be mounted.

    Filesystem can be converted temporarily so the further processing and rollback is possible,
    or permanently, where previous extended filesystem image gets deleted. Please note, permanent
    conversion takes a while as BTRFS filesystem needs to be properly rebalanced afterwards.

    General options:

    * **permanent**: Specify if the migration should be permanent (false by default)
    * **keeplf**: Keep ``lost+found`` of the partition (removed by default,
                  but still in the image, if not permanent migration)

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.convert /dev/sda1
        salt '*' btrfs.convert /dev/sda1 permanent=True
    '''

    out = __salt__['cmd.run_all']("blkid -o export")
    salt.utils.fsutils._verify_run(out)
    devices = salt.utils.fsutils._blkid_output(out['stdout'])
    if not devices.get(device):
        raise CommandExecutionError("The device \"{0}\" was is not found.".format(device))

    if not devices[device]["type"] in ['ext2', 'ext3', 'ext4']:
        raise CommandExecutionError("The device \"{0}\" is a \"{1}\" file system.".format(
            device, devices[device]["type"]))

    mountpoint = salt.utils.fsutils._get_mounts(devices[device]["type"]).get(
        device, [{'mount_point': None}])[0].get('mount_point')
    if mountpoint == '/':
        raise CommandExecutionError("""One does not simply converts a root filesystem!

Converting an extended root filesystem to BTRFS is a careful
and lengthy process, among other steps including the following
requirements:

  1. Proper verified backup.
  2. System outage.
  3. Offline system access.

For further details, please refer to your OS vendor
documentation regarding this topic.
""")

    salt.utils.fsutils._verify_run(__salt__['cmd.run_all']("umount {0}".format(device)))

    ret = {
        'before': {
            'fsck_status': _fsck_ext(device),
            'mount_point': mountpoint,
            'type': devices[device]["type"],
        }
    }

    salt.utils.fsutils._verify_run(__salt__['cmd.run_all']("btrfs-convert {0}".format(device)))
    salt.utils.fsutils._verify_run(__salt__['cmd.run_all']("mount {0} {1}".format(device, mountpoint)))

    # Refresh devices
    out = __salt__['cmd.run_all']("blkid -o export")
    salt.utils.fsutils._verify_run(out)
    devices = salt.utils.fsutils._blkid_output(out['stdout'])

    ret['after'] = {
        'fsck_status': "N/A",  # ToDO
        'mount_point': mountpoint,
        'type': devices[device]["type"],
    }

    # Post-migration procedures
    image_path = "{0}/ext2_saved".format(mountpoint)
    orig_fstype = ret['before']['type']

    if not os.path.exists(image_path):
        raise CommandExecutionError(
            "BTRFS migration went wrong: the image \"{0}\" not found!".format(image_path))

    if not permanent:
        ret['after']['{0}_image'.format(orig_fstype)] = image_path
        ret['after']['{0}_image_info'.format(orig_fstype)] = os.popen(
            "file {0}/image".format(image_path)).read().strip()
    else:
        ret['after']['{0}_image'.format(orig_fstype)] = 'removed'
        ret['after']['{0}_image_info'.format(orig_fstype)] = 'N/A'

        salt.utils.fsutils._verify_run(__salt__['cmd.run_all']("btrfs subvolume delete {0}".format(image_path)))
        out = __salt__['cmd.run_all']("btrfs filesystem balance {0}".format(mountpoint))
        salt.utils.fsutils._verify_run(out)
        ret['after']['balance_log'] = out['stdout']

    lost_found = "{0}/lost+found".format(mountpoint)
    if os.path.exists(lost_found) and not keeplf:
        salt.utils.fsutils._verify_run(__salt__['cmd.run_all']("rm -rf {0}".format(lost_found)))

    return ret


def _restripe(mountpoint, direction, *devices, **kwargs):
    '''
    Restripe BTRFS: add or remove devices from the particular mounted filesystem.
    '''
    fs_log = []

    if salt.utils.fsutils._is_device(mountpoint):
        raise CommandExecutionError(
            "Mountpount expected, while device \"{0}\" specified".format(mountpoint))

    mounted = False
    for device, mntpoints in six.iteritems(salt.utils.fsutils._get_mounts("btrfs")):
        for mntdata in mntpoints:
            if mntdata['mount_point'] == mountpoint:
                mounted = True
                break

    if not mounted:
        raise CommandExecutionError(
            "No BTRFS device mounted on \"{0}\" mountpoint".format(mountpoint))

    if not devices:
        raise CommandExecutionError("No devices specified.")

    available_devices = __salt__['btrfs.devices']()
    for device in devices:
        if device not in six.iterkeys(available_devices):
            raise CommandExecutionError("Device \"{0}\" is not recognized".format(device))

    cmd = ['btrfs device {0}'.format(direction)]
    for device in devices:
        cmd.append(device)

    if direction == 'add':
        if kwargs.get("nodiscard"):
            cmd.append("-K")
        if kwargs.get("force"):
            cmd.append("-f")

    cmd.append(mountpoint)

    out = __salt__['cmd.run_all'](' '.join(cmd))
    salt.utils.fsutils._verify_run(out)
    if out['stdout']:
        fs_log.append(out['stdout'])

    if direction == 'add':
        out = None
        data_conversion = kwargs.get("dc")
        meta_conversion = kwargs.get("mc")
        if data_conversion and meta_conversion:
            out = __salt__['cmd.run_all'](
                "btrfs balance start -dconvert={0} -mconvert={1} {2}".format(
                    data_conversion, meta_conversion, mountpoint))
        else:
            out = __salt__['cmd.run_all']("btrfs filesystem balance {0}".format(mountpoint))
        salt.utils.fsutils._verify_run(out)
        if out['stdout']:
            fs_log.append(out['stdout'])

    # Summarize the result
    ret = {}
    if fs_log:
        ret.update({'log': '\n'.join(fs_log)})
    ret.update(__salt__['btrfs.info'](mountpoint))

    return ret


def add(mountpoint, *devices, **kwargs):
    '''
    Add a devices to a BTRFS filesystem.

    General options:

    * **nodiscard**: Do not perform whole device TRIM
    * **force**: Force overwrite existing filesystem on the disk

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.add /mountpoint /dev/sda1 /dev/sda2
    '''
    return _restripe(mountpoint, 'add', *devices, **kwargs)


def delete(mountpoint, *devices, **kwargs):
    '''
    Remove devices from a BTRFS filesystem.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.delete /mountpoint /dev/sda1 /dev/sda2
    '''
    return _restripe(mountpoint, 'delete', *devices, **kwargs)


def _parse_proplist(data):
    '''
    Parse properties list.
    '''
    out = {}
    for line in data.split("\n"):
        line = re.split(r"\s+", line, 1)
        if len(line) == 2:
            out[line[0]] = line[1]

    return out


def properties(obj, type=None, set=None):
    '''
    List properties for given btrfs object. The object can be path of BTRFS device,
    mount point, or any directories/files inside the BTRFS filesystem.

    General options:

    * **type**: Possible types are s[ubvol], f[ilesystem], i[node] and d[evice].
    * **force**: Force overwrite existing filesystem on the disk
    * **set**: <key=value,key1=value1...> Options for a filesystem properties.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.properties /mountpoint
        salt '*' btrfs.properties /dev/sda1 type=subvol set='ro=false,label="My Storage"'
    '''
    if type and type not in ['s', 'subvol', 'f', 'filesystem', 'i', 'inode', 'd', 'device']:
        raise CommandExecutionError("Unknown property type: \"{0}\" specified".format(type))

    cmd = ['btrfs']
    cmd.append('property')
    cmd.append(set and 'set' or 'list')
    if type:
        cmd.append('-t{0}'.format(type))
    cmd.append(obj)

    if set:
        try:
            for key, value in [[item.strip() for item in keyset.split("=")]
                               for keyset in set.split(",")]:
                cmd.append(key)
                cmd.append(value)
        except Exception as ex:
            raise CommandExecutionError(ex)

    out = __salt__['cmd.run_all'](' '.join(cmd))
    salt.utils.fsutils._verify_run(out)

    if not set:
        ret = {}
        for prop, descr in six.iteritems(_parse_proplist(out['stdout'])):
            ret[prop] = {'description': descr}
            value = __salt__['cmd.run_all'](
                "btrfs property get {0} {1}".format(obj, prop))['stdout']
            ret[prop]['value'] = value and value.split("=")[-1] or "N/A"

        return ret
