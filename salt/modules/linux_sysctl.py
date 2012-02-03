'''
Module for viewing and modifying sysctl parameters
'''

import os
from salt.exceptions import CommandExecutionError

__outputter__ = {
    'assign': 'txt',
}


def __virtual__():
    '''
    Only run on Linux systems
    '''
    return 'sysctl' if __grains__['kernel'] == 'Linux' else False


def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example::

        salt '*' sysctl.show
    '''
    cmd = 'sysctl -a'
    ret = {}
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if not line:
            continue
        if ' = ' not in line:
            continue
        comps = line.split(' = ')
        ret[comps[0]] = comps[1]
    return ret


def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example::

        salt '*' sysctl.get net.ipv4.ip_forward
    '''
    cmd = 'sysctl -n {0}'.format(name)
    out = __salt__['cmd.run'](cmd).strip()
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example:
    salt '*' sysctl.assign net.ipv4.ip_forward 1
    '''
    sysctl_file = '/proc/sys/{0}'.format(name.replace('.', '/'))
    if not os.path.exists(sysctl_file):
        raise CommandExecutionError('sysctl {0} does not exist'.format(name))

    cmd = 'sysctl -w {0}={1}'.format(name, value)
    ret = {}
    out = __salt__['cmd.run'](cmd).strip()
    if ' = ' not in out:
        raise CommandExecutionError('sysctl -w failed: {0}'.format(out))
    comps = out.split(' = ')
    ret[comps[0]] = comps[1]
    return ret


def persist(name, value, config='/etc/sysctl.conf'):
    '''
    Assign and persist a simple sysctl parameter for this minion

    CLI Example::

        salt '*' sysctl.persist net.ipv4.ip_forward 1
    '''
    running = show()
    edited = False
    # If the sysctl.conf is not present, add it
    if not os.path.isfile(config):
        open(config, 'w+').write('#\n# Kernel sysctl configuration\n#\n')
    # Read the existing sysctl.conf
    nlines = []
    for line in open(config, 'r').readlines():
        if line.startswith('#'):
            nlines.append(line)
            continue
        if '=' not in line:
            nlines.append(line)
            continue
        comps = line.split('=')
        comps[0] = comps[0].strip()
        comps[1] = comps[1].strip()
        if len(comps) < 2:
            nlines.append(line)
            continue
        if name == comps[0]:
            # This is the line to edit
            if str(comps[1]) == str(value):
                # It is correct in the config, check if it is correct in /proc
                if name in running:
                    if not running[name] == str(value):
                        assign(name, value)
                        return 'Updated'
                return 'Already set'
            nlines.append('{0} = {1}\n'.format(name, value))
            edited = True
            continue
    if not edited:
        nlines.append('{0} = {1}\n'.format(name, value))
    open(config, 'w+').writelines(nlines)
    assign(name, value)
    return 'Updated'
