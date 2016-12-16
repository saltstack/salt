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

import logging
log = logging.getLogger(__name__)

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandExecutionError, SaltInvocationError

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
    # If selinux is Disabled, the path does not exist.
    except AttributeError:
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
    except (IOError, OSError, AttributeError):
        return 'Disabled'


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

    # enforce file does not exist if currently disabled.  Only for toggling enforcing/permissive
    if getenforce() != 'Disabled':
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


def _validate_filetype(filetype):
    '''
        Checks if the given filetype is a valid SELinux filetype specification.
        Throws an SaltInvocationError if it isn't.

        .. versionadded:: 2016.3.4
    '''
    if filetype not in ['a', 'f', 'd', 'c', 'b', 's', 'l', 'p']:
        raise SaltInvocationError('Invalid filetype given: {0}'.format(filetype))
    return True


def filetype_id_to_string(filetype='a'):
    '''
    Translates SELinux filetype single-letter representation
    to a more human-readable version (which is also used in `semanage fcontext -l`).

    .. versionadded:: 2016.3.4
    '''
    return {
        'a': 'all files',
        'f': 'regular file',
        'd': 'directory',
        'c': 'character device',
        'b': 'block device',
        's': 'socket',
        'l': 'symbolic link',
        'p': 'named pipe'}.get(filetype, 'error')


def fcontext_get_policy(name, filetype=None, se_type=None, se_user=None, se_level=None):
    '''
    Returns the current entry in the SELinux policy list as a dictionary.
    Returns None if no exact match was found
    Returned keys are:
    - filespec (the name supplied and matched)
    - filetype (the descriptive name of the filetype supplied)
    - selinux_user, selinux_role, selinux_type, selinux_level (the selinux context)
    For a more in-depth explanation of the selinux context, go to
    https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/Security-Enhanced_Linux/chap-Security-Enhanced_Linux-SELinux_Contexts.html

    name: filespec of the file or directory. Regex syntax is allowed.
    filetype: The SELinux filetype specification.
              Use one of [a, f, d, c, b, s, l, p].
              See also `man semanage-fcontext`.
              Defaults to 'a' (all files)

    .. versionadded:: 2016.3.4
    '''
    _validate_filetype(filetype)
    cmd = "semanage fcontext -l | egrep '^" + re.escape(name) + "[ ]{2,}"
    if filetype is not None:
        cmd += filetype_id_to_string(filetype)
    else:
        cmd += '[[:alpha:] ]+'
    cmd += '[ ]{2,}'
    if se_user is not None:
        cmd += se_user
    else:
        cmd += '[^:]+'
    cmd += ':[^:]+:'  # Include any SELinux role
    if se_type is not None:
        cmd += se_type
    else:
        cmd += '[^:]+'
    cmd += ':'
    if se_level is not None:
        cmd += se_level
    else:
        cmd += '[^:]+'
    cmd += "$'"
    current_entry_text = __salt__['cmd.shell'](cmd)
    if current_entry_text == '':
        return None
    ret = {}
    current_entry_list = re.split('[ ]{2,}', current_entry_text)
    ret['filespec'] = current_entry_list[0]
    ret['filetype'] = current_entry_list[1]
    selinux_context = current_entry_list[2].split(':')
    for index, value in enumerate(['selinux_user', 'selinux_role', 'selinux_type', 'selinux_level']):
        ret[value] = selinux_context[index]
    return ret


def fcontext_add_or_delete_policy(action, name, filetype=None, se_type=None, se_user=None, se_level=None):
    '''
    Sets ('add' overwrites policies) or deletes the SELinux policy for a given
    filespec and other optional parameters.
    Returns the result of the call to semanage.
    Note that you don't have to remove an entry before setting a new one for a given
    filespec and filetype, as adding one with semanage automatically overwrites a
    previously configured SELinux context.

    name: filespec of the file or directory. Regex syntax is allowed.
    file_type: The SELinux filetype specification.
              Use one of [a, f, d, c, b, s, l, p].
              See also ``man semanage-fcontext``.
              Defaults to 'a' (all files)
    se_type: SELinux context type. There are many.
    se_user: SELinux user. Use ``semanage login -l`` to determine which ones are available to you
    se_level: The MLS range of the SELinux context.

    .. versionadded:: 2016.3.4
    '''
    if action not in ['add', 'delete']:
        raise SaltInvocationError('Actions supported are "add" and "delete", not "{0}".'.format(action))
    cmd = 'semanage fcontext --{0}'.format(action)
    if filetype is not None:
        _validate_filetype(filetype)
        cmd += ' --ftype {0}'.format(filetype)
    if se_type is not None:
        cmd += ' --type {0}'.format(se_type)
    if se_user is not None:
        cmd += ' --seuser {0}'.format(se_user)
    if se_level is not None:
        cmd += ' --range {0}'.format(se_level)
    cmd += ' ' + re.escape(name)
    return __salt__['cmd.run_all'](cmd)


def fcontext_policy_is_applied(name):
    '''
    Returns an empty string if the SELinux policy for a given filespec is applied,
    returns string with differences in policy and actual situation otherwise.

    name: filespec of the file or directory. Regex syntax is allowed.

    .. versionadded:: 2016.3.4
    '''
    return __salt__['cmd.run']('restorecon -n -v {0}'.format(re.escape(name)))


def fcontext_apply_policy(name, recursive=False):
    '''
    Applies SElinux policies to filespec using `restorecon [-R] filespec`.
    Returns dict with changes if succesful, the output of the restorecon command otherwise.

    name: filespec of the file or directory. Regex syntax is allowed.
    recursive: Recursively apply SELinux policies.

    .. versionadded:: 2016.3.4
    '''
    ret = {}
    changes_text = fcontext_policy_is_applied(name)
    cmd = 'restorecon '
    if recursive:
        cmd += '-R '
    cmd += re.escape(name)
    apply_ret = __salt__['cmd.run_all'](cmd)
    ret.update(apply_ret)
    if apply_ret['retcode'] == 0:
        changes_list = re.findall('context (.*)->(.*)$', changes_text)
        log.debug('fcontext_apply_policy: Changes: {0}'.format(changes_list))
        ret.update({'changes': {'old': changes_list[0][0], 'new': changes_list[0][1]}})
    return ret
