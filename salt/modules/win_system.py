'''
Support for reboot, shutdown, etc
'''

import salt.utils


def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return 'system'


def halt():
    '''
    Halt a running system
    
    CLI Example::
    
        salt '*' system.halt
    '''
    cmd = 'shutdown /s'
    ret = __salt__['cmd.run'](cmd)
    return ret


def init(runlevel):
    '''
    Change the system runlevel on sysV compatible systems
    
    CLI Example::
    
        salt '*' system.init 3
    '''
    #cmd = 'init {0}'.format(runlevel)
    #ret = __salt__['cmd.run'](cmd)
    #return ret

    # TODO: Create a mapping of runlevels to 
    #       corresponding Windows actions

    return 'Not implemented on Windows yet.'


def poweroff():
    '''
    Poweroff a running system
    
    CLI Example::
    
        salt '*' system.poweroff
    '''
    cmd = 'shutdown /s'
    ret = __salt__['cmd.run'](cmd)
    return ret


def reboot():
    '''
    Reboot the system
    
    CLI Example::
    
        salt '*' system.reboot
    '''
    cmd = 'shutdown /r'
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown(timeout=5):
    '''
    Shutdown a running system
    
    CLI Example::
    
        salt '*' system.shutdown
    '''
    cmd = 'shutdown /s /t {0}'.format(timeout)
    ret = __salt__['cmd.run'](cmd)
    return ret


def shutdown_hard():
    '''
    Shutdown a running system with no timeout or warning
    
    CLI Example::
    
        salt '*' system.shutdown_hard
    '''
    cmd = 'shutdown /p'
    ret = __salt__['cmd.run'](cmd)
    return ret
