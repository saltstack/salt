# -*- coding: utf-8 -*-
'''
Support for pam
'''

# Import python libs
import os

# Import salt libs
import salt.utils

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


def __virtual__():
    '''
    Only load the module if iptables is installed
    '''
    if os.path.exists('/usr/lib/libpam.so'):
        return 'pam'
    return False


def _parse(contents=None, file_name=None):
    '''
    Parse a standard pam config file
    '''
    if contents:
        pass
    elif file_name and os.path.exists(file_name):
        with salt.utils.fopen(file_name, 'r') as ifile:
            contents = ifile.read()
    else:
        return False

    rules = []
    for line in contents.splitlines():
        if not line:
            continue
        if line.startswith('#'):
            continue
        control_flag = ''
        module = ''
        arguments = []
        comps = line.split()
        interface = comps[0]
        position = 1
        if comps[1].startswith('['):
            control_flag = comps[1].replace('[', '')
            for part in comps[2:]:
                position += 1
                if part.endswith(']'):
                    control_flag += ' {0}'.format(part.replace(']', ''))
                    position += 1
                    break
                else:
                    control_flag += ' {0}'.format(part)
        else:
            control_flag = comps[1]
            position += 1
        module = comps[position]
        if len(comps) > position:
            position += 1
            arguments = comps[position:]
        rules.append({'interface': interface,
                      'control_flag': control_flag,
                      'module': module,
                      'arguments': arguments})
    return rules


def read_file(file_name):
    '''
    This is just a test function, to make sure parsing works

    CLI Example:

    .. code-block:: bash

        salt '*' pam.read_file /etc/pam.d/login
    '''
    return _parse(file_name=file_name)


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' pam.help

        salt '*' pam.help read_file
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
