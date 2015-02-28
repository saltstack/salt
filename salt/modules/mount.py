# -*- coding: utf-8 -*-
'''
Salt module to manage unix mounts and the fstab file
'''

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils
from salt._compat import string_types
from salt.utils import which as _which
from salt.exceptions import CommandNotFoundError, CommandExecutionError

# Set up logger
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'mount'


def __virtual__():
    '''
    Only load on POSIX-like systems
    '''
    # Disable on Windows, a specific file module exists:
    if salt.utils.is_windows():
        return False
    return True


def _list_mounts():
    ret = {}
    for line in __salt__['cmd.run_stdout']('mount -l').split('\n'):
        comps = re.sub(r"\s+", " ", line).split()
        ret[comps[2]] = comps[0]
    return ret


def _active_mountinfo(ret):
    _list = _list_mounts()
    filename = '/proc/self/mountinfo'
    if not os.access(filename, os.R_OK):
        msg = 'File not readable {0}'
        raise CommandExecutionError(msg.format(filename))

    blkid_info = __salt__['disk.blkid']()

    with salt.utils.fopen(filename) as ifile:
        for line in ifile:
            comps = line.split()
            device = comps[2].split(':')
            # each line can have any number of
            # optional parameters, we use the
            # location of the seperator field to
            # determine the location of the elements
            # after it.
            _sep = comps.index('-')
            device_name = comps[_sep + 2]
            device_uuid = None
            device_label = None
            if device_name:
                device_uuid = blkid_info.get(device_name, {}).get('UUID')
                device_uuid = device_uuid and device_uuid.lower()
                device_label = blkid_info.get(device_name, {}).get('LABEL')
            ret[comps[4]] = {'mountid': comps[0],
                             'parentid': comps[1],
                             'major': device[0],
                             'minor': device[1],
                             'root': comps[3],
                             'opts': comps[5].split(','),
                             'fstype': comps[_sep + 1],
                             'device': device_name,
                             'alt_device': _list.get(comps[4], None),
                             'superopts': comps[_sep + 3].split(','),
                             'device_uuid': device_uuid,
                             'device_label': device_label}
    return ret


def _active_mounts(ret):
    '''
    List active mounts on Linux systems
    '''
    _list = _list_mounts()
    filename = '/proc/self/mounts'
    if not os.access(filename, os.R_OK):
        msg = 'File not readable {0}'
        raise CommandExecutionError(msg.format(filename))

    with salt.utils.fopen(filename) as ifile:
        for line in ifile:
            comps = line.split()
            ret[comps[1]] = {'device': comps[0],
                             'alt_device': _list.get(comps[1], None),
                             'fstype': comps[2],
                             'opts': comps[3].split(',')}
    return ret


def _active_mounts_freebsd(ret):
    '''
    List active mounts on FreeBSD systems
    '''
    for line in __salt__['cmd.run_stdout']('mount -p').split('\n'):
        comps = re.sub(r"\s+", " ", line).split()
        ret[comps[1]] = {'device': comps[0],
                         'fstype': comps[2],
                         'opts': comps[3].split(',')}
    return ret


def _active_mounts_solaris(ret):
    '''
    List active mounts on Solaris systems
    '''
    for line in __salt__['cmd.run_stdout']('mount -v').split('\n'):
        comps = re.sub(r"\s+", " ", line).split()
        ret[comps[2]] = {'device': comps[0],
                         'fstype': comps[4],
                         'opts': comps[5].split('/')}
    return ret


def active(extended=False):
    '''
    List the active mounts.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.active
    '''
    ret = {}
    if __grains__['os'] == 'FreeBSD':
        _active_mounts_freebsd(ret)
    elif __grains__['os'] == 'Solaris':
        _active_mounts_solaris(ret)
    else:
        if extended:
            try:
                _active_mountinfo(ret)
            except CommandExecutionError:
                _active_mounts(ret)
        else:
            _active_mounts(ret)
    return ret


def fstab(config='/etc/fstab'):
    '''
    List the contents of the fstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.fstab
    '''
    ret = {}
    if not os.path.isfile(config):
        return ret
    with salt.utils.fopen(config) as ifile:
        for line in ifile:
            if line.startswith('#'):
                # Commented
                continue
            if not line.strip():
                # Blank line
                continue
            comps = line.split()
            if len(comps) != 6:
                # Invalid entry
                continue
            ret[comps[1]] = {'device': comps[0],
                             'fstype': comps[2],
                             'opts': comps[3].split(','),
                             'dump': comps[4],
                             'pass': comps[5]}
    return ret


def rm_fstab(name, config='/etc/fstab'):
    '''
    Remove the mount point from the fstab

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_fstab /mnt/foo
    '''
    contents = fstab(config)
    if name not in contents:
        return True
    # The entry is present, get rid of it
    lines = []
    try:
        with salt.utils.fopen(config, 'r') as ifile:
            for line in ifile:
                if line.startswith('#'):
                    # Commented
                    lines.append(line)
                    continue
                if not line.strip():
                    # Blank line
                    lines.append(line)
                    continue
                comps = line.split()
                if len(comps) != 6:
                    # Invalid entry
                    lines.append(line)
                    continue
                comps = line.split()
                if comps[1] == name:
                    continue
                lines.append(line)
    except (IOError, OSError) as exc:
        msg = "Couldn't read from {0}: {1}"
        raise CommandExecutionError(msg.format(config, str(exc)))

    try:
        with salt.utils.fopen(config, 'w+') as ofile:
            ofile.writelines(lines)
    except (IOError, OSError) as exc:
        msg = "Couldn't write to {0}: {1}"
        raise CommandExecutionError(msg.format(config, str(exc)))
    return True


def set_fstab(
        name,
        device,
        fstype,
        opts='defaults',
        dump=0,
        pass_num=0,
        config='/etc/fstab',
        test=False,
        **kwargs):
    '''
    Verify that this mount is represented in the fstab, change the mount
    to match the data passed, or add the mount if it is not present.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_fstab /mnt/foo /dev/sdz1 ext4
    '''
    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ','.join(opts)
    lines = []
    change = False
    present = False

    if not os.path.isfile(config):
        raise CommandExecutionError('Bad config file "{0}"'.format(config))

    try:
        with salt.utils.fopen(config, 'r') as ifile:
            for line in ifile:
                if line.startswith('#'):
                    # Commented
                    lines.append(line)
                    continue
                if not line.strip():
                    # Blank line
                    lines.append(line)
                    continue
                comps = line.split()
                if len(comps) != 6:
                    # Invalid entry
                    lines.append(line)
                    continue
                if comps[1] == name or comps[0] == device:
                    # check to see if there are changes
                    # and fix them if there are any
                    present = True
                    if comps[0] != device:
                        change = True
                        comps[0] = device
                    if comps[1] != name:
                        change = True
                        comps[1] = name
                    if comps[2] != fstype:
                        change = True
                        comps[2] = fstype
                    if comps[3] != opts:
                        change = True
                        comps[3] = opts
                    if comps[4] != str(dump):
                        change = True
                        comps[4] = str(dump)
                    if comps[5] != str(pass_num):
                        change = True
                        comps[5] = str(pass_num)
                    if change:
                        log.debug(
                            'fstab entry for mount point {0} needs to be '
                            'updated'.format(name)
                        )
                        newline = (
                            '{0}\t\t{1}\t{2}\t{3}\t{4} {5}\n'.format(
                                device, name, fstype, opts, dump, pass_num
                            )
                        )
                        lines.append(newline)
                else:
                    lines.append(line)
    except (IOError, OSError) as exc:
        msg = 'Couldn\'t read from {0}: {1}'
        raise CommandExecutionError(msg.format(config, str(exc)))

    if change:
        if not salt.utils.test_mode(test=test, **kwargs):
            try:
                with salt.utils.fopen(config, 'w+') as ofile:
                    # The line was changed, commit it!
                    ofile.writelines(lines)
            except (IOError, OSError):
                msg = 'File not writable {0}'
                raise CommandExecutionError(msg.format(config))

        return 'change'

    if not change:
        if present:
            # The right entry is already here
            return 'present'
        else:
            if not salt.utils.test_mode(test=test, **kwargs):
                # The entry is new, add it to the end of the fstab
                newline = '{0}\t\t{1}\t{2}\t{3}\t{4} {5}\n'.format(device,
                                                                   name,
                                                                   fstype,
                                                                   opts,
                                                                   dump,
                                                                   pass_num)
                lines.append(newline)
                try:
                    with salt.utils.fopen(config, 'w+') as ofile:
                        # The line was changed, commit it!
                        ofile.writelines(lines)
                except (IOError, OSError):
                    raise CommandExecutionError(
                        'File not writable {0}'.format(
                            config
                        )
                    )
    return 'new'


def mount(name, device, mkmnt=False, fstype='', opts='defaults'):
    '''
    Mount a device

    CLI Example:

    .. code-block:: bash

        salt '*' mount.mount /mnt/foo /dev/sdz1 True
    '''
    if isinstance(opts, string_types):
        opts = opts.split(',')
    if not os.path.exists(name) and mkmnt:
        os.makedirs(name)
    lopts = ','.join(opts)
    args = '-o {0}'.format(lopts)
    if fstype:
        args += ' -t {0}'.format(fstype)
    cmd = 'mount {0} {1} {2} '.format(args, device, name)
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode']:
        return out['stderr']
    return True


def remount(name, device, mkmnt=False, fstype='', opts='defaults'):
    '''
    Attempt to remount a device, if the device is not already mounted, mount
    is called

    CLI Example:

    .. code-block:: bash

        salt '*' mount.remount /mnt/foo /dev/sdz1 True
    '''
    if isinstance(opts, string_types):
        opts = opts.split(',')
    mnts = active()
    if name in mnts:
        # The mount point is mounted, attempt to remount it with the given data
        if 'remount' not in opts:
            opts.append('remount')
        lopts = ','.join(opts)
        args = '-o {0}'.format(lopts)
        if fstype:
            args += ' -t {0}'.format(fstype)
        cmd = 'mount {0} {1} {2} '.format(args, device, name)
        out = __salt__['cmd.run_all'](cmd, python_shell=False)
        if out['retcode']:
            return out['stderr']
        return True
    # Mount a filesystem that isn't already
    return mount(name, device, mkmnt, fstype, opts)


def umount(name):
    '''
    Attempt to unmount a device by specifying the directory it is mounted on

    CLI Example:

    .. code-block:: bash

        salt '*' mount.umount /mnt/foo
    '''
    mnts = active()
    if name not in mnts:
        return "{0} does not have anything mounted".format(name)

    cmd = 'umount {0}'.format(name)
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode']:
        return out['stderr']
    return True


def is_fuse_exec(cmd):
    '''
    Returns true if the command passed is a fuse mountable application.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.is_fuse_exec sshfs
    '''
    cmd_path = _which(cmd)

    # No point in running ldd on a command that doesn't exist
    if not cmd_path:
        return False
    elif not _which('ldd'):
        raise CommandNotFoundError('ldd')

    out = __salt__['cmd.run']('ldd {0}'.format(cmd_path), python_shell=False)
    return 'libfuse' in out


def swaps():
    '''
    Return a dict containing information on active swap

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swaps
    '''
    ret = {}
    with salt.utils.fopen('/proc/swaps') as fp_:
        for line in fp_:
            if line.startswith('Filename'):
                continue
            comps = line.split()
            ret[comps[0]] = {'type': comps[1],
                             'size': comps[2],
                             'used': comps[3],
                             'priority': comps[4]}
    return ret


def swapon(name, priority=None):
    '''
    Activate a swap disk

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swapon /root/swapfile
    '''
    ret = {}
    on_ = swaps()
    if name in on_:
        ret['stats'] = on_[name]
        ret['new'] = False
        return ret
    cmd = 'swapon {0}'.format(name)
    if priority:
        cmd += ' -p {0}'.format(priority)
    __salt__['cmd.run'](cmd, python_shell=False)
    on_ = swaps()
    if name in on_:
        ret['stats'] = on_[name]
        ret['new'] = True
        return ret
    return ret


def swapoff(name):
    '''
    Deactivate a named swap mount

    CLI Example:

    .. code-block:: bash

        salt '*' mount.swapoff /root/swapfile
    '''
    on_ = swaps()
    if name in on_:
        __salt__['cmd.run']('swapoff {0}'.format(name), python_shell=False)
        on_ = swaps()
        if name in on_:
            return False
        return True
    return None


def is_mounted(name):
    '''
    .. versionadded:: 2014.7.0

    Provide information if the path is mounted

    CLI Example:

    .. code-block:: bash

        salt '*' mount.is_mounted /mnt/share
    '''
    active_ = active()
    if name in active_:
        return True
    else:
        return False
