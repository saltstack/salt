'''
Execute calls on selinux
'''

import os

def __virtual__():
    '''
    Check if the os is Linux, and then if selinux is running in permissive or
    enforcing mode.
    '''
    if __grains__['kernel'] == 'Linux':
        if os.path.isdir('/selinux'):
            if os.path.isfile('/selinux/enforce'):
                return 'selinux'
    return False

def getenforce():
    '''
    Return the mode selinux is running in

    CLE Example:
    salt '*' selinux.getenforce
    '''
    if open('/selinux/enforce', 'r').read() == '0':
        return 'Permissive'
    else:
        return 'Enforcing'

def setenforce(mode):
    '''
    Set the enforcing mode
    '''
    if isinstance(mode, str):
        if mode.lower() == 'enforcing':
            mode = '1'
        elif mode.lower() == 'Permissive':
            mode = '0'
        else:
            return 'Invalid mode {0}'.format(mode)
    elif isinstance(mode, int):
        if mode:
            mode = '1'
        else:
            mode = '0'
    else:
        return 'Invalid mode {0}'.format(mode)
    __salt__['cmd.run']('setenforce {0}'.format(mode))
    return getenforce()
