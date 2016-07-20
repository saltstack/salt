# -*- coding: utf-8 -*-
'''
Execute calls on selinux

.. note::
    This module requires the ``semanage`` and ``setsebool`` commands to be
    available on the minion. On RHEL-based distributions, ensure that the
    ``policycoreutils-python`` package is installed. On Fedora 23 and up,
    ensure that the ``policycoreutils-python-utils`` package is installed.  If
    not on a Fedora or RHEL-based distribution, consult the selinux
    documentation for your distro to ensure that the proper packages are
    installed.
'''

# Import python libs
from __future__ import absolute_import
import os

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
import salt.ext.six as six


def __virtual__():
    '''
    Check if the os is Linux, and then if selinux is running in permissive or
    enforcing mode.
    '''
    required_cmds = ('semanage', 'setsebool')

    # Iterate over all of the commands this module uses and make sure
    # each of them are available in the standard PATH to prevent breakage
    for cmd in required_cmds:
        if not salt.utils.which(cmd):
            return False
    # SELinux only makes sense on Linux *obviously*
    if __grains__['kernel'] == 'Linux' and selinux_fs_path():
        return 'selinux'
    return False


# Cache the SELinux directory to not look it up over and over
@decorators.memoize
def selinux_fs_path():
    '''
    Return the location of the SELinux VFS directory

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.selinux_fs_path
    '''
    # systems running systemd (e.g. Fedora 15 and newer)
    # have the selinux filesystem in a different location
    for directory in ('/sys/fs/selinux', '/selinux'):
        if os.path.isdir(directory):
            if os.path.isfile(os.path.join(directory, 'enforce')):
                return directory
    return None


def getenforce():
    '''
    Return the mode selinux is running in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getenforce
    '''
    try:
        enforce = os.path.join(selinux_fs_path(), 'enforce')
        with salt.utils.fopen(enforce, 'r') as _fp:
            if _fp.readline().strip() == '0':
                return 'Permissive'
            else:
                return 'Enforcing'
    except (IOError, OSError, AttributeError) as exc:
        msg = 'Could not read SELinux enforce file: {0}'
        raise CommandExecutionError(msg.format(str(exc)))


def setenforce(mode):
    '''
    Set the SELinux enforcing mode

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setenforce enforcing
    '''
    if isinstance(mode, six.string_types):
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
    enforce = os.path.join(selinux_fs_path(), 'enforce')
    try:
        with salt.utils.fopen(enforce, 'w') as _fp:
            _fp.write(mode)
    except (IOError, OSError) as exc:
        msg = 'Could not write SELinux enforce file: {0}'
        raise CommandExecutionError(msg.format(str(exc)))
    return getenforce()


def getsebool(boolean):
    '''
    Return the information on a specific selinux boolean

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getsebool virt_use_usb
    '''
    return list_sebool().get(boolean, {})


def setsebool(boolean, value, persist=False):
    '''
    Set the value for a boolean

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsebool virt_use_usb off
    '''
    if persist:
        cmd = 'setsebool -P {0} {1}'.format(boolean, value)
    else:
        cmd = 'setsebool {0} {1}'.format(boolean, value)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def setsebools(pairs, persist=False):
    '''
    Set the value of multiple booleans

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsebools '{virt_use_usb: on, squid_use_tproxy: off}'
    '''
    if not isinstance(pairs, dict):
        return {}
    if persist:
        cmd = 'setsebool -P '
    else:
        cmd = 'setsebool '
    for boolean, value in six.iteritems(pairs):
        cmd = '{0} {1}={2}'.format(cmd, boolean, value)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def list_sebool():
    '''
    Return a structure listing all of the selinux booleans on the system and
    what state they are in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.list_sebool
    '''
    bdata = __salt__['cmd.run']('semanage boolean -l').splitlines()
    ret = {}
    for line in bdata[1:]:
        if not line.strip():
            continue
        comps = line.split()
        ret[comps[0]] = {'State': comps[1][1:],
                         'Default': comps[3][:-1],
                         'Description': ' '.join(comps[4:])}
    return ret
