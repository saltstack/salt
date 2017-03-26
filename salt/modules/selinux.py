# -*- coding: utf-8 -*-
'''
Execute calls on selinux

.. note::
    This module requires the ``semanage``, ``setsebool``, and ``semodule``
    commands to be available on the minion. On RHEL-based distributions,
    ensure that the ``policycoreutils`` and ``policycoreutils-python``
    packages are installed. If not on a Fedora or RHEL-based distribution,
    consult the selinux documentation for your distribution to ensure that the
    proper packages are installed.
'''

# Import python libs
from __future__ import absolute_import
import os
import re

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
    required_cmds = ('semanage', 'setsebool', 'semodule')

    # Iterate over all of the commands this module uses and make sure
    # each of them are available in the standard PATH to prevent breakage
    for cmd in required_cmds:
        if not salt.utils.which(cmd):
            return (False, cmd + ' is not in the path')
    # SELinux only makes sense on Linux *obviously*
    if __grains__['kernel'] == 'Linux':
        return 'selinux'
    return (False, 'Module only works on Linux with selinux installed')


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
    try:
        for directory in ('/sys/fs/selinux', '/selinux'):
            if os.path.isdir(directory):
                if os.path.isfile(os.path.join(directory, 'enforce')):
                    return directory
        return None
    #If selinux is Disabled, the path does not exist.
    except (AttributeError) as exc:
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
        return 'Disabled'


def getconfig():
    '''
    Return the selinux mode from the config file

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getconfig
    '''
    try:
        config = '/etc/selinux/config'
        with salt.utils.fopen(config, 'r') as _fp:
            for line in _fp:
                if line.strip().startswith('SELINUX='):
                    return line.split('=')[1].capitalize().strip()
    except (IOError, OSError, AttributeError):
        return None
    return None


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
            modestring = 'Enforcing'
        elif mode.lower() == 'permissive':
            mode = '0'
            modestring = 'Permissive'
        elif mode.lower() == 'disabled':
            mode = '0'
            modestring = 'Disabled'
        else:
            return 'Invalid mode {0}'.format(mode)
    elif isinstance(mode, int):
        if mode:
            mode = '1'
        else:
            mode = '0'
    else:
        return 'Invalid mode {0}'.format(mode)

    if getenforce() != 'Disabled':  # enforce file does not exist if currently disabled.  Only for toggling enforcing/permissive
        enforce = os.path.join(selinux_fs_path(), 'enforce')
        try:
            with salt.utils.fopen(enforce, 'w') as _fp:
                _fp.write(mode)
        except (IOError, OSError) as exc:
            msg = 'Could not write SELinux enforce file: {0}'
            raise CommandExecutionError(msg.format(str(exc)))

    config = '/etc/selinux/config'
    try:
        with salt.utils.fopen(config, 'r') as _cf:
            conf = _cf.read()
        try:
            with salt.utils.fopen(config, 'w') as _cf:
                conf = re.sub(r"\nSELINUX=.*\n", "\nSELINUX=" + modestring + "\n", conf)
                _cf.write(conf)
        except (IOError, OSError) as exc:
            msg = 'Could not write SELinux config file: {0}'
            raise CommandExecutionError(msg.format(str(exc)))
    except (IOError, OSError) as exc:
        msg = 'Could not read SELinux config file: {0}'
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


def getsemod(module):
    '''
    Return the information on a specific selinux module

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getsemod mysql

    .. versionadded:: 2016.3.0
    '''
    return list_semod().get(module, {})


def setsemod(module, state):
    '''
    Enable or disable an SELinux module.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsemod nagios Enabled

    .. versionadded:: 2016.3.0
    '''
    if state.lower() == 'enabled':
        cmd = 'semodule -e {0}'.format(module)
    elif state.lower() == 'disabled':
        cmd = 'semodule -d {0}'.format(module)
    return not __salt__['cmd.retcode'](cmd)


def install_semod(module_path):
    '''
    Install custom SELinux module from file

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.install_semod [salt://]path/to/module.pp

    .. versionadded:: develop
    '''
    if module_path.find('salt://') == 0:
        module_path = __salt__['cp.cache_file'](module_path)
    cmd = 'semodule -i {0}'.format(module_path)
    return not __salt__['cmd.retcode'](cmd)


def remove_semod(module):
    '''
    Remove SELinux module

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.remove_semod module_name

    .. versionadded:: develop
    '''
    cmd = 'semodule -r {0}'.format(module)
    return not __salt__['cmd.retcode'](cmd)


def list_semod():
    '''
    Return a structure listing all of the selinux modules on the system and
    what state they are in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.list_semod

    .. versionadded:: 2016.3.0
    '''
    helptext = __salt__['cmd.run']('semodule -h').splitlines()
    semodule_version = ''
    for line in helptext:
        if line.strip().startswith('full'):
            semodule_version = 'new'

    if semodule_version == 'new':
        mdata = __salt__['cmd.run']('semodule -lfull').splitlines()
        ret = {}
        for line in mdata:
            if not line.strip():
                continue
            comps = line.split()
            if len(comps) == 4:
                ret[comps[1]] = {'Enabled': False,
                                 'Version': None}
            else:
                ret[comps[1]] = {'Enabled': True,
                                 'Version': None}
    else:
        mdata = __salt__['cmd.run']('semodule -l').splitlines()
        ret = {}
        for line in mdata:
            if not line.strip():
                continue
            comps = line.split()
            if len(comps) == 3:
                ret[comps[0]] = {'Enabled': False,
                                 'Version': comps[1]}
            else:
                ret[comps[0]] = {'Enabled': True,
                                 'Version': comps[1]}
    return ret
