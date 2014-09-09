# -*- coding: utf-8 -*-
'''
Module for gathering disk information
'''

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.utils

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return True


def _clean_flags(args, caller):
    '''
    Sanitize flags passed into df
    '''
    flags = ''
    if args is None:
        return flags
    allowed = ('a', 'B', 'h', 'H', 'i', 'k', 'l', 'P', 't', 'T', 'x', 'v')
    for flag in args:
        if flag in allowed:
            flags += flag
        else:
            raise CommandExecutionError(
                'Invalid flag passed to {0}'.format(caller)
            )
    return flags


def usage(args=None):
    '''
    Return usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    '''
    flags = _clean_flags(args, 'disk.usage')
    if not os.path.isfile('/etc/mtab') and __grains__['kernel'] == 'Linux':
        log.warn('df cannot run without /etc/mtab')
        if __grains__.get('virtual_subtype') == 'LXC':
            log.warn('df command failed and LXC detected. If you are running '
                     'a Docker container, consider linking /proc/mounts to '
                     '/etc/mtab or consider running Docker with -privileged')
        return {}
    if __grains__['kernel'] == 'Linux':
        cmd = 'df -P'
    elif __grains__['kernel'] == 'OpenBSD':
        cmd = 'df -kP'
    else:
        cmd = 'df'
    if flags:
        cmd += ' -{0}'.format(flags)
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        while not comps[1].isdigit():
            comps[0] = '{0} {1}'.format(comps[0], comps[1])
            comps.pop(1)
        try:
            if __grains__['kernel'] == 'Darwin':
                ret[comps[8]] = {
                        'filesystem': comps[0],
                        '512-blocks': comps[1],
                        'used': comps[2],
                        'available': comps[3],
                        'capacity': comps[4],
                        'iused': comps[5],
                        'ifree': comps[6],
                        '%iused': comps[7],
                }
            else:
                ret[comps[5]] = {
                        'filesystem': comps[0],
                        '1K-blocks': comps[1],
                        'used': comps[2],
                        'available': comps[3],
                        'capacity': comps[4],
                }
        except IndexError:
            log.warn('Problem parsing disk usage information')
            ret = {}
    return ret


def inodeusage(args=None):
    '''
    Return inode usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.inodeusage
    '''
    flags = _clean_flags(args, 'disk.inodeusage')
    cmd = 'df -i'
    if flags:
        cmd += ' -{0}'.format(flags)
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        # Don't choke on empty lines
        if not comps:
            continue

        try:
            if __grains__['kernel'] == 'OpenBSD':
                ret[comps[8]] = {
                    'inodes': int(comps[5]) + int(comps[6]),
                    'used': comps[5],
                    'free': comps[6],
                    'use': comps[7],
                    'filesystem': comps[0],
                }
            else:
                ret[comps[5]] = {
                    'inodes': comps[1],
                    'used': comps[2],
                    'free': comps[3],
                    'use': comps[4],
                    'filesystem': comps[0],
                }
        except (IndexError, ValueError):
            log.warn('Problem parsing inode usage information')
            ret = {}
    return ret


def percent(args=None):
    '''
    Return partition information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.percent /var
    '''
    if __grains__['kernel'] == 'Linux':
        cmd = 'df -P'
    elif __grains__['kernel'] == 'OpenBSD':
        cmd = 'df -kP'
    else:
        cmd = 'df'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        while not comps[1].isdigit():
            comps[0] = '{0} {1}'.format(comps[0], comps[1])
            comps.pop(1)
        try:
            if __grains__['kernel'] == 'Darwin':
                ret[comps[8]] = comps[4]
            else:
                ret[comps[5]] = comps[4]
        except IndexError:
            log.warn('Problem parsing disk usage information')
            ret = {}
    if args:
        return ret[args]
    else:
        return ret


def blkid(device=None):
    '''
    Return block device attributes: UUID, LABEL, etc.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.blkid
        salt '*' disk.blkid /dev/sda
    '''
    args = ""
    if device:
        args = " " + device

    ret = {}
    for line in __salt__['cmd.run_stdout']('blkid' + args).split('\n'):
        comps = line.split()
        device = comps[0][:-1]
        info = {}
        device_attributes = re.split(('\"*\"'), line.partition(' ')[2])
        for key, value in zip(*[iter(device_attributes)]*2):
            key = key.strip('=').strip(' ')
            info[key] = value.strip('"')
        ret[device] = info

    return ret
