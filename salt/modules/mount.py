# -*- coding: utf-8 -*-
'''
Salt module to manage unix mounts and the fstab file
'''
from __future__ import absolute_import

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils
from salt.ext.six import string_types
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
    if __grains__['os'] in ['MacOS', 'Darwin']:
        mounts = __salt__['cmd.run_stdout']('mount')
    else:
        mounts = __salt__['cmd.run_stdout']('mount -l')

    for line in mounts.split('\n'):
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
            if device_name:
                device_uuid = blkid_info.get(device_name, {}).get('UUID')
                device_uuid = device_uuid and device_uuid.lower()
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
                             'device_uuid': device_uuid}
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


def _active_mounts_openbsd(ret):
    '''
    List active mounts on OpenBSD systems
    '''
    for line in __salt__['cmd.run_stdout']('mount -v').split('\n'):
        comps = re.sub(r"\s+", " ", line).split()
        nod = __salt__['cmd.run_stdout']('ls -l {0}'.format(comps[0]))
        nod = ' '.join(nod.split()).split(" ")
        parens = re.findall(r'\((.*?)\)', line, re.DOTALL)
        ret[comps[3]] = {'device': comps[0],
                         'fstype': comps[5],
                         'opts': parens[1].split(", "),
                         'major': str(nod[4].strip(",")),
                         'minor': str(nod[5]),
                         'device_uuid': parens[0]}
    return ret


def _active_mounts_darwin(ret):
    '''
    List active mounts on Mac OS systems
    '''
    for line in __salt__['cmd.run_stdout']('mount').split('\n'):
        comps = re.sub(r"\s+", " ", line).split()
        parens = re.findall(r'\((.*?)\)', line, re.DOTALL)[0].split(", ")
        ret[comps[2]] = {'device': comps[0],
                         'fstype': parens[0],
                         'opts': parens[1:]}
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
    elif __grains__['os'] == 'OpenBSD':
        _active_mounts_openbsd(ret)
    elif __grains__['os'] in ['MacOS', 'Darwin']:
        _active_mounts_darwin(ret)
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


def rm_fstab(name, device, config='/etc/fstab'):
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
                if device:
                    if comps[1] == name and comps[0] == device:
                        continue
                else:
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
                if comps[1] == name and comps[0] == device:
                    # check to see if there are changes
                    # and fix them if there are any
                    present = True
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


def rm_automaster(name, device, config='/etc/auto_salt'):
    '''
    Remove the mount point from the auto_master

    CLI Example:

    .. code-block:: bash

        salt '*' mount.rm_automaster /mnt/foo
    '''
    contents = automaster(config)
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
                if len(comps) != 3:
                    # Invalid entry
                    lines.append(line)
                    continue

                comps = line.split()
                prefix = "/.."
                name_chk = comps[0].replace(prefix, "")
                device_fmt = comps[2].split(":")

                if device:
                    if name_chk == name and device_fmt[1] == device:
                        continue
                else:
                    if name_chk == name:
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

    # Update automount
    __salt__['cmd.run']('automount -cv')
    return True


def set_automaster(
        name,
        device,
        fstype,
        opts='',
        config='/etc/auto_salt',
        test=False,
        **kwargs):
    '''
    Verify that this mount is represented in the auto_salt, change the mount
    to match the data passed, or add the mount if it is not present.

    CLI Example:

    .. code-block:: bash

        salt '*' mount.set_automaster /mnt/foo /dev/sdz1 ext4
    '''
    # Fix the opts type if it is a list
    if isinstance(opts, list):
        opts = ','.join(opts)
    lines = []
    change = False
    present = False
    automaster_file = "/etc/auto_master"

    if not os.path.isfile(config):
        __salt__['file.touch'](config)
        __salt__['file.append'](automaster_file, "/-\t\t\t{0}".format(config))

    name = "/..{0}".format(name)
    device_fmt = "{0}:{1}".format(fstype, device)
    type_opts = "-fstype={0},{1}".format(fstype, opts)

    if fstype == 'smbfs':
        device_fmt = device_fmt.replace(fstype, "")

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
                if len(comps) != 3:
                    # Invalid entry
                    lines.append(line)
                    continue
                if comps[0] == name or comps[2] == device_fmt:
                    # check to see if there are changes
                    # and fix them if there are any
                    present = True
                    if comps[0] != name:
                        change = True
                        comps[0] = name
                    if comps[1] != type_opts:
                        change = True
                        comps[1] = type_opts
                    if comps[2] != device_fmt:
                        change = True
                        comps[2] = device_fmt
                    if change:
                        log.debug(
                            'auto_master entry for mount point {0} needs to be '
                            'updated'.format(name)
                        )
                        newline = (
                            '{0}\t{1}\t{2}\n'.format(
                                name, type_opts, device_fmt)
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
                newline = (
                    '{0}\t{1}\t{2}\n'.format(
                        name, type_opts, device_fmt)
                )
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


def automaster(config='/etc/auto_salt'):
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
            if len(comps) != 3:
                # Invalid entry
                continue

            prefix = "/.."
            name = comps[0].replace(prefix, "")
            device_fmt = comps[2].split(":")
            opts = comps[1].split(',')

            ret[name] = {'device': device_fmt[1],
                         'fstype': opts[0],
                         'opts': opts[1:]}
    return ret


def mount(name, device, mkmnt=False, fstype='', opts='defaults', user=None):
    '''
    Mount a device

    CLI Example:

    .. code-block:: bash

        salt '*' mount.mount /mnt/foo /dev/sdz1 True
    '''

    # Darwin doesn't expect defaults when mounting without other options
    if 'defaults' in opts and __grains__['os'] in ['MacOS', 'Darwin']:
        opts = None

    if isinstance(opts, string_types):
        opts = opts.split(',')

    if not os.path.exists(name) and mkmnt:
        __salt__['file.mkdir'](name=name, user=user)

    args = ''
    if opts is not None:
        lopts = ','.join(opts)
        args = '-o {0}'.format(lopts)
    if fstype:
        args += ' -t {0}'.format(fstype)
    cmd = 'mount {0} {1} {2} '.format(args, device, name)
    out = __salt__['cmd.run_all'](cmd, runas=user, python_shell=False)
    if out['retcode']:
        return out['stderr']
    return True


def remount(name, device, mkmnt=False, fstype='', opts='defaults', user=None):
    '''
    Attempt to remount a device, if the device is not already mounted, mount
    is called

    CLI Example:

    .. code-block:: bash

        salt '*' mount.remount /mnt/foo /dev/sdz1 True
    '''
    force_mount = False
    if __grains__['os'] in ['MacOS', 'Darwin']:
        if opts == 'defaults':
            opts = 'noowners'
        if fstype == 'smbfs':
            force_mount = True

    if isinstance(opts, string_types):
        opts = opts.split(',')
    mnts = active()
    if name in mnts:
        # The mount point is mounted, attempt to remount it with the given data
        if 'remount' not in opts and __grains__['os'] not in ['OpenBSD', 'MacOS', 'Darwin']:
            opts.append('remount')
        if force_mount:
            # We need to force the mount but first we should unmount
            umount(name, device, user=user)
        lopts = ','.join(opts)
        args = '-o {0}'.format(lopts)
        if fstype:
            args += ' -t {0}'.format(fstype)
        if __grains__['os'] not in ['OpenBSD', 'MacOS', 'Darwin'] or force_mount:
            cmd = 'mount {0} {1} {2} '.format(args, device, name)
        else:
            cmd = 'mount -u {0} {1} {2} '.format(args, device, name)
        out = __salt__['cmd.run_all'](cmd, runas=user, python_shell=False)
        if out['retcode']:
            return out['stderr']
        return True
    # Mount a filesystem that isn't already
    return mount(name, device, mkmnt, fstype, opts, user=user)


def umount(name, device=None, user=None):
    '''
    Attempt to unmount a device by specifying the directory it is mounted on

    CLI Example:

    .. code-block:: bash

        salt '*' mount.umount /mnt/foo

        .. versionadded:: Lithium

        salt '*' mount.umount /mnt/foo /dev/xvdc1
    '''
    mnts = active()
    if name not in mnts:
        return "{0} does not have anything mounted".format(name)

    if not device:
        cmd = 'umount {0}'.format(name)
    else:
        cmd = 'umount {0}'.format(device)
    out = __salt__['cmd.run_all'](cmd, runas=user, python_shell=False)
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
    if __grains__['os'] != 'OpenBSD':
        with salt.utils.fopen('/proc/swaps') as fp_:
            for line in fp_:
                if line.startswith('Filename'):
                    continue
                comps = line.split()
                ret[comps[0]] = {'type': comps[1],
                                 'size': comps[2],
                                 'used': comps[3],
                                 'priority': comps[4]}
    else:
        for line in __salt__['cmd.run_stdout']('swapctl -kl').splitlines():
            if line.startswith(('Device', 'Total')):
                continue
            swap_type = "file"
            comps = line.split()
            if comps[0].startswith('/dev/'):
                swap_type = "partition"
            ret[comps[0]] = {'type': swap_type,
                             'size': comps[1],
                             'used': comps[2],
                             'priority': comps[5]}
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
        if __grains__['os'] != 'OpenBSD':
            __salt__['cmd.run']('swapoff {0}'.format(name), python_shell=False)
        else:
            __salt__['cmd.run']('swapctl -d {0}'.format(name),
                                python_shell=False)
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
