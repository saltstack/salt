'''
Module for managing partitions on posix-like systems.

Some functions may not be available, depending on your version of parted.

Check man 8 parted for more information, or the online docs at:

http://www.gnu.org/software/parted/manual/html_chapter/parted_2.html
'''

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if __grains__['os'] in disable:
        return False
    return 'partition'


def probe(device=''):
    '''
    Ask the kernel to update its local partition data

    CLI Examples::

        salt '*' partition.probe
        salt '*' partition.probe /dev/sda
    '''
    cmd = 'partprobe {0}'.format(device)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def part_list(device, unit=None):
    '''
    Ask the kernel to update its local partition data

    CLI Examples::

        salt '*' partition.partlist /dev/sda
        salt '*' partition.partlist /dev/sda unit=s
        salt '*' partition.partlist /dev/sda unit=kB
    '''
    if unit:
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
            if len(comps) == 8:
                ret['info'] = {
                    'disk': comps[0],
                    'size': comps[1],
                    'interface': comps[2],
                    'logical sector': comps[3],
                    'physical sector': comps[4],
                    'partition table': comps[5],
                    'model': comps[6],
                    'disk flags': comps[7]}
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

    CLI Example::

        salt '*' partition.align_check /dev/sda minimal 1
    '''
    cmd = 'parted -m -s {0} align-check {1} {2}'.format(device, part_type, partition)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def check(device, minor):
    '''
    partition.check device minor

    Checks if the file system on partition <minor> has any errors.

    CLI Example::

        salt '*' partition.check 1
    '''
    cmd = 'parted -m -s {0} check {1}'.format(device, minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def cp(device, from_minor, to_minor):
    '''
    partition.check device from_minor to_minor

    Copies the file system on the partition <from-minor> to partition
        <to-minor>, deleting the original contents of the destination
        partition.

    CLI Example::

        salt '*' partition.cp /dev/sda 2 3
    '''
    cmd = 'parted -m -s {0} cp {1} {2}'.format(device, from_minor, to_minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def mkfs(device, minor, fs_type):
    '''
    partition.mkfs device minor fs_type

    Makes a file system <fs_type> on partition <minor>, destroying all data
        that resides on that partition. <fs_type> must be one of "ext2",
        "fat32", "fat16", "linux-swap" or "reiserfs" (if libreiserfs is
        installed)

    CLI Example::

        salt '*' partition.mkfs 2 fat32
    '''
    cmd = 'parted -m -s {0} mklabel {1}'.format(device, label_type)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def mklabel(device, label_type):
    '''
    partition.mklabel device label_type

    Create a new disklabel (partition table) of label_type.
    Type should be one of "aix", "amiga", "bsd", "dvh", "gpt", "loop", "mac",
        "msdos", "pc98", or "sun".

    CLI Example::

        salt '*' partition.mklabel /dev/sda msdos
    '''
    cmd = 'parted -m -s {0} mklabel {1}'.format(device, label_type)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def mkpart(device, part_type, fs_type, start, end):
    '''
    partition.mkpart device part_type fs_type start end

    Make a part_type partition for filesystem fs_type, beginning at start and
        ending at end (by default in megabytes).  part_type should be one of
        "primary", "logical", or "extended".

    CLI Example::

        salt '*' partition.mkpart /dev/sda primary fat32 0 639
    '''
    cmd = 'parted -m -s {0} mkpart {1} {2} {3} {4}'.format(device, part_type, fs_type, start, end)
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

    CLI Example::

        salt '*' partition.mkpartfs /dev/sda logical ext2 440 670
    '''
    cmd = 'parted -m -s {0} mkpart {1} {2} {3} {4}'.format(device, part_type, fs_type, start, end)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def name(device, partition, name):
    '''
    partition.name device partition name

    Set the name of partition to name. This option works only on Mac, PC98,
        and GPT disklabels. The name can be placed in quotes, if necessary.

    CLI Example::

        salt '*' partition.name /dev/sda 1 'My Documents'
    '''
    cmd = 'parted -m -s {0} name {1} {2}'.format(device, partition, name)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def rescue(device, start, end):
    '''
    partition.rescue device start end

    Rescue a lost partition that was located somewhere between start and end.
        If a partition is found, parted will ask if you want to create an
        entry for it in the partition table.

    CLI Example::

        salt '*' partition.rescue /dev/sda 0 8056
    '''
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

    CLI Example::

        salt '*' partition.resize /dev/sda 3 200 850
    '''
    cmd = 'parted -m -s {0} resize {1} {2} {3}'.format(device, minor, start, end)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def rm(device, minor):
    '''
    partition.rm device minor

    Removes the partition with number <minor>.

    CLI Example::

        salt '*' partition.rm /dev/sda 5
    '''
    cmd = 'parted -m -s {0} rm {1}'.format(device, minor)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def set(device, minor, flag, state):
    '''
    partition.set device  minor flag state

    Changes a flag on the partition with number <minor>. A flag can be either
        "on" or "off". Some or all of these flags will be available, depending
        on what disk label you are using.

    CLI Example::

        salt '*' partition.set /dev/sda 1 boot on
    '''
    cmd = 'parted -m -s {0} set {1} {2} {3}'.format(device, minor, flag, state)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def toggle(device, partition, flag):
    '''
    partition.toggle device partition flag

    Toggle the state of <flag> on <partition>

    CLI Example::

        salt '*' partition.name /dev/sda 1 boot
    '''
    cmd = 'parted -m -s {0} toggle {1} {2} {3}'.format(device, partition, flag)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out

