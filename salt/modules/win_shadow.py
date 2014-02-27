# -*- coding: utf-8 -*-
'''
Manage the shadow file
'''

import salt.utils

# Define the module's virtual name
__virtualname__ = 'shadow'

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}

def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def info(name):
    '''
    Return information for the specified user
    This is just returns dummy data so that salt states can work.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    '''
    ret = {
            'name': name,
            'passwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_password(name, password):
    '''
    Set the password for a named user.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root mysecretpassword
    '''
    cmd = 'net user {0} {1}'.format(name, password)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.help

        salt '*' shadow.help set_password
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))

