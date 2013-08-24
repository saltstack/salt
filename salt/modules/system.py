'''
Support for reboot, shutdown, etc
'''

import salt.utils


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

    CLI Example::

        salt '*' system.halt
    '''
    cmd = 'halt'
    ret = __salt__['cmd.run'](cmd)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example::

        salt '*' system.init 3
    '''
    cmd = 'init {0}'.format(runlevel)
    ret = __salt__['cmd.run'](cmd)
    return ret


def poweroff():
    '''
    Poweroff a running system

    CLI Example::

        salt '*' system.poweroff
    '''
    cmd = 'poweroff'
    ret = __salt__['cmd.run'](cmd)
    return ret


def reboot():
    '''
    Reboot the system using the 'reboot' command

    CLI Example::

        salt '*' system.reboot
    '''
    cmd = 'reboot'
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown():
    '''
    Shutdown a running system

    CLI Example::

        salt '*' system.shutdown
    '''
    cmd = 'shutdown'
    ret = __salt__['cmd.run'](cmd)
    return ret
