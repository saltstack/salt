'''
Module for gathering disk information
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
    return 'disk'

def usage(args=None):
    '''
    Return usage information for volumes mounted on this minion

    CLI Example::

        salt '*' disk.usage
    '''
    if __grains__['kernel'] == 'Linux':
        cmd = 'df -P'
    elif __grains__['kernel'] == 'OpenBSD':
        cmd = 'df -kP'
    else:
        cmd = 'df'
    if args:
        cmd = cmd + ' -' + args
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        try:
            ret[comps[5]] = {
                'filesystem': comps[0],
                '1K-blocks':  comps[1],
                'used':       comps[2],
                'available':  comps[3],
                'capacity':   comps[4],
            }
        except IndexError:
            log.warn("Problem parsing disk usage information")
            ret = {}
    return ret

def inodeusage(args=None):
    '''
    Return inode usage information for volumes mounted on this minion

    CLI Example::

        salt '*' disk.inodeusage
    '''
    cmd = 'df -i'
    if args is not None:
        cmd = cmd + ' -' + args
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
                    'used':   comps[5],
                    'free':   comps[6],
                    'use':    comps[7],
                    'filesystem': comps[0],
                }
            else:
                ret[comps[5]] = {
                    'inodes': comps[1],
                    'used':   comps[2],
                    'free':   comps[3],
                    'use':    comps[4],
                    'filesystem': comps[0],
                }
        except (IndexError, ValueError):
            log.warn("Problem parsing inode usage information")
            ret = {}
    return ret
