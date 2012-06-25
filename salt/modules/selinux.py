'''
Execute calls on selinux
'''
# Import python libs
import os

# Import salt libs
import salt.utils
from salt._compat import string_types

__selinux_fs_path__ = None


def __virtual__():
    '''
    Check if the os is Linux, and then if selinux is running in permissive or
    enforcing mode.
    '''
    if not salt.utils.which('semanage'):
        return False
    if not salt.utils.which('seinfo'):
        return False

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
    '''
    Return the location of the SELinux VFS directory

    CLI Example::

        salt '*' selinux.selinux_fs_path
    '''
    return __selinux_fs_path__


def getenforce():
    '''
    Return the mode selinux is running in

    CLI Example::

        salt '*' selinux.getenforce
    '''
    if open(os.path.join(__selinux_fs_path__, 'enforce'), 'r').read() == '0':
        return 'Permissive'
    else:
        return 'Enforcing'


def setenforce(mode):
    '''
    Set the SELinux enforcing mode

    CLI Example::

        salt '*' selinux.setenforce enforcing
    '''
    if isinstance(mode, string_types):
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


def getsebool(boolean):
    '''
    Return the information on a specific selinux boolean

    CLI Example::

        salt '*' selinux.getsebool virt_use_usb
    '''
    return list_sebool().get(boolean, {})


def setsebool(boolean, value, persist=False):
    '''
    Set the value for a boolean

    CLI Example::

        salt '*' selinux.setsebool virt_use_usb off
    '''
    if persist:
        cmd = 'setsebool -P {0} {1}'.format(boolean, value)
    else:
        cmd = 'setsebool {0} {1}'.format(boolean, value)
    return not __salt__['cmd.retcode'](cmd)


def setsebools(pairs, persist=False):
    '''
    Set the value of multiple booleans

    CLI Example::

        salt '*' selinux.setsebools '{virt_use_usb: on, squid_use_tproxy: off}'
    '''
    if not isinstance(pairs, dict):
        return {}
    if persist:
        cmd = 'setsebool -P '
    else:
        cmd = 'setsebool '
    for boolean, value in pairs.items():
        cmd = '{0} {1}={2}'.format(cmd, boolean, value)
    return not __salt__['cmd.retcode'](cmd)


def list_sebool():
    '''
    Return a structure listing all of the selinux booleans on the system and
    what state they are in

    CLI Example::

        salt '*' selinux.list_sebool
    '''
    bdata = __salt__['cmd.run']('semanage boolean -l').split('\n')
    ret = {}
    for line in bdata[1:]:
        if not line.strip():
            continue
        comps = line.split()
        ret[comps[0]] = {
                         'State': comps[1][1:],
                         'Default': comps[3][:-1],
                         'Description': ' '.join(comps[4:])}
    return ret
