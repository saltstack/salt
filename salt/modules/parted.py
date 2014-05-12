# -*- coding: utf-8 -*-
'''
Module for managing partitions on POSIX-like systems.

:depends:   - parted, partprobe, lsblk (usually parted and util-linux packages)

Some functions may not be available, depending on your version of parted.

Check the manpage for ``parted(8)`` for more information, or the online docs
at:

http://www.gnu.org/software/parted/manual/html_chapter/parted_2.html

In light of parted not directly supporting partition IDs, some of this module
has been written to utilize sfdisk instead. For further information, please
reference the man page for ``sfdisk(8)``.
'''

# Import python libs
import os
import stat
import string
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'partition'

# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    'set_': 'set',
    'list_': 'list',
}


VALID_UNITS = set(['s', 'B', 'kB', 'MB', 'MiB', 'GB', 'GiB', 'TB', 'TiB', '%',
                   'cyl', 'chs', 'compact'])


def __virtual__():
    '''
    Only work on POSIX-like systems, which have parted and lsblk installed.
    These are usually provided by the ``parted`` and ``util-linux`` packages.
    '''
    if salt.utils.is_windows():
        return False
    if not salt.utils.which('parted'):
        return False
    if not salt.utils.which('lsblk'):
        return False
    return __virtualname__


def probe(device=''):
    '''
    Ask the kernel to update its local partition data

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.probe
        salt '*' partition.probe /dev/sda
    '''
    if device:
        dev = device.replace('/dev/', '')
        if dev not in os.listdir('/dev'):
            raise CommandExecutionError(
                'Invalid device passed to partition.probe'
            )
    cmd = 'partprobe {0}'.format(device)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def part_list(device, unit=None):
    '''
    Deprecated. Calls partition.list.

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.part_list /dev/sda
        salt '*' partition.part_list /dev/sda unit=s
        salt '*' partition.part_list /dev/sda unit=kB
    '''
    return list_(device, unit)


def list_(device, unit=None):
    '''
    partition.list device unit

    Prints partition information of given <device>

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.list /dev/sda
        salt '*' partition.list /dev/sda unit=s
        salt '*' partition.list /dev/sda unit=kB
    '''
    if device:
        dev = device.replace('/dev/', '')
        if dev not in os.listdir('/dev'):
            raise CommandExecutionError(
                'Invalid device passed to partition.part_list'
            )

    if unit:
        if unit not in VALID_UNITS:
            raise CommandExecutionError(
                'Invalid unit passed to partition.part_list'
            )
        cmd = 'parted -m -s {0} unit {1} print'.format(device, unit)
    else:
        cmd = 'parted -m -s {0} print'.format(device)

    out = __salt__['cmd.run'](cmd).splitlines()
    ret = {'info': {}, 'partitions': {}}
    mode = 'info'
    for line in out:
        if line.startswith('BYT'):
            continue
        comps = line.replace(';', '').split(':')
        if mode == 'info':
            if 7 <= len(comps) <= 8:
                ret['info'] = {
                    'disk': comps[0],
                    'size': comps[1],
                    'interface': comps[2],
                    'logical sector': comps[3],
                    'physical sector': comps[4],
                    'partition table': comps[5],
                    'model': comps[6]}
                try:
                    ret['info']['disk flags'] = comps[7]
                except IndexError:
                    # Older parted (2.x) doesn't show disk flags in the 'print'
                    # output, and will return a 7-column output for the info
                    # line. In these cases we just leave this field out of the
                    # return dict.
                    pass
                mode = 'partitions'
        else:
            ret['partitions'][comps[0]] = {
                'number': comps[0],
                'start': comps[1],
                'end': comps[2],
                'size': comps[3],
                'type': comps[4],
                'file system': comps[5],
                'flags': comps[6]}
    return ret


def align_check(device, part_type, partition):
    '''
    partition.align_check device part_type partition

    Check if partition satisfies the alignment constraint of part_type.
    Type must be "minimal" or "optimal".

    CLI Example:

    .. code-block:: bash

        salt '*' partition.align_check /dev/sda minimal 1
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError(
            'Invalid device passed to partition.align_check'
        )

    if part_type not in set(['minimal', 'optimal']):
        raise CommandExecutionError(
            'Invalid part_type passed to partition.align_check'
        )

    try:
        int(partition)
    except Exception:
        raise CommandExecutionError(
            'Invalid partition passed to partition.align_check'
        )

    cmd = 'parted -m -s {0} align-check {1} {2}'.format(
        device, part_type, partition
    )
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def check(device, minor):
    '''
    partition.check device minor

    Checks if the file system on partition <minor> has any errors.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.check 1
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.check')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.check'
        )

    cmd = 'parted -m -s {0} check {1}'.format(device, minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def cp(device, from_minor, to_minor):  # pylint: disable=C0103
    '''
    partition.check device from_minor to_minor

    Copies the file system on the partition <from-minor> to partition
        <to-minor>, deleting the original contents of the destination
        partition.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.cp /dev/sda 2 3
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.cp')

    try:
        int(from_minor)
        int(to_minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.cp'
        )

    cmd = 'parted -m -s {0} cp {1} {2}'.format(device, from_minor, to_minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def get_id(device, minor):
    '''
    partition.get_id

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
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.get_id')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.get_id'
        )

    cmd = 'sfdisk --print-id {0} {1}'.format(device, minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def set_id(device, minor, system_id):
    '''
    partition.set_id

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
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.set_id')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.set_id'
        )

    if system_id not in system_types():
        raise CommandExecutionError(
            'Invalid system_id passed to partition.set_id'
        )

    cmd = 'sfdisk --change-id {0} {1} {2}'.format(device, minor, system_id)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def system_types():
    '''
    List the system types that are supported by the installed version of sfdisk

    CLI Example:

    .. code-block:: bash

        salt '*' partition.system_types
    '''
    ret = {}
    for line in __salt__['cmd.run']('sfdisk -T').splitlines():
        if not line:
            continue
        if line.startswith('Id'):
            continue
        comps = line.strip().split()
        ret[comps[0]] = comps[1]
    return ret


def mkfs(device, fs_type):
    '''
    partition.mkfs device fs_type

    Makes a file system <fs_type> on partition <device>, destroying all data
        that resides on that partition. <fs_type> must be one of "ext2",
        "fat32", "fat16", "linux-swap" or "reiserfs" (if libreiserfs is
        installed)

    CLI Example:

    .. code-block:: bash

        salt '*' partition.mkfs /dev/sda2 fat32
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.mkfs')

    if fs_type not in set(['ext2', 'fat32', 'fat16', 'linux-swap', 'reiserfs',
                          'hfs', 'hfs+', 'hfsx', 'NTFS', 'ufs']):
        raise CommandExecutionError('Invalid fs_type passed to partition.mkfs')

    cmd = 'mkfs.{0} {1}'.format(fs_type, device)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def mklabel(device, label_type):
    '''
    partition.mklabel device label_type

    Create a new disklabel (partition table) of label_type.
    Type should be one of "aix", "amiga", "bsd", "dvh", "gpt", "loop", "mac",
    "msdos", "pc98", or "sun".

    CLI Example:

    .. code-block:: bash

        salt '*' partition.mklabel /dev/sda msdos
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError(
            'Invalid device passed to partition.mklabel'
        )

    if label_type not in set(['aix', 'amiga', 'bsd', 'dvh', 'gpt', 'loop', 'mac',
                             'msdos', 'pc98', 'sun']):
        raise CommandExecutionError(
            'Invalid label_type passed to partition.mklabel'
        )

    cmd = 'parted -m -s {0} mklabel {1}'.format(device, label_type)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def _validate_partition_boundary(boundary):
    try:
        for unit in VALID_UNITS:
            if boundary.endswith(unit):
                return
        int(boundary)
    except Exception:
        raise CommandExecutionError(
            'Invalid partition boundary passed: "{0}"'.format(boundary)
        )


def mkpart(device, part_type, fs_type=None, start=None, end=None):
    '''
    partition.mkpart device part_type fs_type start end

    Make a part_type partition for filesystem fs_type, beginning at start and
        ending at end (by default in megabytes).  part_type should be one of
        "primary", "logical", or "extended".

    CLI Examples:

    .. code-block:: bash

        salt '*' partition.mkpart /dev/sda primary fat32 0 639
        salt '*' partition.mkpart /dev/sda primary start=0 end=639
    '''
    if not start or not end:
        raise CommandExecutionError(
            'partition.mkpart requires a start and an end'
        )

    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError(
            'Invalid device passed to partition.mkpart'
        )

    if part_type not in set(['primary', 'logical', 'extended']):
        raise CommandExecutionError(
            'Invalid part_type passed to partition.mkpart'
        )

    if fs_type not in set(['ext2', 'fat32', 'fat16', 'linux-swap', 'reiserfs',
                          'hfs', 'hfs+', 'hfsx', 'NTFS', 'ufs', 'xfs']):
        raise CommandExecutionError(
            'Invalid fs_type passed to partition.mkpart'
        )

    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    if fs_type:
        cmd = 'parted -m -s -- {0} mkpart {1} {2} {3} {4}'.format(
            device, part_type, fs_type, start, end
        )
    else:
        cmd = 'parted -m -s -- {0} mkpart {1} {2} {3}'.format(
            device, part_type, start, end
        )

    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def mkpartfs(device, part_type, fs_type, start, end):
    '''
    partition.mkpartfs device part_type fs_type start end

    Make a <part_type> partition with a new filesystem of <fs_type>, beginning
        at <start> and ending at <end> (by default in megabytes).  <part_type>
        should be one of "primary", "logical", or "extended". <fs_type> must be
        one of "ext2", "fat32", "fat16", "linux-swap" or "reiserfs" (if
        libreiserfs is installed)

    CLI Example:

    .. code-block:: bash

        salt '*' partition.mkpartfs /dev/sda logical ext2 440 670
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError(
            'Invalid device passed to partition.mkpartfs'
        )

    if part_type not in set(['primary', 'logical', 'extended']):
        raise CommandExecutionError(
            'Invalid part_type passed to partition.mkpartfs'
        )

    if fs_type not in set(['ext2', 'fat32', 'fat16', 'linux-swap', 'reiserfs',
                           'hfs', 'hfs+', 'hfsx', 'NTFS', 'ufs', 'xfs']):
        raise CommandExecutionError(
            'Invalid fs_type passed to partition.mkpartfs'
        )

    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    cmd = 'parted -m -s -- {0} mkpart {1} {2} {3} {4}'.format(
        device, part_type, fs_type, start, end
    )
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def name(device, partition, name):
    '''
    partition.name device partition name

    Set the name of partition to name. This option works only on Mac, PC98,
        and GPT disklabels. The name can be placed in quotes, if necessary.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.name /dev/sda 1 'My Documents'
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.name')

    try:
        int(partition)
    except Exception:
        raise CommandExecutionError(
            'Invalid partition passed to partition.name'
        )

    valid = string.ascii_letters + string.digits + ' _-'
    for letter in name:
        if letter not in valid:
            raise CommandExecutionError(
                'Invalid characters passed to partition.name'
            )

    cmd = 'parted -m -s {0} name {1} {2}'.format(device, partition, name)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def rescue(device, start, end):
    '''
    partition.rescue device start end

    Rescue a lost partition that was located somewhere between start and end.
        If a partition is found, parted will ask if you want to create an
        entry for it in the partition table.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.rescue /dev/sda 0 8056
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.rescue')

    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    cmd = 'parted -m -s {0} rescue {1} {2}'.format(device, start, end)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def resize(device, minor, start, end):
    '''
    partition.resize device minor, start, end

    Resizes the partition with number <minor>. The partition will start <start>
        from the beginning of the disk, and end <end> from the beginning of the
        disk. resize never changes the minor number. Extended partitions can be
        resized, so long as the new extended partition completely contains all
        logical partitions.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.resize /dev/sda 3 200 850
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.resize')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.resize'
        )

    _validate_partition_boundary(start)
    _validate_partition_boundary(end)

    out = __salt__['cmd.run'](
        'parted -m -s -- {0} resize {1} {2} {3}'.format(
            device, minor, start, end
        )
    )
    return out.splitlines()


def rm(device, minor):  # pylint: disable=C0103
    '''
    partition.rm device minor

    Removes the partition with number <minor>.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.rm /dev/sda 5
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.rm')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.rm'
        )

    cmd = 'parted -m -s {0} rm {1}'.format(device, minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def set_(device, minor, flag, state):
    '''
    partition.set device  minor flag state

    Changes a flag on the partition with number <minor>. A flag can be either
        "on" or "off". Some or all of these flags will be available, depending
        on what disk label you are using.

    CLI Example:

    .. code-block:: bash

        salt '*' partition.set /dev/sda 1 boot on
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.set')

    try:
        int(minor)
    except Exception:
        raise CommandExecutionError(
            'Invalid minor number passed to partition.set'
        )

    if flag not in set(['bios_grub', 'legacy_boot', 'boot', 'lba', 'root',
                       'swap', 'hidden', 'raid', 'LVM', 'PALO', 'PREP', 'DIAG']):
        raise CommandExecutionError('Invalid flag passed to partition.set')

    if state not in set(['on', 'off']):
        raise CommandExecutionError('Invalid state passed to partition.set')

    cmd = 'parted -m -s {0} set {1} {2} {3}'.format(device, minor, flag, state)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def toggle(device, partition, flag):
    '''
    partition.toggle device partition flag

    Toggle the state of <flag> on <partition>

    CLI Example:

    .. code-block:: bash

        salt '*' partition.name /dev/sda 1 boot
    '''
    dev = device.replace('/dev/', '')
    if dev not in os.listdir('/dev'):
        raise CommandExecutionError('Invalid device passed to partition.toggle')

    try:
        int(partition)
    except Exception:
        raise CommandExecutionError(
            'Invalid partition number passed to partition.toggle'
        )

    if flag not in set(['bios_grub', 'legacy_boot', 'boot', 'lba', 'root',
                       'swap', 'hidden', 'raid', 'LVM', 'PALO', 'PREP', 'DIAG']):
        raise CommandExecutionError('Invalid flag passed to partition.toggle')

    cmd = 'parted -m -s {0} toggle {1} {2} {3}'.format(device, partition, flag)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def exists(device=''):
    '''
    partition.exists device

    Check to see if the partition exists

    CLI Example:

    .. code-block:: bash

        salt '*' partition.exists /dev/sdb1
    '''
    if os.path.exists(device):
        dev = os.stat(device).st_mode

        if stat.S_ISBLK(dev):
            return True

    return False


def get_block_device():
    '''
    Retrieve a list of disk devices

    .. versionadded:: Helium

    CLI Example:

    .. code-block:: bash

        salt '*' partition.get_block_device
    '''
    ret = []
    cmd = '/bin/lsblk -n -io KNAME -d -e 1,7,11 -l'
    devs = __salt__['cmd.run'](cmd).splitlines()
    for dev in devs:
        if dev not in os.listdir('/dev'):
            continue
        ret.append(dev)
    return ret
