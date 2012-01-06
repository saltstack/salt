'''
Execute calls on selinux
'''

import os

__selinux_fs_path__ = None

def __virtual__():
    '''
    Check if the os is Linux, and then if selinux is running in permissive or
    enforcing mode.
    '''
    global __selinux_fs_path__
    if __grains__['kernel'] == 'Linux':
        # systems running systemd (e.g. Fedora 15 and newer)
        # have the selinux filesystem in a different location
        for directory in ['/sys/fs/selinux', '/selinux']:
            if os.path.isdir(directory):
                if os.path.isfile(os.path.join(directory, 'enforce')):
                    __selinux_fs_path__ = directory
                    return 'selinux'
    return False

def selinux_fs_path():
    return __selinux_fs_path__

def getenforce():
    '''
    Return the mode selinux is running in

    CLE Example::

        salt '*' selinux.getenforce
    '''
    if open(os.path.join(__selinux_fs_path__, 'enforce'), 'r').read() == '0':
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
        elif mode.lower() == 'permissive':
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
