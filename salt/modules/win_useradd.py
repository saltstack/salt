# -*- coding: utf-8 -*-
'''
Manage Windows users with the net user command

NOTE: This currently only works with local user accounts, not domain accounts
'''
from __future__ import absolute_import

try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except:  # pylint: disable=W0702
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils
from salt.ext.six import string_types
from salt.exceptions import CommandExecutionError
import logging

log = logging.getLogger(__name__)

try:
    import win32net
    import win32netcon
    import win32security
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is Windows
    '''
    if HAS_WIN32NET_MODS is True and salt.utils.is_windows():
        return __virtualname__
    return False


def add(name,
        password=None,
        # Disable pylint checking on the next options. They exist to match the
        # user modules of other distributions.
        # pylint: disable=W0613
        uid=None,
        gid=None,
        groups=None,
        home=False,
        shell=None,
        unique=False,
        system=False,
        fullname=False,
        roomnumber=False,
        workphone=False,
        homephone=False,
        loginclass=False,
        createhome=False
        # pylint: enable=W0613
        ):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name password
    '''
    if password:
        ret = __salt__['cmd.run_all']('net user {0} {1} /add /y'.format(name, password))
    else:
        ret = __salt__['cmd.run_all']('net user {0} /add'.format(name))
    if groups:
        chgroups(name, groups)
    if fullname:
        chfullname(name, fullname)
    return ret['retcode'] == 0


def delete(name,
           # Disable pylint checking on the next options. They exist to match
           # the user modules of other distributions.
           # pylint: disable=W0613
           purge=False,
           force=False
           # pylint: enable=W0613
           ):
    '''
    Remove a user from the minion
    NOTE: purge and force have not been implemented on Windows yet

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name
    '''
    ret = __salt__['cmd.run_all']('net user {0} /delete'.format(name))
    return ret['retcode'] == 0


def setpassword(name, password):
    '''
    Set a user's password

    CLI Example:

    .. code-block:: bash

        salt '*' user.setpassword name password
    '''
    ret = __salt__['cmd.run_all'](
        'net user {0} {1}'.format(name, password), output_loglevel='quiet'
    )
    return ret['retcode'] == 0


def addgroup(name, group):
    '''
    Add user to a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.addgroup username groupname
    '''
    name = _cmd_quote(name)
    group = _cmd_quote(group).lstrip('\'').rstrip('\'')

    user = info(name)
    if not user:
        return False
    if group in user['groups']:
        return True

    cmd = 'net localgroup "{0}" {1} /add'.format(group, name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=True)

    return ret['retcode'] == 0


def removegroup(name, group):
    '''
    Remove user from a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.removegroup username groupname
    '''
    name = _cmd_quote(name)
    group = _cmd_quote(group).lstrip('\'').rstrip('\'')

    user = info(name)

    if not user:
        return False

    if group not in user['groups']:
        return True

    cmd = 'net localgroup "{0}" {1} /delete'.format(group, name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=True)

    return ret['retcode'] == 0


def chhome(name, home, persist=False):
    '''
    Change the home directory of the user, pass True for persist to move files
    to the new home directory if the old home directory exist.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo \\\\fileserver\\home\\foo True
    '''
    pre_info = info(name)

    if not pre_info:
        return False

    if home == pre_info['home']:
        return True

    if __salt__['cmd.retcode']('net user {0} /homedir:{1}'.format(
            name, home)) != 0:
        return False

    if persist and home is not None and pre_info['home'] is not None:
        cmd = 'move /Y {0} {1}'.format(pre_info['home'], home)
        if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
            log.debug('Failed to move the contents of the Home Directory')

    post_info = info(name)
    if post_info['home'] != pre_info['home']:
        return post_info['home'] == home

    return False


def chprofile(name, profile):
    '''
    Change the profile directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chprofile foo \\\\fileserver\\profiles\\foo
    '''
    pre_info = info(name)

    if not pre_info:
        return False

    if profile == pre_info['profile']:
        return True
    if __salt__['cmd.retcode']('net user {0} /profilepath:{1}'.format(
            name, profile)) != 0:
        return False

    post_info = info(name)
    if post_info['profile'] != pre_info['profile']:
        return post_info['profile'] == profile

    return False


def chfullname(name, fullname):
    '''
    Change the full name of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname user 'First Last'
    '''
    pre_info = info(name)

    if not pre_info:
        return False

    name = _cmd_quote(name)
    fullname_qts = _cmd_quote(fullname).replace("'", "\"")

    if fullname == pre_info['fullname']:
        return True
    if __salt__['cmd.retcode']('net user {0} /fullname:{1}'.format(
            name, fullname_qts), python_shell=True) != 0:
        return False

    post_info = info(name)
    if post_info['fullname'] != pre_info['fullname']:
        return post_info['fullname'] == fullname

    return False


def chgroups(name, groups, append=True):
    '''
    Change the groups this user belongs to, add append=False to make the user a
    member of only the specified groups

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root True
    '''
    if isinstance(groups, string_types):
        groups = groups.split(',')

    groups = [x.strip(' *') for x in groups]
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True

    name = _cmd_quote(name)

    if not append:
        for group in ugrps:
            group = _cmd_quote(group).lstrip('\'').rstrip('\'')
            if group not in groups:
                cmd = 'net localgroup "{0}" {1} /delete'.format(group, name)
                __salt__['cmd.run_all'](cmd, python_shell=True)

    for group in groups:
        if group in ugrps:
            continue
        group = _cmd_quote(group).lstrip('\'').rstrip('\'')
        cmd = 'net localgroup "{0}" {1} /add'.format(group, name)
        __salt__['cmd.run_all'](cmd, python_shell=True)

    agrps = set(list_groups(name))
    return len(ugrps - agrps) == 0


def info(name):
    '''
    Return user information

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    '''
    ret = {}
    items = {}
    try:
        items = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error:
        pass

    if items:
        groups = []
        try:
            groups = win32net.NetUserGetLocalGroups(None, name)
        except win32net.error:
            pass

        ret['fullname'] = items['full_name']
        ret['name'] = items['name']
        ret['uid'] = win32security.ConvertSidToStringSid(items['user_sid'])
        ret['passwd'] = items['password']
        ret['comment'] = items['comment']
        ret['active'] = (not bool(items['flags'] & win32netcon.UF_ACCOUNTDISABLE))
        ret['logonscript'] = items['script_path']
        ret['profile'] = items['profile']
        if not ret['profile']:
            ret['profile'] = _get_userprofile_from_registry(name, ret['uid'])
        ret['home'] = items['home_dir']
        if not ret['home']:
            ret['home'] = ret['profile']
        ret['groups'] = groups
        ret['gid'] = ''

    return ret


def _get_userprofile_from_registry(user, sid):
    '''
    In case net user doesn't return the userprofile
    we can get it from the registry
    '''
    profile_dir = __salt__['reg.read_key'](
        'HKEY_LOCAL_MACHINE', u'SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList\\{0}'.format(sid),
        'ProfileImagePath'
    )
    log.debug(u'user {0} with sid={2} profile is located at "{1}"'.format(user, profile_dir, sid))
    return profile_dir


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    '''
    ugrp = set()
    try:
        user = info(name)['groups']
    except KeyError:
        return False
    for group in user:
        ugrp.add(group.strip(' *'))

    return sorted(list(ugrp))


def getent(refresh=False):
    '''
    Return the list of all info for all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    '''
    if 'user.getent' in __context__ and not refresh:
        return __context__['user.getent']

    ret = []
    for user in __salt__['user.list_users']():
        stuff = {}
        user_info = __salt__['user.info'](user)

        stuff['gid'] = ''
        stuff['groups'] = user_info['groups']
        stuff['home'] = user_info['home']
        stuff['name'] = user_info['name']
        stuff['passwd'] = user_info['passwd']
        stuff['shell'] = ''
        stuff['uid'] = user_info['uid']

        ret.append(stuff)

    __context__['user.getent'] = ret
    return ret


def list_users():
    '''
    Return a list of users on Windows
    '''
    res = 0
    users = []
    user_list = []
    dowhile = True
    try:
        while res or dowhile:
            dowhile = False
            (users, _, res) = win32net.NetUserEnum(
                None,
                0,
                win32netcon.FILTER_NORMAL_ACCOUNT,
                res,
                win32netcon.MAX_PREFERRED_LENGTH
            )
            for user in users:
                user_list.append(user['name'])
        return user_list
    except win32net.error:
        pass


def rename(name, new_name):
    '''
    Change the username for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename name new_name
    '''
    current_info = info(name)
    if not current_info:
        raise CommandExecutionError('User {0!r} does not exist'.format(name))
    new_info = info(new_name)
    if new_info:
        raise CommandExecutionError('User {0!r} already exists'.format(new_name))
    cmd = 'wmic useraccount where name="{0}" rename {1}'.format(name, new_name)
    __salt__['cmd.run'](cmd)
    post_info = info(new_name)
    if post_info['name'] != current_info['name']:
        return post_info['name'] == new_name
    return False
