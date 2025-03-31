"""
Module for managing disks and blockdevices
"""

import collections
import decimal
import logging
import os
import re
import subprocess

import salt.utils.decorators
import salt.utils.decorators.path
import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandExecutionError

__func_alias__ = {"format_": "format"}

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return False, "This module doesn't work on Windows."
    return True


def _parse_numbers(text):
    """
    Convert a string to a number, allowing for a K|M|G|T postfix, 32.8K.
    Returns a decimal number if the string is a real number,
    or the string unchanged otherwise.
    """
    if text.isdigit():
        return decimal.Decimal(text)

    try:
        postPrefixes = {
            "K": "10E3",
            "M": "10E6",
            "G": "10E9",
            "T": "10E12",
            "P": "10E15",
            "E": "10E18",
            "Z": "10E21",
            "Y": "10E24",
        }
        if text[-1] in postPrefixes:
            v = decimal.Decimal(text[:-1])
            v = v * decimal.Decimal(postPrefixes[text[-1]])
            return v
        else:
            return decimal.Decimal(text)
    except ValueError:
        return text


def _clean_flags(args, caller):
    """
    Sanitize flags passed into df
    """
    flags = ""
    if args is None:
        return flags
    # TODO: most of these cause the result parsing to fail
    allowed = ("a", "B", "h", "H", "i", "k", "l", "P", "t", "T", "x", "v")
    for flag in args:
        if flag in allowed:
            flags += flag
        else:
            raise CommandExecutionError(f"Invalid flag passed to {caller}")
    return flags


def usage(args=None):
    """
    Return usage information for volumes mounted on this minion

    args
        Sequence of flags to pass to the ``df`` command.

    .. versionchanged:: 2019.2.0

        Default for SunOS changed to 1 kilobyte blocks

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    """
    flags = _clean_flags(args, "disk.usage")
    if not os.path.isfile("/etc/mtab") and __grains__["kernel"] == "Linux":
        log.error("df cannot run without /etc/mtab")
        if __grains__.get("virtual_subtype") == "LXC":
            log.error(
                "df command failed and LXC detected. If you are running "
                "a Docker container, consider linking /proc/mounts to "
                "/etc/mtab or consider running Docker with -privileged"
            )
        return {}
    if __grains__["kernel"] == "Linux":
        cmd = "df -P"
    elif __grains__["kernel"] == "OpenBSD" or __grains__["kernel"] == "AIX":
        cmd = "df -kP"
    elif __grains__["kernel"] == "SunOS":
        cmd = "df -k"
    else:
        cmd = "df"
    if flags:
        cmd += f" -{flags}"
    ret = {}
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    oldline = None
    for line in out:
        if not line:
            continue
        if line.startswith("Filesystem"):
            continue
        if oldline:
            line = oldline + " " + line
        comps = line.split()
        if len(comps) == 1:
            oldline = line
            continue
        else:
            oldline = None
        while len(comps) >= 2 and not comps[1].isdigit():
            comps[0] = f"{comps[0]} {comps[1]}"
            comps.pop(1)
        if len(comps) < 2:
            continue
        try:
            if __grains__["kernel"] == "Darwin":
                ret[comps[8]] = {
                    "filesystem": comps[0],
                    "512-blocks": comps[1],
                    "used": comps[2],
                    "available": comps[3],
                    "capacity": comps[4],
                    "iused": comps[5],
                    "ifree": comps[6],
                    "%iused": comps[7],
                }
            else:
                ret[comps[5]] = {
                    "filesystem": comps[0],
                    "1K-blocks": comps[1],
                    "used": comps[2],
                    "available": comps[3],
                    "capacity": comps[4],
                }
        except IndexError:
            log.error("Problem parsing disk usage information")
            ret = {}
    return ret


def inodeusage(args=None):
    """
    Return inode usage information for volumes mounted on this minion

    args
        Sequence of flags to pass to the ``df`` command.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.inodeusage
    """
    flags = _clean_flags(args, "disk.inodeusage")
    if __grains__["kernel"] == "AIX":
        cmd = "df -i"
    else:
        cmd = "df -iP"
    if flags:
        cmd += f" -{flags}"
    ret = {}
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in out:
        if line.startswith("Filesystem"):
            continue
        comps = line.split()
        # Don't choke on empty lines
        if not comps:
            continue

        try:
            if __grains__["kernel"] == "OpenBSD":
                ret[comps[8]] = {
                    "inodes": int(comps[5]) + int(comps[6]),
                    "used": comps[5],
                    "free": comps[6],
                    "use": comps[7],
                    "filesystem": comps[0],
                }
            elif __grains__["kernel"] == "AIX":
                ret[comps[6]] = {
                    "inodes": comps[4],
                    "used": comps[5],
                    "free": comps[2],
                    "use": comps[5],
                    "filesystem": comps[0],
                }
            else:
                ret[comps[5]] = {
                    "inodes": comps[1],
                    "used": comps[2],
                    "free": comps[3],
                    "use": comps[4],
                    "filesystem": comps[0],
                }
        except (IndexError, ValueError):
            log.error("Problem parsing inode usage information")
            ret = {}
    return ret


def percent(args=None):
    """
    Return partition information for volumes mounted on this minion

    args
        Specify a single partition for which to return data.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.percent /var
    """
    if __grains__["kernel"] == "Linux":
        cmd = "df -P"
    elif __grains__["kernel"] == "OpenBSD" or __grains__["kernel"] == "AIX":
        cmd = "df -kP"
    else:
        cmd = "df"
    ret = {}
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    for line in out:
        if not line:
            continue
        if line.startswith("Filesystem"):
            continue
        comps = line.split()
        while len(comps) >= 2 and not comps[1].isdigit():
            comps[0] = f"{comps[0]} {comps[1]}"
            comps.pop(1)
        if len(comps) < 2:
            continue
        try:
            if __grains__["kernel"] == "Darwin":
                ret[comps[8]] = comps[4]
            else:
                ret[comps[5]] = comps[4]
        except IndexError:
            log.error("Problem parsing disk usage information")
            ret = {}
    if args and args not in ret:
        log.error(
            "Problem parsing disk usage information: Partition '%s' does not exist!",
            args,
        )
        ret = {}
    elif args:
        return ret[args]

    return ret


@salt.utils.decorators.path.which("blkid")
def blkid(device=None, token=None):
    """
    Return block device attributes: UUID, LABEL, etc. This function only works
    on systems where blkid is available.

    device
        Device name from the system

    token
        Any valid token used for the search

    CLI Example:

    .. code-block:: bash

        salt '*' disk.blkid
        salt '*' disk.blkid /dev/sda
        salt '*' disk.blkid token='UUID=6a38ee5-7235-44e7-8b22-816a403bad5d'
        salt '*' disk.blkid token='TYPE=ext4'
    """
    cmd = ["blkid"]
    if device:
        cmd.append(device)
    elif token:
        cmd.extend(["-t", token])

    ret = {}
    blkid_result = __salt__["cmd.run_all"](cmd, python_shell=False)

    if blkid_result["retcode"] > 0:
        return ret

    for line in blkid_result["stdout"].splitlines():
        if not line:
            continue
        comps = line.split()
        device = comps[0][:-1]
        info = {}
        device_attributes = re.split('"*"', line.partition(" ")[2])
        for key, value in zip(*[iter(device_attributes)] * 2):
            key = key.strip("=").strip(" ")
            info[key] = value.strip('"')
        ret[device] = info

    return ret


def tune(device, **kwargs):
    """
    Set attributes for the specified device

    CLI Example:

    .. code-block:: bash

        salt '*' disk.tune /dev/sda1 read-ahead=1024 read-write=True

    Valid options are: ``read-ahead``, ``filesystem-read-ahead``,
    ``read-only``, ``read-write``.

    See the ``blockdev(8)`` manpage for a more complete description of these
    options.
    """

    kwarg_map = {
        "read-ahead": "setra",
        "filesystem-read-ahead": "setfra",
        "read-only": "setro",
        "read-write": "setrw",
    }
    opts = ""
    args = []
    for key in kwargs:
        if key in kwarg_map:
            switch = kwarg_map[key]
            if key != "read-write":
                args.append(switch.replace("set", "get"))
            else:
                args.append("getro")
            if kwargs[key] == "True" or kwargs[key] is True:
                opts += f"--{key} "
            else:
                opts += f"--{switch} {kwargs[key]} "
    cmd = f"blockdev {opts}{device}"
    out = __salt__["cmd.run"](cmd, python_shell=False).splitlines()
    return dump(device, args)


def wipe(device):
    """
    Remove the filesystem information

    CLI Example:

    .. code-block:: bash

        salt '*' disk.wipe /dev/sda1
    """

    cmd = f"wipefs -a {device}"
    try:
        out = __salt__["cmd.run_all"](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out["retcode"] == 0:
        return True
    else:
        log.error("Error wiping device %s: %s", device, out["stderr"])
        return False


def dump(device, args=None):
    """
    Return all contents of dumpe2fs for a specified device

    device
        The device path to dump.

    args
        A list of attributes to return. Returns all by default.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.dump /dev/sda1
    """
    cmd = (
        "blockdev --getro --getsz --getss --getpbsz --getiomin --getioopt --getalignoff"
        " --getmaxsect --getsize --getsize64 --getra --getfra {}".format(device)
    )
    ret = {}
    opts = [c[2:] for c in cmd.split() if c.startswith("--")]
    out = __salt__["cmd.run_all"](cmd, python_shell=False)
    if out["retcode"] == 0:
        lines = [line for line in out["stdout"].splitlines() if line]
        count = 0
        for line in lines:
            ret[opts[count]] = line
            count = count + 1
        if args:
            temp_ret = {}
            for arg in args:
                temp_ret[arg] = ret[arg]
            return temp_ret
        else:
            return ret
    else:
        return False


def resize2fs(device):
    """
    Resizes the filesystem.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.resize2fs /dev/sda1
    """
    cmd = f"resize2fs {device}"
    try:
        out = __salt__["cmd.run_all"](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out["retcode"] == 0:
        return True


@salt.utils.decorators.path.which("sync")
@salt.utils.decorators.path.which("mkfs")
def format_(
    device,
    fs_type="ext4",
    inode_size=None,
    lazy_itable_init=None,
    fat=None,
    force=False,
):
    """
    Format a filesystem onto a device

    .. versionadded:: 2016.11.0

    device
        The device in which to create the new filesystem

    fs_type
        The type of filesystem to create

    inode_size
        Size of the inodes

        This option is only enabled for ext and xfs filesystems

    lazy_itable_init
        If enabled and the uninit_bg feature is enabled, the inode table will
        not be fully initialized by mke2fs.  This speeds up filesystem
        initialization noticeably, but it requires the kernel to finish
        initializing the filesystem  in  the  background  when  the filesystem
        is first mounted.  If the option value is omitted, it defaults to 1 to
        enable lazy inode table zeroing.

        This option is only enabled for ext filesystems

    fat
        FAT size option. Can be 12, 16 or 32, and can only be used on
        fat or vfat filesystems.

    force
        Force mke2fs to create a filesystem, even if the specified device is
        not a partition on a block special device. This option is only enabled
        for ext and xfs filesystems

        This option is dangerous, use it with caution.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.format /dev/sdX1
    """
    cmd = ["mkfs", "-t", str(fs_type)]
    if inode_size is not None:
        if fs_type[:3] == "ext":
            cmd.extend(["-i", str(inode_size)])
        elif fs_type == "xfs":
            cmd.extend(["-i", f"size={inode_size}"])
    if lazy_itable_init is not None:
        if fs_type[:3] == "ext":
            cmd.extend(["-E", f"lazy_itable_init={lazy_itable_init}"])
    if fat is not None and fat in (12, 16, 32):
        if fs_type[-3:] == "fat":
            cmd.extend(["-F", fat])
    if force:
        if fs_type[:3] == "ext":
            cmd.append("-F")
        elif fs_type == "xfs":
            cmd.append("-f")
    cmd.append(str(device))

    mkfs_success = __salt__["cmd.retcode"](cmd, ignore_retcode=True) == 0
    sync_success = __salt__["cmd.retcode"]("sync", ignore_retcode=True) == 0

    return all([mkfs_success, sync_success])


@salt.utils.decorators.path.which_bin(["lsblk", "df"])
def fstype(device):
    """
    Return the filesystem name of the specified device

    .. versionadded:: 2016.11.0

    device
        The name of the device

    CLI Example:

    .. code-block:: bash

        salt '*' disk.fstype /dev/sdX1
    """
    if salt.utils.path.which("lsblk"):
        lsblk_out = __salt__["cmd.run"](f"lsblk -o fstype {device}").splitlines()
        if len(lsblk_out) > 1:
            fs_type = lsblk_out[1].strip()
            if fs_type:
                return fs_type

    if salt.utils.path.which("df"):
        # the fstype was not set on the block device, so inspect the filesystem
        # itself for its type
        if __grains__["kernel"] == "AIX" and os.path.isfile("/usr/sysv/bin/df"):
            df_out = __salt__["cmd.run"](f"/usr/sysv/bin/df -n {device}").split()
            if len(df_out) > 2:
                fs_type = df_out[2]
                if fs_type:
                    return fs_type
        else:
            df_out = __salt__["cmd.run"](f"df -T {device}").splitlines()
            if len(df_out) > 1:
                fs_type = df_out[1]
                if fs_type:
                    return fs_type

    return ""


@salt.utils.decorators.path.which("hdparm")
def _hdparm(args, failhard=True):
    """
    Execute hdparm
    Fail hard when required
    return output when possible
    """
    cmd = f"hdparm {args}"
    result = __salt__["cmd.run_all"](cmd)
    if result["retcode"] != 0:
        msg = "{}: {}".format(cmd, result["stderr"])
        if failhard:
            raise CommandExecutionError(msg)
        else:
            log.warning(msg)

    return result["stdout"]


@salt.utils.decorators.path.which("hdparm")
def hdparms(disks, args="aAbBcCdgHiJkMmNnQrRuW"):
    """
    Retrieve disk parameters.

    .. versionadded:: 2016.3.0

    disks
        Single disk or list of disks to query.

    args
        Sequence of ``hdparm`` flags to fetch.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.hdparms /dev/sda
    """
    if isinstance(args, (list, tuple)):
        args = "".join(args)

    if not isinstance(disks, (list, tuple)):
        disks = [disks]

    out = {}
    for disk in disks:
        if not disk.startswith("/dev"):
            disk = f"/dev/{disk}"
        disk_data = {}
        for line in _hdparm(f"-{args} {disk}", False).splitlines():
            line = line.strip()
            if not line or line == disk + ":":
                continue

            if ":" in line:
                key, vals = line.split(":", 1)
                key = re.sub(r" is$", "", key)
            elif "=" in line:
                key, vals = line.split("=", 1)
            else:
                continue
            key = key.strip().lower().replace(" ", "_")
            vals = vals.strip()

            rvals = []
            if re.match(r"[0-9]+ \(.*\)", vals):
                vals = vals.split(" ")
                rvals.append(int(vals[0]))
                rvals.append(vals[1].strip("()"))
            else:
                valdict = {}
                for val in re.split(r"[/,]", vals.strip()):
                    val = val.strip()
                    try:
                        val = int(val)
                        rvals.append(val)
                    except Exception:  # pylint: disable=broad-except
                        if "=" in val:
                            deep_key, val = val.split("=", 1)
                            deep_key = deep_key.strip()
                            val = val.strip()
                            if val:
                                valdict[deep_key] = val
                        elif val:
                            rvals.append(val)
                if valdict:
                    rvals.append(valdict)
                if not rvals:
                    continue
                elif len(rvals) == 1:
                    rvals = rvals[0]
            disk_data[key] = rvals

        out[disk] = disk_data

    return out


@salt.utils.decorators.path.which("hdparm")
def hpa(disks, size=None):
    """
    Get/set Host Protected Area settings

    T13 INCITS 346-2001 (1367D) defines the BEER (Boot Engineering Extension Record)
    and PARTIES (Protected Area Run Time Interface Extension Services), allowing
    for a Host Protected Area on a disk.

    It's often used by OEMS to hide parts of a disk, and for overprovisioning SSD's

    .. warning::
        Setting the HPA might clobber your data, be very careful with this on active disks!

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' disk.hpa /dev/sda
        salt '*' disk.hpa /dev/sda 5%
        salt '*' disk.hpa /dev/sda 10543256
    """

    hpa_data = {}
    for disk, data in hdparms(disks, "N").items():
        visible, total, status = next(iter(data.values()))
        if visible == total or "disabled" in status:
            hpa_data[disk] = {"total": total}
        else:
            hpa_data[disk] = {
                "total": total,
                "visible": visible,
                "hidden": total - visible,
            }

    if size is None:
        return hpa_data

    for disk, data in hpa_data.items():
        try:
            size = data["total"] - int(size)
        except Exception:  # pylint: disable=broad-except
            if "%" in size:
                size = int(size.strip("%"))
                size = (100 - size) * data["total"]
                size /= 100
        if size <= 0:
            size = data["total"]

        _hdparm(f"--yes-i-know-what-i-am-doing -Np{size} {disk}")


def smart_attributes(dev, attributes=None, values=None):
    """
    Fetch SMART attributes
    Providing attributes will deliver only requested attributes
    Providing values will deliver only requested values for attributes

    Default is the Backblaze recommended
    set (https://www.backblaze.com/blog/hard-drive-smart-stats/):
    (5,187,188,197,198)

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' disk.smart_attributes /dev/sda
        salt '*' disk.smart_attributes /dev/sda attributes=(5,187,188,197,198)
    """

    if not dev.startswith("/dev/"):
        dev = "/dev/" + dev

    cmd = f"smartctl --attributes {dev}"
    smart_result = __salt__["cmd.run_all"](cmd, output_loglevel="quiet")
    if smart_result["retcode"] != 0:
        raise CommandExecutionError(smart_result["stderr"])

    smart_result = iter(smart_result["stdout"].splitlines())

    fields = []
    for line in smart_result:
        if line.startswith("ID#"):
            fields = re.split(r"\s+", line.strip())
            fields = [key.lower() for key in fields[1:]]
            break

    if values is not None:
        fields = [field if field in values else "_" for field in fields]

    smart_attr = {}
    for line in smart_result:
        if not re.match(r"[\s]*\d", line):
            break

        line = re.split(r"\s+", line.strip(), maxsplit=len(fields))
        attr = int(line[0])

        if attributes is not None and attr not in attributes:
            continue

        data = dict(zip(fields, line[1:]))
        try:
            del data["_"]
        except Exception:  # pylint: disable=broad-except
            pass

        for field in data:
            val = data[field]
            try:
                val = int(val)
            except Exception:  # pylint: disable=broad-except
                try:
                    val = [int(value) for value in val.split(" ")]
                except Exception:  # pylint: disable=broad-except
                    pass
            data[field] = val

        smart_attr[attr] = data

    return smart_attr


@salt.utils.decorators.path.which("iostat")
def iostat(interval=1, count=5, disks=None):
    """
    Gather and return (averaged) IO stats.

    .. versionadded:: 2016.3.0

    .. versionchanged:: 2016.11.4
        Added support for AIX

    CLI Example:

    .. code-block:: bash

        salt '*' disk.iostat 1 5 disks=sda
    """
    if salt.utils.platform.is_linux():
        return _iostat_linux(interval, count, disks)
    elif salt.utils.platform.is_freebsd():
        return _iostat_fbsd(interval, count, disks)
    elif salt.utils.platform.is_aix():
        return _iostat_aix(interval, count, disks)


def _iostats_dict(header, stats):
    """
    Transpose collected data, average it, stomp it in dict using header

    Use Decimals so we can properly calc & round, convert to float 'caus' we can't transmit Decimals over 0mq
    """
    stats = [
        float((sum(stat) / len(stat)).quantize(decimal.Decimal(".01")))
        for stat in zip(*stats)
    ]
    stats = dict(zip(header, stats))
    return stats


def _iostat_fbsd(interval, count, disks):
    """
    Tested on FreeBSD, quite likely other BSD's only need small changes in cmd syntax
    """
    if disks is None:
        iostat_cmd = f"iostat -xC -w {interval} -c {count} "
    elif isinstance(disks, str):
        iostat_cmd = f"iostat -x -w {interval} -c {count} {disks}"
    else:
        iostat_cmd = "iostat -x -w {} -c {} {}".format(interval, count, " ".join(disks))

    sys_stats = []
    dev_stats = collections.defaultdict(list)
    sys_header = []
    dev_header = []
    h_len = 1000  # randomly absurdly high

    ret = iter(
        __salt__["cmd.run_stdout"](iostat_cmd, output_loglevel="quiet").splitlines()
    )
    for line in ret:
        if not line.startswith("device"):
            continue
        elif not dev_header:
            dev_header = line.split()[1:]
        while line is not False:
            line = next(ret, False)
            if not line or not line[0].isalnum():
                break
            line = line.split()
            disk = line[0]
            stats = [decimal.Decimal(x) for x in line[1:]]
            # h_len will become smallest number of fields in stat lines
            if len(stats) < h_len:
                h_len = len(stats)
            dev_stats[disk].append(stats)

    iostats = {}

    # The header was longer than the smallest number of fields
    # Therefore the sys stats are hidden in there
    if h_len < len(dev_header):
        sys_header = dev_header[h_len:]
        dev_header = dev_header[0:h_len]

        for disk, stats in dev_stats.items():
            if len(stats[0]) > h_len:
                sys_stats = [stat[h_len:] for stat in stats]
                dev_stats[disk] = [stat[0:h_len] for stat in stats]

        iostats["sys"] = _iostats_dict(sys_header, sys_stats)

    for disk, stats in dev_stats.items():
        iostats[disk] = _iostats_dict(dev_header, stats)

    return iostats


def _iostat_linux(interval, count, disks):
    if disks is None:
        iostat_cmd = f"iostat -x {interval} {count} "
    elif isinstance(disks, str):
        iostat_cmd = f"iostat -xd {interval} {count} {disks}"
    else:
        iostat_cmd = "iostat -xd {} {} {}".format(interval, count, " ".join(disks))

    sys_stats = []
    dev_stats = collections.defaultdict(list)
    sys_header = []
    dev_header = []

    ret = iter(
        __salt__["cmd.run_stdout"](iostat_cmd, output_loglevel="quiet").splitlines()
    )
    for line in ret:
        if line.startswith("avg-cpu:"):
            if not sys_header:
                sys_header = tuple(line.split()[1:])
            line = [decimal.Decimal(x) for x in next(ret).split()]
            sys_stats.append(line)
        elif line.startswith("Device:"):
            if not dev_header:
                dev_header = tuple(line.split()[1:])
            while line is not False:
                line = next(ret, False)
                if not line or not line[0].isalnum():
                    break
                line = line.split()
                disk = line[0]
                stats = [decimal.Decimal(x) for x in line[1:]]
                dev_stats[disk].append(stats)

    iostats = {}

    if sys_header:
        iostats["sys"] = _iostats_dict(sys_header, sys_stats)

    for disk, stats in dev_stats.items():
        iostats[disk] = _iostats_dict(dev_header, stats)

    return iostats


def _iostat_aix(interval, count, disks):
    """
    AIX support to gather and return (averaged) IO stats.
    """
    log.debug("AIX disk iostat entry")

    if disks is None:
        iostat_cmd = f"iostat -dD {interval} {count} "
    elif isinstance(disks, str):
        iostat_cmd = f"iostat -dD {disks} {interval} {count}"
    else:
        iostat_cmd = "iostat -dD {} {} {}".format(" ".join(disks), interval, count)

    ret = {}
    procn = None
    fields = []
    disk_name = ""
    disk_mode = ""
    dev_stats = collections.defaultdict(list)
    for line in __salt__["cmd.run"](iostat_cmd).splitlines():
        # Note: iostat -dD is per-system
        #
        # root@l490vp031_pub:~/devtest# iostat -dD hdisk6 1 3
        #
        # System configuration: lcpu=8 drives=1 paths=2 vdisks=2
        #
        # hdisk6          xfer:  %tm_act      bps      tps      bread      bwrtn
        #                          0.0      0.0      0.0        0.0        0.0
        #                read:      rps  avgserv  minserv  maxserv   timeouts      fails
        #                          0.0      0.0      0.0      0.0           0          0
        #               write:      wps  avgserv  minserv  maxserv   timeouts      fails
        #                          0.0      0.0      0.0      0.0           0          0
        #               queue:  avgtime  mintime  maxtime  avgwqsz    avgsqsz     sqfull
        #                          0.0      0.0      0.0      0.0        0.0         0.0
        # --------------------------------------------------------------------------------
        #
        # hdisk6          xfer:  %tm_act      bps      tps      bread      bwrtn
        #                          9.6     16.4K     4.0       16.4K       0.0
        #                read:      rps  avgserv  minserv  maxserv   timeouts      fails
        #                          4.0      4.9      0.3      9.9           0          0
        #               write:      wps  avgserv  minserv  maxserv   timeouts      fails
        #                          0.0      0.0      0.0      0.0           0          0
        #               queue:  avgtime  mintime  maxtime  avgwqsz    avgsqsz     sqfull
        #                          0.0      0.0      0.0      0.0        0.0         0.0
        # --------------------------------------------------------------------------------
        #
        # hdisk6          xfer:  %tm_act      bps      tps      bread      bwrtn
        #                          0.0      0.0      0.0        0.0        0.0
        #                read:      rps  avgserv  minserv  maxserv   timeouts      fails
        #                          0.0      0.0      0.3      9.9           0          0
        #               write:      wps  avgserv  minserv  maxserv   timeouts      fails
        #                          0.0      0.0      0.0      0.0           0          0
        #               queue:  avgtime  mintime  maxtime  avgwqsz    avgsqsz     sqfull
        #                          0.0      0.0      0.0      0.0        0.0         0.0
        # --------------------------------------------------------------------------------
        if not line or line.startswith("System") or line.startswith("-----------"):
            continue

        if not re.match(r"\s", line):
            # seen disk name
            dsk_comps = line.split(":")
            dsk_firsts = dsk_comps[0].split()
            disk_name = dsk_firsts[0]
            disk_mode = dsk_firsts[1]
            fields = dsk_comps[1].split()
            if disk_name not in dev_stats.keys():
                dev_stats[disk_name] = []
                procn = len(dev_stats[disk_name])
                dev_stats[disk_name].append({})
                dev_stats[disk_name][procn][disk_mode] = {}
                dev_stats[disk_name][procn][disk_mode]["fields"] = fields
                dev_stats[disk_name][procn][disk_mode]["stats"] = []
            continue

        if ":" in line:
            comps = line.split(":")
            fields = comps[1].split()
            disk_mode = comps[0].lstrip()
            if disk_mode not in dev_stats[disk_name][0].keys():
                dev_stats[disk_name][0][disk_mode] = {}
                dev_stats[disk_name][0][disk_mode]["fields"] = fields
                dev_stats[disk_name][0][disk_mode]["stats"] = []
        else:
            line = line.split()
            stats = [_parse_numbers(x) for x in line[:]]
            dev_stats[disk_name][0][disk_mode]["stats"].append(stats)

    iostats = {}

    for disk, list_modes in dev_stats.items():
        iostats[disk] = {}
        for modes in list_modes:
            for disk_mode in modes.keys():
                fields = modes[disk_mode]["fields"]
                stats = modes[disk_mode]["stats"]
                iostats[disk][disk_mode] = _iostats_dict(fields, stats)

    return iostats


def get_fstype_from_path(path):
    """
    Return the filesystem type of the underlying device for a specified path.

    .. versionadded:: 3006.0

    path
        The path for the function to evaluate.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.get_fstype_from_path /root
    """
    dev = __salt__["mount.get_device_from_path"](path)
    return fstype(dev)
