"""
Module for managing partitions on POSIX-like systems.

:depends:   - parted, partprobe, lsblk (usually parted and util-linux packages)

Some functions may not be available, depending on your version of parted.

Check the manpage for ``parted(8)`` for more information, or the online docs
at:

http://www.gnu.org/software/parted/manual/html_chapter/parted_2.html

In light of parted not directly supporting partition IDs, some of this module
has been written to utilize sfdisk instead. For further information, please
reference the man page for ``sfdisk(8)``.
"""

import logging
import os
import re
import stat
import string

import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "partition"

# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    "set_": "set",
    "list_": "list",
}

VALID_UNITS = {
    "s",
    "B",
    "kB",
    "MB",
    "MiB",
    "GB",
    "GiB",
    "TB",
    "TiB",
    "%",
    "cyl",
    "chs",
    "compact",
}

VALID_DISK_FLAGS = {"cylinder_alignment", "pmbr_boot", "implicit_partition_table"}

VALID_PARTITION_FLAGS = {
    "boot",
    "root",
    "swap",
    "hidden",
    "raid",
    "lvm",
    "lba",
    "hp-service",
    "palo",
    "prep",
    "msftres",
    "bios_grub",
    "atvrecv",
    "diag",
    "legacy_boot",
    "msftdata",
    "irst",
    "esp",
    "type",
}


def __virtual__():
    """
    Only work on POSIX-like systems, which have parted and lsblk installed.
    These are usually provided by the ``parted`` and ``util-linux`` packages.
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The parted execution module failed to load "
            "Windows systems are not supported.",
        )
    if not salt.utils.path.which("parted"):
        return (
            False,
            "The parted execution module failed to load "
            "parted binary is not in the path.",
        )
    if not salt.utils.path.which("lsblk"):
        return (
            False,
            "The parted execution module failed to load "
            "lsblk binary is not in the path.",
        )
    if not salt.utils.path.which("partprobe"):
        return (
            False,
            "The parted execution module failed to load "
            "partprobe binary is not in the path.",
        )
    return __virtualname__


# TODO: all the other inputs to the functions in this module are repetitively
# validated within each function; collect them into validation functions here,
# similar to _validate_device and _validate_partition_boundary
def _validate_device(device):
    """
    Ensure the device name supplied is valid in a manner similar to the
    `exists` function, but raise errors on invalid input rather than return
    False.

    This function only validates a block device, it does not check if the block
    device is a drive or a partition or a filesystem, etc.
    """
    if os.path.exists(device):
        dev = os.stat(device).st_mode

        if stat.S_ISBLK(dev):
            return

    raise CommandExecutionError("Invalid device passed to partition module.")


def _validate_partition_boundary(boundary):
    """
    Ensure valid partition boundaries are supplied.
    """
    boundary = str(boundary)
    match = re.search(r"^([\d.]+)(\D*)$", boundary)
    if match:
        unit = match.group(2)
        if not unit or unit in VALID_UNITS:
            return
    raise CommandExecutionError(f'Invalid partition boundary passed: "{boundary}"')


def probe(*devices):
    """
    Ask the kernel to update its local partition data. When no args are
    specified all block devices are tried.

    Caution: Generally only works on devices with no mounted partitions and
    may take a long time to return if specified devices are in use.

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.probe
        salt '*' partition.probe /dev/sda
        salt '*' partition.probe /dev/sda /dev/sdb
    """
    for device in devices:
        _validate_device(device)

    cmd = "partprobe -- {}".format(" ".join(devices))
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def list_(device, unit=None):
    """
    Prints partition information of given <device>

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.list /dev/sda
        salt '*' partition.list /dev/sda unit=s
        salt '*' partition.list /dev/sda unit=kB
    """
    _validate_device(device)

    if unit:
        if unit not in VALID_UNITS:
            raise CommandExecutionError("Invalid unit passed to partition.part_list")
        cmd = f"parted -m -s {device} unit {unit} print"
    else:
        cmd = f"parted -m -s {device} print"

    out = __salt__["cmd.run_stdout"](cmd).splitlines()
    ret = {"info": {}, "partitions": {}}
    mode = "info"
    for line in out:
        if line in ("BYT;", "CHS;", "CYL;"):
            continue
        cols = line.rstrip(";").split(":")
        if mode == "info":
            if 7 <= len(cols) <= 8:
                ret["info"] = {
                    "disk": cols[0],
                    "size": cols[1],
                    "interface": cols[2],
                    "logical sector": cols[3],
                    "physical sector": cols[4],
                    "partition table": cols[5],
                    "model": cols[6],
                }
                if len(cols) == 8:
                    ret["info"]["disk flags"] = cols[7]
                    # Older parted (2.x) doesn't show disk flags in the 'print'
                    # output, and will return a 7-column output for the info
                    # line. In these cases we just leave this field out of the
                    # return dict.
                mode = "partitions"
            else:
                raise CommandExecutionError(
                    "Problem encountered while parsing output from parted"
                )
        else:
            # Parted (v3.1) have a variable field list in machine
            # readable output:
            #
            # number:start:end:[size:]([file system:name:flags;]|[free;])
            #
            # * If units are in CHS 'size' is not printed.
            # * If is a logical partition with PED_PARTITION_FREESPACE
            #   set, the last three fields are replaced with the
            #   'free' text.
            #
            fields = ["number", "start", "end"]
            if unit != "chs":
                fields.append("size")
            if cols[-1] == "free":
                # Drop the last element from the list
                cols.pop()
            else:
                fields.extend(["file system", "name", "flags"])
            if len(fields) == len(cols):
                ret["partitions"][cols[0]] = dict(zip(fields, cols))
            else:
                raise CommandExecutionError(
                    "Problem encountered while parsing output from parted"
                )
    return ret


def align_check(device, part_type, partition):
    """
    Check if partition satisfies the alignment constraint of part_type.
    Type must be "minimal" or "optimal".

    CLI Example:

    .. code-block:: bash

        salt '*' partition.align_check /dev/sda minimal 1
    """
    _validate_device(device)

    if part_type not in {"minimal", "optimal"}:
        raise CommandExecutionError("Invalid part_type passed to partition.align_check")

    try:
        int(partition)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid partition passed to partition.align_check")

    cmd = f"parted -m {device} align-check {part_type} {partition}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def check(device, minor):
    """
    Checks if the file system on partition <minor> has any errors.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.check 1
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.check")

    cmd = f"parted -m -s {device} check {minor}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def cp(device, from_minor, to_minor):  # pylint: disable=C0103
    """
    Copies the file system on the partition <from-minor> to partition
    <to-minor>, deleting the original contents of the destination
    partition.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.cp /dev/sda 2 3
    """
    _validate_device(device)

    try:
        int(from_minor)
        int(to_minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.cp")

    cmd = f"parted -m -s {device} cp {from_minor} {to_minor}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def get_id(device, minor):
    """
    Prints the system ID for the partition. Some typical values are::

         b: FAT32 (vfat)
         7: HPFS/NTFS
        82: Linux Swap
        83: Linux
        8e: Linux LVM
        fd: Linux RAID Auto

    CLI Example:

    .. code-block:: bash

        salt '*' partition.get_id /dev/sda 1
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.get_id")

    cmd = f"sfdisk --print-id {device} {minor}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def set_id(device, minor, system_id):
    """
    Sets the system ID for the partition. Some typical values are::

         b: FAT32 (vfat)
         7: HPFS/NTFS
        82: Linux Swap
        83: Linux
        8e: Linux LVM
        fd: Linux RAID Auto

    CLI Example:

    .. code-block:: bash

        salt '*' partition.set_id /dev/sda 1 83
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.set_id")

    if system_id not in system_types():
        raise CommandExecutionError("Invalid system_id passed to partition.set_id")

    cmd = f"sfdisk --change-id {device} {minor} {system_id}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def system_types():
    """
    List the system types that are supported by the installed version of sfdisk

    CLI Example:

    .. code-block:: bash

        salt '*' partition.system_types
    """
    ret = {}
    for line in __salt__["cmd.run"]("sfdisk -T").splitlines():
        if not line:
            continue
        if line.startswith("Id"):
            continue
        comps = line.strip().split()
        ret[comps[0]] = comps[1]
    return ret


def _is_fstype(fs_type):
    """
    Check if file system type is supported in module
    :param fs_type: file system type
    :return: True if fs_type is supported in this module, False otherwise
    """
    return fs_type in (
        "btrfs",
        "ext2",
        "ext3",
        "ext4",
        "fat",
        "fat32",
        "fat16",
        "linux-swap",
        "reiserfs",
        "hfs",
        "hfs+",
        "hfsx",
        "NTFS",
        "ntfs",
        "ufs",
        "xfs",
    )


def mkfs(device, fs_type):
    """
    Makes a file system <fs_type> on partition <device>, destroying all data
    that resides on that partition. <fs_type> must be one of "ext2", "fat32",
    "fat16", "linux-swap" or "reiserfs" (if libreiserfs is installed)

    CLI Example:

    .. code-block:: bash

        salt '*' partition.mkfs /dev/sda2 fat32
    """
    _validate_device(device)

    if not _is_fstype(fs_type):
        raise CommandExecutionError("Invalid fs_type passed to partition.mkfs")

    if fs_type == "NTFS":
        fs_type = "ntfs"

    if fs_type == "linux-swap":
        mkfs_cmd = "mkswap"
    else:
        mkfs_cmd = f"mkfs.{fs_type}"

    if not salt.utils.path.which(mkfs_cmd):
        return f"Error: {mkfs_cmd} is unavailable."
    cmd = f"{mkfs_cmd} {device}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def mklabel(device, label_type):
    """
    Create a new disklabel (partition table) of label_type.

    Type should be one of "aix", "amiga", "bsd", "dvh", "gpt", "loop", "mac",
    "msdos", "pc98", or "sun".

    CLI Example:

    .. code-block:: bash

        salt '*' partition.mklabel /dev/sda msdos
    """
    if label_type not in {
        "aix",
        "amiga",
        "bsd",
        "dvh",
        "gpt",
        "loop",
        "mac",
        "msdos",
        "pc98",
        "sun",
    }:
        raise CommandExecutionError("Invalid label_type passed to partition.mklabel")

    cmd = ("parted", "-m", "-s", device, "mklabel", label_type)
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    return out


def mkpart(device, part_type, fs_type=None, start=None, end=None):
    """
    Make a part_type partition for filesystem fs_type, beginning at start and
    ending at end (by default in megabytes).  part_type should be one of
    "primary", "logical", or "extended".

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.mkpart /dev/sda primary fs_type=fat32 start=0 end=639
        salt '*' partition.mkpart /dev/sda primary start=0 end=639
    """
    _validate_device(device)

    if part_type not in {"primary", "logical", "extended"}:
        raise CommandExecutionError("Invalid part_type passed to partition.mkpart")

    if fs_type and not _is_fstype(fs_type):
        raise CommandExecutionError("Invalid fs_type passed to partition.mkpart")

    if start is not None and end is not None:
        _validate_partition_boundary(start)
        _validate_partition_boundary(end)

    if start is None:
        start = ""

    if end is None:
        end = ""

    if fs_type:
        cmd = (
            "parted",
            "-m",
            "-s",
            "--",
            device,
            "mkpart",
            part_type,
            fs_type,
            start,
            end,
        )
    else:
        cmd = ("parted", "-m", "-s", "--", device, "mkpart", part_type, start, end)

    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    return out


def mkpartfs(device, part_type, fs_type=None, start=None, end=None):
    """
    The mkpartfs actually is an alias to mkpart and is kept for compatibility.
    To know the valid options and usage syntax read mkpart documentation.

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.mkpartfs /dev/sda primary fs_type=fat32 start=0 end=639
        salt '*' partition.mkpartfs /dev/sda primary start=0 end=639
    """
    out = mkpart(device, part_type, fs_type, start, end)
    return out


def name(device, partition, name):
    """
    Set the name of partition to name. This option works only on Mac, PC98, and
    GPT disklabels. The name can be placed in quotes, if necessary.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.name /dev/sda 1 'My Documents'
    """
    _validate_device(device)

    try:
        int(partition)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid partition passed to partition.name")

    valid = string.ascii_letters + string.digits + " _-"
    for letter in name:
        if letter not in valid:
            raise CommandExecutionError("Invalid characters passed to partition.name")

    cmd = f'''parted -m -s {device} name {partition} "'{name}'"'''
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def rescue(device, start, end):
    """
    Rescue a lost partition that was located somewhere between start and end.
    If a partition is found, parted will ask if you want to create an
    entry for it in the partition table.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.rescue /dev/sda 0 8056
    """
    _validate_device(device)
    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    cmd = f"parted -m -s {device} rescue {start} {end}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def resize(device, minor, start, end):
    """
    Resizes the partition with number <minor>.

    The partition will start <start> from the beginning of the disk, and end
    <end> from the beginning of the disk. resize never changes the minor number.
    Extended partitions can be resized, so long as the new extended partition
    completely contains all logical partitions.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.resize /dev/sda 3 200 850
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.resize")

    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    out = __salt__["cmd.run"](f"parted -m -s -- {device} resize {minor} {start} {end}")
    return out.splitlines()


def rm(device, minor):  # pylint: disable=C0103
    """
    Removes the partition with number <minor>.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.rm /dev/sda 5
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.rm")

    cmd = f"parted -m -s {device} rm {minor}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def set_(device, minor, flag, state):
    """
    Changes a flag on the partition with number <minor>.

    A flag can be either "on" or "off" (make sure to use proper quoting, see
    :ref:`YAML Idiosyncrasies <yaml-idiosyncrasies>`). Some or all of these
    flags will be available, depending on what disk label you are using.

    Valid flags are:
      * boot
      * root
      * swap
      * hidden
      * raid
      * lvm
      * lba
      * hp-service
      * palo
      * prep
      * msftres
      * bios_grub
      * atvrecv
      * diag
      * legacy_boot
      * msftdata
      * irst
      * esp
      * type

    CLI Example:

    .. code-block:: bash

        salt '*' partition.set /dev/sda 1 boot '"on"'
    """
    _validate_device(device)

    try:
        int(minor)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError("Invalid minor number passed to partition.set")

    if flag not in VALID_PARTITION_FLAGS:
        raise CommandExecutionError("Invalid flag passed to partition.set")

    if state not in {"on", "off"}:
        raise CommandExecutionError("Invalid state passed to partition.set")

    cmd = f"parted -m -s {device} set {minor} {flag} {state}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def toggle(device, partition, flag):
    """
    Toggle the state of <flag> on <partition>. Valid flags are the same as
        the set command.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.toggle /dev/sda 1 boot
    """
    _validate_device(device)

    try:
        int(partition)
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError(
            "Invalid partition number passed to partition.toggle"
        )

    if flag not in VALID_PARTITION_FLAGS:
        raise CommandExecutionError("Invalid flag passed to partition.toggle")

    cmd = f"parted -m -s {device} toggle {partition} {flag}"
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def disk_set(device, flag, state):
    """
    Changes a flag on selected device.

    A flag can be either "on" or "off" (make sure to use proper
    quoting, see :ref:`YAML Idiosyncrasies
    <yaml-idiosyncrasies>`). Some or all of these flags will be
    available, depending on what disk label you are using.

    Valid flags are:
      * cylinder_alignment
      * pmbr_boot
      * implicit_partition_table

    CLI Example:

    .. code-block:: bash

        salt '*' partition.disk_set /dev/sda pmbr_boot '"on"'
    """
    _validate_device(device)

    if flag not in VALID_DISK_FLAGS:
        raise CommandExecutionError("Invalid flag passed to partition.disk_set")

    if state not in {"on", "off"}:
        raise CommandExecutionError("Invalid state passed to partition.disk_set")

    cmd = ["parted", "-m", "-s", device, "disk_set", flag, state]
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def disk_toggle(device, flag):
    """
    Toggle the state of <flag> on <device>. Valid flags are the same
    as the disk_set command.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.disk_toggle /dev/sda pmbr_boot
    """
    _validate_device(device)

    if flag not in VALID_DISK_FLAGS:
        raise CommandExecutionError("Invalid flag passed to partition.disk_toggle")

    cmd = ["parted", "-m", "-s", device, "disk_toggle", flag]
    out = __salt__["cmd.run"](cmd).splitlines()
    return out


def exists(device=""):
    """
    Check to see if the partition exists

    CLI Example:

    .. code-block:: bash

        salt '*' partition.exists /dev/sdb1
    """
    if os.path.exists(device):
        dev = os.stat(device).st_mode

        if stat.S_ISBLK(dev):
            return True

    return False


def get_block_device():
    """
    Retrieve a list of disk devices

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' partition.get_block_device
    """
    cmd = "lsblk -n -io KNAME -d -e 1,7,11 -l"
    devs = __salt__["cmd.run"](cmd).splitlines()
    return devs
