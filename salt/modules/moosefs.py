# -*- coding: utf-8 -*-
'''
Module for gathering and managing information about MooseFS
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only load if the mfs commands are installed
    '''
    if salt.utils.which('mfsgetgoal'):
        return 'moosefs'
    return False


def dirinfo(path, opts=None):
    '''
    Return information on a directory located on the Moose

    CLI Example:

    .. code-block:: bash

        salt '*' moosefs.dirinfo /path/to/dir/ [-[n][h|H]]
    '''
    cmd = 'mfsdirinfo'
    ret = {}
    if opts:
        cmd += ' -' + opts
    cmd += ' ' + path
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    output = out['stdout'].splitlines()
    for line in output:
        if not line:
            continue
        comps = line.split(':')
        ret[comps[0].strip()] = comps[1].strip()
    return ret


def fileinfo(path):
    '''
    Return information on a file located on the Moose

    CLI Example:

    .. code-block:: bash

        salt '*' moosefs.fileinfo /path/to/dir/
    '''
    cmd = 'mfsfileinfo ' + path
    ret = {}
    chunknum = ''
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    output = out['stdout'].splitlines()
    for line in output:
        if not line:
            continue
        if '/' in line:
            comps = line.split('/')

            chunknum = comps[0].strip().split(':')
            meta = comps[1].strip().split(' ')

            chunk = chunknum[0].replace('chunk ', '')
            loc = chunknum[1].strip()
            id_ = meta[0].replace('(id:', '')
            ver = meta[1].replace(')', '').replace('ver:', '')

            ret[chunknum[0]] = {
                'chunk': chunk,
                'loc': loc,
                'id': id_,
                'ver': ver,
            }
        if 'copy' in line:
            copyinfo = line.strip().split(':')
            ret[chunknum[0]][copyinfo[0]] = {
                'copy': copyinfo[0].replace('copy ', ''),
                'ip': copyinfo[1].strip(),
                'port': copyinfo[2],
            }
    return ret


def mounts():
    '''
    Return a list of current MooseFS mounts

    CLI Example:

    .. code-block:: bash

        salt '*' moosefs.mounts
    '''
    cmd = 'mount'
    ret = {}
    out = __salt__['cmd.run_all'](cmd)

    output = out['stdout'].splitlines()
    for line in output:
        if not line:
            continue
        if 'fuse.mfs' in line:
            comps = line.split(' ')
            info1 = comps[0].split(':')
            info2 = info1[1].split('/')
            ret[comps[2]] = {
                'remote': {
                    'master': info1[0],
                    'port': info2[0],
                    'subfolder': '/' + info2[1],
                },
                'local': comps[2],
                'options': (comps[5].replace('(', '').replace(')', '')
                            .split(',')),
            }
    return ret


def getgoal(path, opts=None):
    '''
    Return goal(s) for a file or directory

    CLI Example:

    .. code-block:: bash

        salt '*' moosefs.getgoal /path/to/file [-[n][h|H]]
        salt '*' moosefs.getgoal /path/to/dir/ [-[n][h|H][r]]
    '''
    cmd = 'mfsgetgoal'
    ret = {}
    if opts:
        cmd += ' -' + opts
    else:
        opts = ''
    cmd += ' ' + path
    out = __salt__['cmd.run_all'](cmd, python_shell=False)

    output = out['stdout'].splitlines()
    if 'r' not in opts:
        goal = output[0].split(': ')
        ret = {
            'goal': goal[1],
        }
    else:
        for line in output:
            if not line:
                continue
            if path in line:
                continue
            comps = line.split()
            keytext = comps[0] + ' with goal'
            if keytext not in ret:
                ret[keytext] = {}
            ret[keytext][comps[3]] = comps[5]
    return ret
