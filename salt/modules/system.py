# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

import salt.utils


def __virtual__():
    '''
    Only supported on POSIX-like systems
    '''
    if salt.utils.is_windows() or not salt.utils.which('shutdown'):
        return False
    return True


def halt():
    '''
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    '''
    cmd = ['halt']
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    cmd = ['init', '{0}'.format(runlevel)]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def poweroff():
    '''
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    '''
    cmd = ['poweroff']
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def reboot(at_time=None):
    '''
    Reboot the system

    at_time
        The wait time in minutes before the system will be shutdown.

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    '''
    cmd = ['shutdown', '-r', ('{0}'.format(at_time) if at_time else 'now')]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret


def shutdown(at_time=None):
    '''
    Shutdown a running system

    at_time
        The wait time in minutes before the system will be shutdown.

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown 5
    '''
    cmd = ['shutdown', '-h', ('{0}'.format(at_time) if at_time else 'now')]
    ret = __salt__['cmd.run'](cmd, python_shell=False)
    return ret
