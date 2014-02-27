# -*- coding: utf-8 -*-
'''
Module for configuring Windows Firewall
'''

# Import python libs
import re

# Import salt libs
import salt.utils

# Define the module's virtual name
__virtualname__ = 'firewall'

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


def get_config():
    '''
    Get the status of all the firewall profiles

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.get_config
    '''
    profiles = {}
    curr = None

    cmd = 'netsh advfirewall show allprofiles'
    for line in __salt__['cmd.run'](cmd).splitlines():
        if not curr:
            tmp = re.search('(.*) Profile Settings:', line)
            if tmp:
                curr = tmp.group(1)
        elif line.startswith('State'):
            profiles[curr] = line.split()[1] == 'ON'
            curr = None

    return profiles


def disable():
    '''
    Disable all the firewall profiles

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.disable
    '''
    return __salt__['cmd.run'](
            'netsh advfirewall set allprofiles state off'
            ) == 'Ok.'


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' firewall.help

        salt '*' firewall.help disable
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))

