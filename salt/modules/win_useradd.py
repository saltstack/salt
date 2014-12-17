# -*- coding: utf-8 -*-
'''
Manage Windows users with the net user command

NOTE: This currently only works with local user accounts, not domain accounts
'''

# Import salt libs
import salt.utils
from salt._compat import string_types
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
        cmd = ['net', 'user', name, password, '/add', '/y']
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    else:
        cmd = ['net', 'user', name, '/add']
        ret = __salt__['cmd.run_all'](cmd, python_shell=False)
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
    cmd = ['net', 'user', name, '/delete']
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    return ret['retcode'] == 0


def setpassword(name, password):
    '''
    Set a user's password

    CLI Example:

    .. code-block:: bash

        salt '*' user.setpassword name password
    '''
    ret = __salt__['cmd.run_all'](
        ['net', 'user', name, password],
        output_loglevel='quiet',
        python_shell=False
    )
    return ret['retcode'] == 0


def addgroup(name, group):
    '''
    Add user to a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.addgroup username groupname
    '''
    user = info(name)
    if not user:
        return False
    if group in user['groups']:
        return True
    ret = __salt__['cmd.run_all'](
        ['net', 'localgroup', group, name, '/add'],
        python_shell=False
    )
    return ret['retcode'] == 0


def removegroup(name, group):
    '''
    Remove user from a group

    CLI Example:

    .. code-block:: bash

        salt '*' user.removegroup username groupname
    '''
    user = info(name)

    if not user:
        return False

    if group not in user['groups']:
        return True

    ret = __salt__['cmd.run_all'](
        ['net', 'localgroup', group, name, '/delete'],
        python_shell=False
    )
    return ret['retcode'] == 0


def chhome(name, home):
    '''
    Change the home directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo \\\\fileserver\\home\\foo
    '''
    pre_info = info(name)

    if not pre_info:
        return False

    if home == pre_info['home']:
        return True

    cmd = ['net', 'user', name, '/homedir:{0}'.format(home)]
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        return False

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
    cmd = ['net', 'user', name, '/profilepath:{0}'.format(profile)]
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
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

    if fullname == pre_info['fullname']:
        return True
    cmd = ['net', 'user', name, '/fullname:{0}'.format(fullname)]
    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        return False

    post_info = info(name)
    if post_info['fullname'] != pre_info['fullname']:
        return post_info['fullname'] == fullname

    return False


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

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

    if not append:
        for group in ugrps:
            if group not in groups:
                cmd = ['net', 'localgroup', group, name, '/delete']
                __salt__['cmd.retcode'](cmd, python_shell=False)

    for group in groups:
        if group in ugrps:
            continue
        cmd = ['net', 'localgroup', group, name, '/add']
        __salt__['cmd.retcode'](cmd, python_shell=False)
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
