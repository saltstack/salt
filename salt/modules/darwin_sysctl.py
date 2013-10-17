# -*- coding: utf-8 -*-
'''
Module for viewing and modifying sysctl parameters
'''

# Import python libs
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Define the module's virtual name
__virtualname__ = 'sysctl'


def __virtual__():
    '''
    Only run on Darwin (OS X) systems
    '''
    return __virtualname__ if __grains__['os'] == 'MacOS' else False


def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.show
    '''
    roots = (
        'audit',
        'debug',
        'hw',
        'hw',
        'kern',
        'machdep',
        'net',
        'net',
        'security',
        'user',
        'vfs',
        'vm',
    )
    cmd = 'sysctl -a'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    comps = ['']
    for line in out:
        # This might need to be converted to a regex, and more, as sysctl output
        # can for some reason contain entries such as:
        #
        # user.tzname_max = 255
        # kern.clockrate: hz = 100, tick = 10000, profhz = 100, stathz = 100
        # kern.clockrate: { hz = 100, tick = 10000, tickadj = 2, profhz = 100, stathz = 100 }
        #
        # Yes. That's two `kern.clockrate`.
        #
        if any([line.startswith('{0}.'.format(root)) for root in roots]):
            comps = line.split(': ' if ': ' in line else ' = ', 1)
            if len(comps) == 2:
                ret[comps[0]] = comps[1]
            else:
                ret[comps[0]] = ''
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
    out = __salt__['cmd.run'](cmd)
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' sysctl.assign net.inet.icmp.icmplim 50
    '''
    ret = {}
    cmd = 'sysctl -w {0}="{1}"'.format(name, value)
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

        salt '*' sysctl.persist net.inet.icmp.icmplim 50
        salt '*' sysctl.persist coretemp_load NO config=/etc/sysctl.conf
    '''
    nlines = []
    edited = False
    value = str(value)

    # If the sysctl.conf is not present, add it
    if not os.path.isfile(config):
        try:
            with salt.utils.fopen(config, 'w+') as _fh:
                _fh.write('#\n# Kernel sysctl configuration\n#\n')
        except (IOError, OSError):
            msg = 'Could not write to file: {0}'
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
                new_line = '{0}={1}'.format(name, value)
                nlines.append(new_line)
                edited = True
    if not edited:
        nlines.append('{0}={1}'.format(name, value))
    with salt.utils.fopen(config, 'w+') as ofile:
        ofile.writelines(nlines)
    return 'Updated'
