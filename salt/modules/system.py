# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''

import salt.utils

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}

def __virtual__():
    '''
    Only supported on POSIX-like systems
    '''
    if salt.utils.is_windows() or not salt.utils.which('shutdown'):
        return False
    return 'system'


def halt():
    '''
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    '''
    cmd = 'halt'
    ret = __salt__['cmd.run'](cmd)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    cmd = 'init {0}'.format(runlevel)
    ret = __salt__['cmd.run'](cmd)
    return ret


def poweroff():
    '''
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    '''
    cmd = 'poweroff'
    ret = __salt__['cmd.run'](cmd)
    return ret


def reboot():
    '''
    Reboot the system using the 'reboot' command

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    '''
    cmd = 'reboot'
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown(at_time=None):
    '''
    Shutdown a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
    '''

    if at_time:
        cmd = 'shutdown -h {0}'.format(at_time)
    else:
        cmd = 'shutdown -h now'
    ret = __salt__['cmd.run'](cmd)
    return ret


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' system.help

        salt '*' system.help reboot
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))

