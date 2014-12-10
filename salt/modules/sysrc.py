# -*- coding: utf-8 -*-
'''
sysrc module for FreeBSD
'''
from __future__ import absolute_import

import salt.utils
from salt.exceptions import CommandExecutionError


def __virtual__():
    '''
    Only runs if sysrc exists
    '''
    return __salt__['cmd.has_exec']('sysrc')


def get(**kwargs):
    '''
    Return system rc configuration variables

    CLI Example:

     .. code-block:: bash

         salt '*' sysrc.get includeDefaults=True
    '''

    cmd = 'sysrc -v'

    if 'name' in kwargs:
        cmd += ' '+kwargs['name']
    elif kwargs.get('includeDefaults', False):
        cmd += ' -A'
    else:
        cmd += ' -a'

    if 'file' in kwargs:
        cmd += ' -f '+kwargs['file']

    if 'jail' in kwargs:
        cmd += ' -j '+kwargs['jail']

    sysrcs = __salt__['cmd.run'](cmd, python_shell=False)
    if "sysrc: unknown variable" in sysrcs:
        return None

    ret = {}
    for sysrc in sysrcs.split("\n"):
        rcfile = sysrc.split(': ')[0]
        var = sysrc.split(': ')[1]
        val = sysrc.split(': ')[2]
        if rcfile not in ret:
            ret[rcfile] = {}
        ret[rcfile][var] = val
    return ret


def set(name, value, **kwargs):
    '''
    Set system rc configuration variables

    CLI Example:

     .. code-block:: bash

         salt '*' sysrc.remove name=sshd_enable
    '''

    cmd = 'sysrc -v'

    if 'file' in kwargs:
        cmd += ' -f '+kwargs['file']

    if 'jail' in kwargs:
        cmd += ' -j '+kwargs['jail']
    cmd += ' '+name+"=\""+value+"\""

    sysrcs = __salt__['cmd.run'](cmd, python_shell=False)

    ret = {}
    for sysrc in sysrcs.split("\n"):
        rcfile = sysrc.split(': ')[0]
        var = sysrc.split(': ')[1]
        newval = sysrc.split(': ')[2].split(" -> ")[1]
        if rcfile not in ret:
            ret[rcfile] = {}
        ret[rcfile][var] = newval
    return ret


def remove(name, **kwargs):
    '''
    Remove system rc configuration variables

    CLI Example:

     .. code-block:: bash

         salt '*' sysrc.remove name=sshd_enable
    '''

    cmd = 'sysrc -v'

    if 'file' in kwargs:
        cmd += ' -f '+kwargs['file']

    if 'jail' in kwargs:
        cmd += ' -j '+kwargs['jail']

    cmd += ' -x '+name

    sysrcs = __salt__['cmd.run'](cmd, python_shell=False)
    if "sysrc: unknown variable" in sysrcs:
        raise CommandExecutionError(sysrcs)
    else:
        return name+" removed"
