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

"""
Module for managing BTRFS file systems.
"""
import itertools
import os
import re
import subprocess
import uuid

import salt.utils.fsutils
import salt.utils.platform
from salt.exceptions import CommandExecutionError


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    return not salt.utils.platform.is_windows() and __grains__.get("kernel") == "Linux"


def version():
    """
    Return BTRFS version.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.version
    """
    out = __salt__["cmd.run_all"]("btrfs --version")
    if out.get("stderr"):
        raise CommandExecutionError(out["stderr"])
    return {"version": out["stdout"].split(" ", 1)[-1]}


def _parse_btrfs_info(data):
    """
    Parse BTRFS device info data.
    """
    ret = {}
    for line in [line for line in data.split("\n") if line][:-1]:
        if line.startswith("Label:"):
            line = re.sub(r"Label:\s+", "", line)
            label, uuid_ = (tkn.strip() for tkn in line.split("uuid:"))
            ret["label"] = label != "none" and label or None
            ret["uuid"] = uuid_
            continue

        if line.startswith("\tdevid"):
            dev_data = re.split(r"\s+", line.strip())
            dev_id = dev_data[-1]
            ret[dev_id] = {
                "device_id": dev_data[1],
                "size": dev_data[3],
                "used": dev_data[5],
            }

    return ret


def info(device):
    """
    Get BTRFS filesystem information.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.info /dev/sda1
    """
    out = __salt__["cmd.run_all"](f"btrfs filesystem show {device}")
    salt.utils.fsutils._verify_run(out)

    return _parse_btrfs_info(out["stdout"])


def devices():
    """
    Get known BTRFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.devices
    """
    out = __salt__["cmd.run_all"]("blkid -o export")
    salt.utils.fsutils._verify_run(out)

    return salt.utils.fsutils._blkid_output(out["stdout"], fs_type="btrfs")


def _defragment_mountpoint(mountpoint):
    """
    Defragment only one BTRFS mountpoint.
    """
    out = __salt__["cmd.run_all"](f"btrfs filesystem defragment -f {mountpoint}")
    return {
        "mount_point": mountpoint,
        "passed": not out["stderr"],
        "log": out["stderr"] or False,
        "range": False,
    }


def defragment(path):
    """
    Defragment mounted BTRFS filesystem.
    In order to defragment a filesystem, device should be properly mounted and writable.

    If passed a device name, then defragmented whole filesystem, mounted on in.
    If passed a moun tpoint of the filesystem, then only this mount point is defragmented.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.defragment /dev/sda1
        salt '*' btrfs.defragment /path/on/filesystem
    """
    is_device = salt.utils.fsutils._is_device(path)
    mounts = salt.utils.fsutils._get_mounts("btrfs")
    if is_device and not mounts.get(path):
        raise CommandExecutionError(f'Device "{path}" is not mounted')

    result = []
    if is_device:
        for mount_point in mounts[path]:
            result.append(_defragment_mountpoint(mount_point["mount_point"]))
    else:
        is_mountpoint = False
        for mountpoints in mounts.values():
            for mpnt in mountpoints:
                if path == mpnt["mount_point"]:
                    is_mountpoint = True
                    break
        d_res = _defragment_mountpoint(path)
        if (
            not is_mountpoint
            and not d_res["passed"]
            and "range ioctl not supported" in d_res["log"]
        ):
            d_res["log"] = (
                "Range ioctl defragmentation is not supported in this kernel."
            )

        if not is_mountpoint:
            d_res["mount_point"] = False
            d_res["range"] = os.path.exists(path) and path or False

        result.append(d_res)

    return result


def features():
    """
    List currently available BTRFS features.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.mkfs_features
    """
    out = __salt__["cmd.run_all"]("mkfs.btrfs -O list-all")
    salt.utils.fsutils._verify_run(out)

    ret = {}
    for line in [
        re.sub(r"\s+", " ", line) for line in out["stderr"].split("\n") if " - " in line
    ]:
        option, description = line.split(" - ", 1)
        ret[option] = description

    return ret


def _usage_overall(raw):
    """
    Parse usage/overall.
    """
    data = {}
    for line in raw.split("\n")[1:]:
        keyset = [
            item.strip()
            for item in re.sub(r"\s+", " ", line).split(":", 1)
            if item.strip()
        ]
        if len(keyset) == 2:
            key = re.sub(r"[()]", "", keyset[0]).replace(" ", "_").lower()
            if key in ["free_estimated", "global_reserve"]:  # An extra field
                subk = keyset[1].split("(")
                data[key] = subk[0].strip()
                subk = subk[1].replace(")", "").split(": ")
                data[f"{key}_{subk[0]}"] = subk[1]
            else:
                data[key] = keyset[1]

    return data


def _usage_specific(raw):
    """
    Parse usage/specific.
    """

    def get_key(val):
        return dict([tuple(val.split(":"))])

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
    """
    Parse usage/unallocated.
    """
    ret = {}
    for line in raw.split("\n")[1:]:
        keyset = re.sub(r"\s+", " ", line.strip()).split(" ")
        if len(keyset) == 2:
            ret[keyset[0]] = keyset[1]

    return ret


def usage(path):
    """
    Show in which disk the chunks are allocated.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.usage /your/mountpoint
    """
    out = __salt__["cmd.run_all"](f"btrfs filesystem usage {path}")
    salt.utils.fsutils._verify_run(out)

    ret = {}
    for section in out["stdout"].split("\n\n"):
        if section.startswith("Overall:\n"):
            ret["overall"] = _usage_overall(section)
        elif section.startswith("Unallocated:\n"):
            ret["unallocated"] = _usage_unallocated(section)
        else:
            ret.update(_usage_specific(section))

    return ret


def mkfs(*devices, **kwargs):
    """
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
    """
    if not devices:
        raise CommandExecutionError("No devices specified")

    mounts = salt.utils.fsutils._get_mounts("btrfs")
    for device in devices:
        if mounts.get(device):
            raise CommandExecutionError(f'Device "{device}" should not be mounted')

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
            cmd.append(f"-d {dto}")
        if mto:
            cmd.append(f"-m {mto}")

    for key, option in [
        ("-l", "leafsize"),
        ("-L", "label"),
        ("-O", "fts"),
        ("-A", "allocsize"),
        ("-b", "bytecount"),
        ("-n", "nodesize"),
        ("-s", "sectorsize"),
    ]:
        if option == "label" and option in kwargs:
            kwargs["label"] = "'{}'".format(kwargs["label"])
        if kwargs.get(option):
            cmd.append(f"{key} {kwargs.get(option)}")

    if kwargs.get("uuid"):
        cmd.append(
            "-U {}".format(
                kwargs.get("uuid") is True and uuid.uuid1() or kwargs.get("uuid")
            )
        )

    if kwargs.get("nodiscard"):
        cmd.append("-K")
    if not kwargs.get("noforce"):
        cmd.append("-f")

    cmd.extend(devices)

    out = __salt__["cmd.run_all"](" ".join(cmd))
    salt.utils.fsutils._verify_run(out)

    ret = {"log": out["stdout"]}
    ret.update(__salt__["btrfs.info"](devices[0]))

    return ret


def resize(mountpoint, size):
    """
    Resize filesystem.

    General options:

    * **mountpoint**: Specify the BTRFS mountpoint to resize.
    * **size**: ([+/-]<newsize>[kKmMgGtTpPeE]|max) Specify the new size of the target.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.resize /mountpoint size=+1g
        salt '*' btrfs.resize /dev/sda1 size=max
    """

    if size == "max":
        if not salt.utils.fsutils._is_device(mountpoint):
            raise CommandExecutionError(
                f'Mountpoint "{mountpoint}" should be a valid device'
            )
        if not salt.utils.fsutils._get_mounts("btrfs").get(mountpoint):
            raise CommandExecutionError(f'Device "{mountpoint}" should be mounted')
    elif (
        len(size) < 3
        or size[0] not in "-+"
        or size[-1] not in "kKmMgGtTpPeE"
        or re.sub(r"\d", "", size[1:][:-1])
    ):
        raise CommandExecutionError(
            'Unknown size: "{}". Expected: [+/-]<newsize>[kKmMgGtTpPeE]|max'.format(
                size
            )
        )

    out = __salt__["cmd.run_all"](f"btrfs filesystem resize {size} {mountpoint}")
    salt.utils.fsutils._verify_run(out)

    ret = {"log": out["stdout"]}
    ret.update(__salt__["btrfs.info"](mountpoint))

    return ret


def _fsck_ext(device):
    """
    Check an ext2/ext3/ext4 file system.

    This is forced check to determine a filesystem is clean or not.
    NOTE: Maybe this function needs to be moved as a standard method in extfs module in a future.
    """
    msgs = {
        0: "No errors",
        1: "Filesystem errors corrected",
        2: "System should be rebooted",
        4: "Filesystem errors left uncorrected",
        8: "Operational error",
        16: "Usage or syntax error",
        32: "Fsck canceled by user request",
        128: "Shared-library error",
    }

    return msgs.get(
        __salt__["cmd.run_all"](f"fsck -f -n {device}")["retcode"],
        "Unknown error",
    )


def convert(device, permanent=False, keeplf=False):
    """
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
    """

    out = __salt__["cmd.run_all"]("blkid -o export")
    salt.utils.fsutils._verify_run(out)
    devices = salt.utils.fsutils._blkid_output(out["stdout"])
    if not devices.get(device):
        raise CommandExecutionError(f'The device "{device}" was is not found.')

    if not devices[device]["type"] in ["ext2", "ext3", "ext4"]:
        raise CommandExecutionError(
            'The device "{}" is a "{}" file system.'.format(
                device, devices[device]["type"]
            )
        )

    mountpoint = (
        salt.utils.fsutils._get_mounts(devices[device]["type"])
        .get(device, [{"mount_point": None}])[0]
        .get("mount_point")
    )
    if mountpoint == "/":
        raise CommandExecutionError(
            """One does not simply converts a root filesystem!

Converting an extended root filesystem to BTRFS is a careful
and lengthy process, among other steps including the following
requirements:

  1. Proper verified backup.
  2. System outage.
  3. Offline system access.

For further details, please refer to your OS vendor
documentation regarding this topic.
"""
        )

    salt.utils.fsutils._verify_run(__salt__["cmd.run_all"](f"umount {device}"))

    ret = {
        "before": {
            "fsck_status": _fsck_ext(device),
            "mount_point": mountpoint,
            "type": devices[device]["type"],
        }
    }

    salt.utils.fsutils._verify_run(__salt__["cmd.run_all"](f"btrfs-convert {device}"))
    salt.utils.fsutils._verify_run(
        __salt__["cmd.run_all"](f"mount {device} {mountpoint}")
    )

    # Refresh devices
    out = __salt__["cmd.run_all"]("blkid -o export")
    salt.utils.fsutils._verify_run(out)
    devices = salt.utils.fsutils._blkid_output(out["stdout"])

    ret["after"] = {
        "fsck_status": "N/A",  # ToDO
        "mount_point": mountpoint,
        "type": devices[device]["type"],
    }

    # Post-migration procedures
    image_path = f"{mountpoint}/ext2_saved"
    orig_fstype = ret["before"]["type"]

    if not os.path.exists(image_path):
        raise CommandExecutionError(
            f'BTRFS migration went wrong: the image "{image_path}" not found!'
        )

    if not permanent:
        ret["after"][f"{orig_fstype}_image"] = image_path
        image_info_proc = subprocess.run(
            ["file", f"{image_path}/image"], check=True, stdout=subprocess.PIPE
        )
        ret["after"][f"{orig_fstype}_image_info"] = image_info_proc.stdout.strip()
    else:
        ret["after"][f"{orig_fstype}_image"] = "removed"
        ret["after"][f"{orig_fstype}_image_info"] = "N/A"

        salt.utils.fsutils._verify_run(
            __salt__["cmd.run_all"](f"btrfs subvolume delete {image_path}")
        )
        out = __salt__["cmd.run_all"](f"btrfs filesystem balance {mountpoint}")
        salt.utils.fsutils._verify_run(out)
        ret["after"]["balance_log"] = out["stdout"]

    lost_found = f"{mountpoint}/lost+found"
    if os.path.exists(lost_found) and not keeplf:
        salt.utils.fsutils._verify_run(__salt__["cmd.run_all"](f"rm -rf {lost_found}"))

    return ret


def _restripe(mountpoint, direction, *devices, **kwargs):
    """
    Restripe BTRFS: add or remove devices from the particular mounted filesystem.
    """
    fs_log = []

    if salt.utils.fsutils._is_device(mountpoint):
        raise CommandExecutionError(
            f'Mountpount expected, while device "{mountpoint}" specified'
        )

    mounted = False
    for device, mntpoints in salt.utils.fsutils._get_mounts("btrfs").items():
        for mntdata in mntpoints:
            if mntdata["mount_point"] == mountpoint:
                mounted = True
                break

    if not mounted:
        raise CommandExecutionError(
            f'No BTRFS device mounted on "{mountpoint}" mountpoint'
        )

    if not devices:
        raise CommandExecutionError("No devices specified.")

    available_devices = __salt__["btrfs.devices"]()
    for device in devices:
        if device not in available_devices.keys():
            raise CommandExecutionError(f'Device "{device}" is not recognized')

    cmd = [f"btrfs device {direction}"]
    for device in devices:
        cmd.append(device)

    if direction == "add":
        if kwargs.get("nodiscard"):
            cmd.append("-K")
        if kwargs.get("force"):
            cmd.append("-f")

    cmd.append(mountpoint)

    out = __salt__["cmd.run_all"](" ".join(cmd))
    salt.utils.fsutils._verify_run(out)
    if out["stdout"]:
        fs_log.append(out["stdout"])

    if direction == "add":
        out = None
        data_conversion = kwargs.get("dc")
        meta_conversion = kwargs.get("mc")
        if data_conversion and meta_conversion:
            out = __salt__["cmd.run_all"](
                "btrfs balance start -dconvert={} -mconvert={} {}".format(
                    data_conversion, meta_conversion, mountpoint
                )
            )
        else:
            out = __salt__["cmd.run_all"](f"btrfs filesystem balance {mountpoint}")
        salt.utils.fsutils._verify_run(out)
        if out["stdout"]:
            fs_log.append(out["stdout"])

    # Summarize the result
    ret = {}
    if fs_log:
        ret.update({"log": "\n".join(fs_log)})
    ret.update(__salt__["btrfs.info"](mountpoint))

    return ret


def add(mountpoint, *devices, **kwargs):
    """
    Add a devices to a BTRFS filesystem.

    General options:

    * **nodiscard**: Do not perform whole device TRIM
    * **force**: Force overwrite existing filesystem on the disk

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.add /mountpoint /dev/sda1 /dev/sda2
    """
    return _restripe(mountpoint, "add", *devices, **kwargs)


def delete(mountpoint, *devices, **kwargs):
    """
    Remove devices from a BTRFS filesystem.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.delete /mountpoint /dev/sda1 /dev/sda2
    """
    return _restripe(mountpoint, "delete", *devices, **kwargs)


def _parse_proplist(data):
    """
    Parse properties list.
    """
    out = {}
    for line in data.split("\n"):
        line = re.split(r"\s+", line, 1)
        if len(line) == 2:
            out[line[0]] = line[1]

    return out


def properties(obj, type=None, set=None):
    """
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
    """
    if type and type not in [
        "s",
        "subvol",
        "f",
        "filesystem",
        "i",
        "inode",
        "d",
        "device",
    ]:
        raise CommandExecutionError(f'Unknown property type: "{type}" specified')

    cmd = ["btrfs"]
    cmd.append("property")
    cmd.append(set and "set" or "list")
    if type:
        cmd.append(f"-t{type}")
    cmd.append(obj)

    if set:
        try:
            for key, value in [
                [item.strip() for item in keyset.split("=")]
                for keyset in set.split(",")
            ]:
                cmd.append(key)
                cmd.append(value)
        except Exception as ex:  # pylint: disable=broad-except
            raise CommandExecutionError(ex)

    out = __salt__["cmd.run_all"](" ".join(cmd))
    salt.utils.fsutils._verify_run(out)

    if not set:
        ret = {}
        for prop, descr in _parse_proplist(out["stdout"]).items():
            ret[prop] = {"description": descr}
            value = __salt__["cmd.run_all"](f"btrfs property get {obj} {prop}")[
                "stdout"
            ]
            ret[prop]["value"] = value and value.split("=")[-1] or "N/A"

        return ret


def subvolume_exists(path):
    """
    Check if a subvolume is present in the filesystem.

    path
        Mount point for the subvolume (full path)

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_exists /mnt/var

    """
    cmd = ["btrfs", "subvolume", "show", path]
    return __salt__["cmd.retcode"](cmd, ignore_retcode=True) == 0


def subvolume_create(name, dest=None, qgroupids=None):
    """
    Create subvolume `name` in `dest`.

    Return True if the subvolume is created, False is the subvolume is
    already there.

    name
         Name of the new subvolume

    dest
         If not given, the subvolume will be created in the current
         directory, if given will be in /dest/name

    qgroupids
         Add the newly created subcolume to a qgroup. This parameter
         is a list

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_create var
        salt '*' btrfs.subvolume_create var dest=/mnt
        salt '*' btrfs.subvolume_create var qgroupids='[200]'

    """
    if qgroupids and type(qgroupids) is not list:
        raise CommandExecutionError("Qgroupids parameter must be a list")

    if dest:
        name = os.path.join(dest, name)

    # If the subvolume is there, we are done
    if subvolume_exists(name):
        return False

    cmd = ["btrfs", "subvolume", "create"]
    if type(qgroupids) is list:
        cmd.append("-i")
        cmd.extend(qgroupids)
    cmd.append(name)

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)
    return True


def subvolume_delete(name=None, names=None, commit=None):
    """
    Delete the subvolume(s) from the filesystem

    The user can remove one single subvolume (name) or multiple of
    then at the same time (names). One of the two parameters needs to
    specified.

    Please, refer to the documentation to understand the implication
    on the transactions, and when the subvolume is really deleted.

    Return True if the subvolume is deleted, False is the subvolume
    was already missing.

    name
        Name of the subvolume to remove

    names
        List of names of subvolumes to remove

    commit
        * 'after': Wait for transaction commit at the end
        * 'each': Wait for transaction commit after each delete

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_delete /var/volumes/tmp
        salt '*' btrfs.subvolume_delete /var/volumes/tmp commit=after

    """
    if not name and not (names and type(names) is list):
        raise CommandExecutionError("Provide a value for the name parameter")

    if commit and commit not in ("after", "each"):
        raise CommandExecutionError("Value for commit not recognized")

    # Filter the names and take the ones that are still there
    names = [
        n for n in itertools.chain([name], names or []) if n and subvolume_exists(n)
    ]

    # If the subvolumes are gone, we are done
    if not names:
        return False

    cmd = ["btrfs", "subvolume", "delete"]
    if commit == "after":
        cmd.append("--commit-after")
    elif commit == "each":
        cmd.append("--commit-each")
    cmd.extend(names)

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)
    return True


def subvolume_find_new(name, last_gen):
    """
    List the recently modified files in a subvolume

    name
        Name of the subvolume

    last_gen
        Last transid marker from where to compare

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_find_new /var/volumes/tmp 1024

    """
    cmd = ["btrfs", "subvolume", "find-new", name, last_gen]

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)

    lines = res["stdout"].splitlines()
    # Filenames are at the end of each inode line
    files = [l.split()[-1] for l in lines if l.startswith("inode")]
    # The last transid is in the last line
    transid = lines[-1].split()[-1]
    return {
        "files": files,
        "transid": transid,
    }


def subvolume_get_default(path):
    """
    Get the default subvolume of the filesystem path

    path
        Mount point for the subvolume

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_get_default /var/volumes/tmp

    """
    cmd = ["btrfs", "subvolume", "get-default", path]

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)

    line = res["stdout"].strip()
    # The ID is the second parameter, and the name the last one, or
    # '(FS_TREE)'
    #
    # When the default one is set:
    # ID 5 (FS_TREE)
    #
    # When we manually set a different one (var):
    # ID 257 gen 8 top level 5 path var
    #
    id_ = line.split()[1]
    name = line.split()[-1]
    return {
        "id": id_,
        "name": name,
    }


def _pop(line, key, use_rest):
    """
    Helper for the line parser.

    If key is a prefix of line, will remove ir from the line and will
    extract the value (space separation), and the rest of the line.

    If use_rest is True, the value will be the rest of the line.

    Return a tuple with the value and the rest of the line.
    """
    value = None
    if line.startswith(key):
        line = line[len(key) :].strip()
        if use_rest:
            value = line
            line = ""
        else:
            value, line = line.split(" ", 1)
    return value, line.strip()


def subvolume_list(
    path,
    parent_id=False,
    absolute=False,
    ogeneration=False,
    generation=False,
    subvolumes=False,
    uuid=False,
    parent_uuid=False,
    sent_subvolume_uuid=False,
    snapshots=False,
    readonly=False,
    deleted=False,
    generation_cmp=None,
    ogeneration_cmp=None,
    sort=None,
):
    """
    List the subvolumes present in the filesystem.

    path
        Mount point for the subvolume

    parent_id
        Print parent ID

    absolute
        Print all the subvolumes in the filesystem and distinguish
        between absolute and relative path with respect to the given
        <path>

    ogeneration
        Print the ogeneration of the subvolume

    generation
        Print the generation of the subvolume

    subvolumes
        Print only subvolumes below specified <path>

    uuid
        Print the UUID of the subvolume

    parent_uuid
        Print the parent uuid of subvolumes (and snapshots)

    sent_subvolume_uuid
        Print the UUID of the sent subvolume, where the subvolume is
        the result of a receive operation

    snapshots
        Only snapshot subvolumes in the filesystem will be listed

    readonly
        Only readonly subvolumes in the filesystem will be listed

    deleted
        Only deleted subvolumens that are ye not cleaned

    generation_cmp
        List subvolumes in the filesystem that its generation is >=,
        <= or = value. '+' means >= value, '-' means <= value, If
        there is neither '+' nor '-', it means = value

    ogeneration_cmp
        List subvolumes in the filesystem that its ogeneration is >=,
        <= or = value

    sort
        List subvolumes in order by specified items. Possible values:
        * rootid
        * gen
        * ogen
        * path
        You can add '+' or '-' in front of each items, '+' means
        ascending, '-' means descending. The default is ascending. You
        can combite it in a list.

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_list /var/volumes/tmp
        salt '*' btrfs.subvolume_list /var/volumes/tmp path=True
        salt '*' btrfs.subvolume_list /var/volumes/tmp sort='[-rootid]'

    """
    if sort and type(sort) is not list:
        raise CommandExecutionError("Sort parameter must be a list")

    valid_sorts = [
        "".join((order, attrib))
        for order, attrib in itertools.product(
            ("-", "", "+"), ("rootid", "gen", "ogen", "path")
        )
    ]
    if sort and not all(s in valid_sorts for s in sort):
        raise CommandExecutionError("Value for sort not recognized")

    cmd = ["btrfs", "subvolume", "list"]

    params = (
        (parent_id, "-p"),
        (absolute, "-a"),
        (ogeneration, "-c"),
        (generation, "-g"),
        (subvolumes, "-o"),
        (uuid, "-u"),
        (parent_uuid, "-q"),
        (sent_subvolume_uuid, "-R"),
        (snapshots, "-s"),
        (readonly, "-r"),
        (deleted, "-d"),
    )
    cmd.extend(p[1] for p in params if p[0])

    if generation_cmp:
        cmd.extend(["-G", generation_cmp])

    if ogeneration_cmp:
        cmd.extend(["-C", ogeneration_cmp])

    # We already validated the content of the list
    if sort:
        cmd.append("--sort={}".format(",".join(sort)))

    cmd.append(path)

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)

    # Parse the output. ID and gen are always at the beginning, and
    # path is always at the end. There is only one column that
    # contains space (top level), and the path value can also have
    # spaces. The issue is that we do not know how many spaces do we
    # have in the path name, so any classic solution based on split
    # will fail.
    #
    # This list is in order.
    columns = (
        "ID",
        "gen",
        "cgen",
        "parent",
        "top level",
        "otime",
        "parent_uuid",
        "received_uuid",
        "uuid",
        "path",
    )
    result = []
    for line in res["stdout"].splitlines():
        table = {}
        for key in columns:
            value, line = _pop(line, key, key == "path")
            if value:
                table[key.lower()] = value
        # If line is not empty here, we are not able to parse it
        if not line:
            result.append(table)

    return result


def subvolume_set_default(subvolid, path):
    """
    Set the subvolume as default

    subvolid
        ID of the new default subvolume

    path
        Mount point for the filesystem

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_set_default 257 /var/volumes/tmp

    """
    cmd = ["btrfs", "subvolume", "set-default", subvolid, path]

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)
    return True


def subvolume_show(path):
    """
    Show information of a given subvolume

    path
        Mount point for the filesystem

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_show /var/volumes/tmp

    """
    cmd = ["btrfs", "subvolume", "show", path]

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)

    result = {}
    table = {}
    # The real name is the first line, later there is a table of
    # values separated with colon.
    stdout = res["stdout"].splitlines()
    key = stdout.pop(0)
    result[key.strip()] = table

    for line in stdout:
        key, value = line.split(":", 1)
        table[key.lower().strip()] = value.strip()
    return result


def subvolume_snapshot(source, dest=None, name=None, read_only=False):
    """
    Create a snapshot of a source subvolume

    source
        Source subvolume from where to create the snapshot

    dest
        If only dest is given, the subvolume will be named as the
        basename of the source

    name
       Name of the snapshot

    read_only
        Create a read only snapshot

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_snapshot /var/volumes/tmp dest=/.snapshots
        salt '*' btrfs.subvolume_snapshot /var/volumes/tmp name=backup

    """
    if not dest and not name:
        raise CommandExecutionError("Provide parameter dest, name, or both")

    cmd = ["btrfs", "subvolume", "snapshot"]
    if read_only:
        cmd.append("-r")

    cmd.append(source)

    if dest and not name:
        cmd.append(dest)
    if dest and name:
        name = os.path.join(dest, name)
    if name:
        cmd.append(name)

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)
    return True


def subvolume_sync(path, subvolids=None, sleep=None):
    """
    Wait until given subvolume are completely removed from the
    filesystem after deletion.

    path
        Mount point for the filesystem

    subvolids
        List of IDs of subvolumes to wait for

    sleep
        Sleep N seconds betwenn checks (default: 1)

    CLI Example:

    .. code-block:: bash

        salt '*' btrfs.subvolume_sync /var/volumes/tmp
        salt '*' btrfs.subvolume_sync /var/volumes/tmp subvolids='[257]'

    """
    if subvolids and type(subvolids) is not list:
        raise CommandExecutionError("Subvolids parameter must be a list")

    cmd = ["btrfs", "subvolume", "sync"]
    if sleep:
        cmd.extend(["-s", sleep])

    cmd.append(path)
    if subvolids:
        cmd.extend(subvolids)

    res = __salt__["cmd.run_all"](cmd)
    salt.utils.fsutils._verify_run(res)
    return True
