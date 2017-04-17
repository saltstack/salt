# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''
from __future__ import absolute_import

import salt.utils

__virtualname__ = 'system'


def __virtual__():
    '''
    Only supported on POSIX-like systems
    Windows, Solaris, and Mac have their own modules
    '''
    if salt.utils.is_windows():
        return (False, 'This module is not available on windows')

    if salt.utils.is_darwin():
        return (False, 'This module is not available on Mac OS')

    if salt.utils.is_sunos():
        return (False, 'This module is not available on SunOS')

    if not salt.utils.which('shutdown'):
        return (False, 'The system execution module failed to load: '
                'only available on Linux systems with shutdown command.')

    return __virtualname__


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
        The wait time in minutes before the system will be rebooted.

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
