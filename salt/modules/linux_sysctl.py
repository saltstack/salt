'''
Module for viewing and modifying sysctl parameters
'''

import re
import os
from salt._compat import string_types
from salt.exceptions import CommandExecutionError

__outputter__ = {
    'assign': 'txt',
    'get': 'txt',
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

    CLI Example::

        salt '*' sysctl.assign net.ipv4.ip_forward 1
    '''
    sysctl_file = '/proc/sys/{0}'.format(name.replace('.', '/'))
    if not os.path.exists(sysctl_file):
        raise CommandExecutionError('sysctl {0} does not exist'.format(name))

    ret  = {}
    cmd  = 'sysctl -w {0}="{1}"'.format(name, value)
    data = __salt__['cmd.run_all'](cmd)
    out  = data['stdout']

    # Example:
    #    # sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
    #    net.ipv4.tcp_rmem = 4096 87380 16777216
    regex = re.compile('^{0}\s+=\s+{1}$'.format(name, value))

    if not regex.match(out):
        if data['retcode'] != 0 and data['stderr']:
            error = data['stderr']
        else:
            error = out
        raise CommandExecutionError('sysctl -w failed: {0}'.format(error))
    new_name, new_value = out.split(' = ')
    ret[new_name] = new_value
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

        # Strip trailing whitespace and split the k,v
        comps = [i.strip() for i in line.split('=', 1)]

        # On Linux procfs, files such as /proc/sys/net/ipv4/tcp_rmem or any
        # other sysctl with whitespace in it consistently uses 1 tab.  Lets
        # allow our users to put a space or tab between multi-value sysctls
        # and have salt not try to set it every single time.
        if isinstance(comps[1], string_types) and ' ' in comps[1]:
            comps[1] = re.sub('\s+', '\t', comps[1])

        # Do the same thing for the value 'just in case'
        if isinstance(value, string_types) and ' ' in value:
            value = re.sub('\s+', '\t', value)

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
        else:
            nlines.append(line)
    if not edited:
        nlines.append('{0} = {1}\n'.format(name, value))
    open(config, 'w+').writelines(nlines)
    assign(name, value)
    return 'Updated'
