# -*- coding: utf-8 -*-
'''
Module for viewing and modifying OpenBSD sysctl parameters
'''
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'sysctl'


def __virtual__():
    '''
    Only run on OpenBSD systems
    '''
    return __virtualname__ if __grains__['os'] == 'OpenBSD' else False


def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    '''
    cmd = 'sysctl'
    ret = {}
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace')
    for line in out.splitlines():
        if not line or '=' not in line:
            continue
        comps = line.split('=', 1)
        ret[comps[0]] = comps[1]
    return ret


def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get hw.physmem
    '''
    cmd = 'sysctl -n {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.inet.ip.forwarding 1
    '''
    ret = {}
    cmd = 'sysctl {0}="{1}"'.format(name, value)
    data = __salt__['cmd.run_all'](cmd)

    if data['retcode'] != 0:
        raise CommandExecutionError('sysctl failed: {0}'.format(
            data['stderr']))
    new_name, new_value = data['stdout'].split(':', 1)
    ret[new_name] = new_value.split(' -> ')[-1]
    return ret


def persist(name, value, config='/etc/sysctl.conf'):
    '''
    Assign and persist a simple sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.persist net.inet.ip.forwarding 1
    '''
    nlines = []
    edited = False
    value = str(value)

    # create /etc/sysctl.conf if not present
    if not os.path.isfile(config):
        try:
            salt.utils.fopen(config, 'w+').close()
        except (IOError, OSError):
            msg = 'Could not create {0}'
            raise CommandExecutionError(msg.format(config))

    with salt.utils.fopen(config, 'r') as ifile:
        for line in ifile:
            if not line.startswith('{0}='.format(name)):
                nlines.append(line)
                continue
            else:
                key, rest = line.split('=', 1)
                if rest.startswith('"'):
                    _, rest_v, rest = rest.split('"', 2)
                elif rest.startswith('\''):
                    _, rest_v, rest = rest.split('\'', 2)
                else:
                    rest_v = rest.split()[0]
                    rest = rest[len(rest_v):]
                if rest_v == value:
                    return 'Already set'
                new_line = _formatfor(key, value, config, rest)
                nlines.append(new_line)
                edited = True
    if not edited:
        nlines.append('{0}={1}\n'.format(name, value))
    with salt.utils.fopen(config, 'w+') as ofile:
        ofile.writelines(nlines)

    assign(name, value)
    return 'Updated'
