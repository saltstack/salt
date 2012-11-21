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
    return 'extfs'


def tune(device, **kwargs):
    '''
    Set attributes for the specified device (using tune2fs)

    CLI Example::

        salt '*' extfs.tune /dev/sda1 force=True label=wildstallyns opts='acl,noexec'

    Valid options are::

        max: max mount count
        count: mount count
        error: error behavior
        extended_opts: extended options (comma separated)
        force: force, even if there are errors (set to True)
        group: group name or gid that can use the reserved blocks
        interval: interval between checks
        journal: add a journal to the file system (set to True)
        journal_opts: options for the fs journal (comma separated)
        label: label to apply to the file system
        reserved: reserved blocks percentage
        last_dir: last mounted directory
        opts: mount options (comma separated)
        feature: set or clear a feature (comma separated)
        mmp_check: mmp check interval
        reserved: reserved blocks count
        quota_opts: quota options (comma separated)
        time: time last checked
        user: user or uid who can use the reserved blocks
        uuid: set the UUID for the file system

        see man 8 tune2fs for a more complete description of these options
    '''
    kwarg_map = {'max': 'c',
                 'count': 'C',
                 'error': 'e',
                 'extended_opts': 'E',
                 'force': 'f',
                 'group': 'g',
                 'interval': 'i',
                 'journal': 'j',
                 'journal_opts': 'J',
                 'label': 'L',
                 'reserved': 'm',
                 'last_dir': 'M',
                 'opts': 'o',
                 'feature': 'O',
                 'mmp_check': 'p',
                 'reserved': 'r',
                 'quota_opts': 'Q',
                 'time': 'T',
                 'user': 'u',
                 'uuid': 'U'}
    opts = ''
    for key in kwargs.keys():
        opt = kwarg_map[key]
        if kwargs[key] == 'True':
            opts += '-{0} '.format(opt)
        else:
            opts += '-{0} {1} '.format(opt, kwargs[key])
    cmd = 'tune2fs {0}{1}'.format(opts, device)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def attributes(device, args=None):
    '''
    Return attributes from dumpe2fs for a specified device

    CLI Example::

        salt '*' extfs.attributes /dev/sda1
    '''
    fsdump = dump(device, args)
    return fsdump['attributes']


def blocks(device, args=None):
    '''
    Return block and inode info from dumpe2fs for a specified device

    CLI Example::

        salt '*' extfs.blocks /dev/sda1
    '''
    fsdump = dump(device, args)
    return fsdump['blocks']


def dump(device, args=None):
    '''
    Return all contents of dumpe2fs for a specified device

    CLI Example::

        salt '*' extfs.dump /dev/sda1
    '''
    cmd = 'dumpe2fs {0}'.format(device)
    if args:
        cmd = cmd + ' -' + args
    ret = {'attributes': {}, 'blocks': {}}
    out = __salt__['cmd.run'](cmd).splitlines()
    mode = 'opts'
    blkgrp = None
    group = None
    for line in out:
        if not line:
            continue
        if line.startswith('dumpe2fs'):
            continue
        if mode == 'opts':
            line = line.replace('\t', ' ')
            comps = line.split(': ')
            if line.startswith('Filesystem features'):
                ret['attributes'][comps[0]] = comps[1].split()
            elif line.startswith('Group'):
                mode = 'blocks'
            else:
                ret['attributes'][comps[0]] = comps[1].strip()

        if mode == 'blocks':
            if line.startswith('Group'):
                line = line.replace(':', '')
                line = line.replace('(', '')
                line = line.replace(')', '')
                line = line.replace('[', '')
                line = line.replace(']', '')
                comps = line.split()
                blkgrp = comps[1]
                group = 'Group {0}'.format(blkgrp)
                ret['blocks'][group] = {}
                ret['blocks'][group]['group'] = blkgrp
                ret['blocks'][group]['range'] = comps[3]
                # TODO: comps[4:], which may look one one of the following:
                #     ITABLE_ZEROED
                #     INODE_UNINIT, ITABLE_ZEROED
                # Does anyone know what to call these?
                ret['blocks'][group]['extra'] = []
            elif 'Free blocks:' in line:
                comps = line.split(': ')
                blocks = comps[1].split(', ')
                ret['blocks'][group]['free blocks'] = blocks
            elif 'Free inodes:' in line:
                comps = line.split(': ')
                inodes = comps[1].split(', ')
                ret['blocks'][group]['free inodes'] = inodes
            else:
                line = line.strip()
                ret['blocks'][group]['extra'].append(line)
    return ret

