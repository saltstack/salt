# -*- coding: utf-8 -*-
'''
Support for reboot, shutdown, etc
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return 'system'


def halt(timeout=5):
    '''
    Halt a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.halt
    '''
    return shutdown(timeout)


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems

    CLI Example:

    .. code-block:: bash

        salt '*' system.init 3
    '''
    #cmd = 'init {0}'.format(runlevel)
    #ret = __salt__['cmd.run'](cmd)
    #return ret

    # TODO: Create a mapping of runlevels to
    #       corresponding Windows actions

    return 'Not implemented on Windows at this time.'


def poweroff(timeout=5):
    '''
    Poweroff a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.poweroff
    '''
    return shutdown(timeout)


def reboot(timeout=5):
    '''
    Reboot the system

    CLI Example:

    .. code-block:: bash

        salt '*' system.reboot
    '''
    cmd = 'shutdown /r /t {0}'.format(timeout)
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown(timeout=5):
    '''
    Shutdown a running system

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown
    '''
    cmd = 'shutdown /s /t {0}'.format(timeout)
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown_hard():
    '''
    Shutdown a running system with no timeout or warning

    CLI Example:

    .. code-block:: bash

        salt '*' system.shutdown_hard
    '''
    cmd = 'shutdown /p /f'
    ret = __salt__['cmd.run'](cmd)
    return ret


def set_computer_name(name):
    '''
    Set the Windows computer name

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' ip.set_computer_name 'DavesComputer'
    '''
    cmd = ('wmic computersystem where name="%COMPUTERNAME%"'
           ' call rename name="{0}"'
           )
    log.debug('Attempting to change computer name. Cmd is: '.format(cmd))
    ret = __salt__['cmd.run'](cmd.format(name))
    if 'ReturnValue = 0;' in ret:
        return {'Computer name': name }
    return False


def set_computer_desc(desc):
    '''
    Set the Windows computer description

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' ip.set_computer_desc 'This computer belongs to Dave!'
    '''
    cmd = 'net config server /srvcomment:"{0}"'.format(desc)
    __salt__['cmd.run'](cmd)
    return {'Computer Description': desc }
