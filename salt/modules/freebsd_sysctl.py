# -*- coding: utf-8 -*-
'''
Module for viewing and modifying sysctl parameters
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'sysctl'


def __virtual__():
    '''
    Only run on FreeBSD systems
    '''
    return __virtualname__ if __grains__['os'] == 'FreeBSD' else False


def _formatfor(name, value, config, tail=''):
    if config == '/boot/loader.conf':
        return '{0}="{1}"{2}'.format(name, value, tail)
    else:
        return '{0}={1}{2}'.format(name, value, tail)


def show(config_file=False):
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    '''
    roots = (
        'compat',
        'debug',
        'dev',
        'hptmv',
        'hw',
        'kern',
        'machdep',
        'net',
        'p1003_1b',
        'security',
        'user',
        'vfs',
        'vm'
    )
    cmd = 'sysctl -ae'
    ret = {}
    out = __salt__['cmd.run'](cmd, output_loglevel='trace')
    comps = ['']
    for line in out.splitlines():
        if any([line.startswith('{0}.'.format(root)) for root in roots]):
            comps = line.split('=', 1)
            ret[comps[0]] = comps[1]
        elif comps[0]:
            ret[comps[0]] += '{0}\n'.format(line)
        else:
            continue
    return ret


def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.get hw.physmem
    '''
    cmd = 'sysctl -n {0}'.format(name)
    out = __salt__['cmd.run'](cmd, python_shell=False)
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.inet.icmp.icmplim 50
    '''
    ret = {}
    cmd = 'sysctl {0}="{1}"'.format(name, value)
    data = __salt__['cmd.run_all'](cmd, python_shell=False)

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

        salt '*' sysctl.persist net.inet.icmp.icmplim 50
        salt '*' sysctl.persist coretemp_load NO config=/boot/loader.conf
    '''
    nlines = []
    edited = False
    value = str(value)

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
        nlines.append("{0}\n".format(_formatfor(name, value, config)))
    with salt.utils.fopen(config, 'w+') as ofile:
        ofile.writelines(nlines)
    if config != '/boot/loader.conf':
        assign(name, value)
    return 'Updated'
