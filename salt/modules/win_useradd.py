# -*- coding: utf-8 -*-
'''
Module for managing Windows Users

:depends:
        - pywintypes
        - win32api
        - win32net
        - win32netcon
        - win32profile
        - win32security
        - win32ts

NOTE: This currently only works with local user accounts, not domain accounts
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils
from salt.ext.six import string_types
from salt.exceptions import CommandExecutionError
import logging

log = logging.getLogger(__name__)

try:
    import pywintypes
    import win32api
    import win32net
    import win32netcon
    import win32profile
    import win32security
    import win32ts
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is Windows
    '''
    if HAS_WIN32NET_MODS and salt.utils.is_windows():
        return __virtualname__
    return False


def add(name,
        password=None,
        fullname=False,
        description=None,
        groups=None,
        home=None,
        homedrive=None,
        profile=None,
        logonscript=None):
    '''
    Add a user to the minion.

    :param name: str
    User name

    :param password: str
    User's password in plain text.

    :param fullname: str
    The user's full name.

    :param description: str
    A brief description of the user account.

    :param groups: list
    A list of groups to add the user to.

    :param home: str
    The path to the user's home directory.

    :param homedrive: str
    The drive letter to assign to the home directory. Must be the Drive Letter
    followed by a colon. ie: U:

    :param profile: str
    An explicit path to a profile. Can be a UNC or a folder on the system. If
    left blank, windows uses it's default profile directory.

    :param logonscript: str
    Path to a login script to run when the user logs on.

    :return: bool
    True if successful. False is unsuccessful.

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name password
    '''
    user_info = {}
    if name:
        user_info['name'] = name
    else:
        return False
    user_info['password'] = password
    user_info['priv'] = win32netcon.USER_PRIV_USER
    user_info['home_dir'] = home
    user_info['comment'] = description
    user_info['flags'] = win32netcon.UF_SCRIPT
    user_info['script_path'] = logonscript

    try:
        win32net.NetUserAdd(None, 1, user_info)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('Failed to create user {0}'.format(name))
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    update(name=name,
           homedrive=homedrive,
           profile=profile,
           fullname=fullname)

    ret = chgroups(name, groups) if groups else True

    return ret


def update(name,
           password=None,
           fullname=None,
           description=None,
           home=None,
           homedrive=None,
           logonscript=None,
           profile=None):
    r'''
    Updates settings for the windows user. Name is the only required parameter.
    Settings will only be changed if the parameter is passed a value.

    .. versionadded:: 2015.8.0

    :param name: str
    The user name to update.

    :param password: str
    New user password in plain text.

    :param fullname: str
    The user's full name.

    :param description: str
    A brief description of the user account.

    :param home: str
    The path to the user's home directory.

    :param homedrive: str
    The drive letter to assign to the home directory. Must be the Drive Letter
    followed by a colon. ie: U:

    :param logonscript: str
    The path to the logon script.

    :param profile: str
    The path to the user's profile directory.

    :return: bool
    True if successful. False is unsuccessful.

    CLI Example:

    .. code-block:: bash

        salt '*' user.update bob password=secret profile=C:\Users\Bob
                 home=\\server\homeshare\bob homedrive=U:
    '''

    # Make sure the user exists
    # Return an object containing current settings for the user
    try:
        user_info = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('Failed to update user {0}'.format(name))
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    # Check parameters to update
    # Update the user object with new settings
    if password:
        user_info['password'] = password
    if home:
        user_info['home_dir'] = home
    if homedrive:
        user_info['home_dir_drive'] = homedrive
    if description:
        user_info['comment'] = description
    if logonscript:
        user_info['script_path'] = logonscript
    if fullname:
        user_info['full_name'] = fullname
    if profile:
        user_info['profile'] = profile

    # Apply new settings
    try:
        win32net.NetUserSetInfo(None, name, 4, user_info)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('Failed to update user {0}'.format(name))
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    return True


def delete(name,
           purge=False,
           force=False):
    '''
    Remove a user from the minion

    :param name:
    The name of the user to delete

    :param purge:
    Boolean value indicating that the user profile should also be removed when
    the user account is deleted. If set to True the profile will be removed.

    :param force:
    Boolean value indicating that the user account should be deleted even if the
    user is logged in. True will log the user out and delete user.

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name
    '''
    # Check if the user exists
    try:
        user_info = win32net.NetUserGetInfo(None, name, 4)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('User not found: {0}'.format(name))
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    # Check if the user is logged in
    # Return a list of logged in users
    try:
        sess_list = win32ts.WTSEnumerateSessions()
    except win32ts.error as exc:
        (number, context, message) = exc
        log.error('No logged in users found')
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))

    # Is the user one that is logged in
    logged_in = False
    session_id = None
    for sess in sess_list:
        if win32ts.WTSQuerySessionInformation(None, sess['SessionId'], win32ts.WTSUserName) == name:
            session_id = sess['SessionId']
            logged_in = True

    # If logged in and set to force, log the user out and continue
    # If logged in and not set to force, return false
    if logged_in:
        if force:
            try:
                win32ts.WTSLogoffSession(win32ts.WTS_CURRENT_SERVER_HANDLE, session_id, True)
            except win32ts.error as exc:
                (number, context, message) = exc
                log.error('User not found: {0}'.format(name))
                log.error('nbr: {0}'.format(number))
                log.error('ctx: {0}'.format(context))
                log.error('msg: {0}'.format(message))
                return False
        else:
            log.error('User {0} is currently logged in.'.format(name))
            return False

    # Remove the User Profile directory
    if purge:
        try:
            sid = getUserSid(name)
            win32profile.DeleteProfile(sid)
        except pywintypes.error as exc:
            (number, context, message) = exc
            if number == 2:  # Profile Folder Not Found
                pass
            else:
                log.error('Failed to remove profile for {0}'.format(name))
                log.error('nbr: {0}'.format(number))
                log.error('ctx: {0}'.format(context))
                log.error('msg: {0}'.format(message))
                return False

    # And finally remove the user account
    try:
        win32net.NetUserDel(None, name)
    except win32net.error as exc:
        (number, context, message) = exc
        log.error('Failed to delete user {0}'.format(name))
        log.error('nbr: {0}'.format(number))
        log.error('ctx: {0}'.format(context))
        log.error('msg: {0}'.format(message))
        return False

    return True


def getUserSid(username):
    domain = win32api.GetComputerName()
    if username.find(u'\\') != -1:
        domain = username.split(u'\\')[0]
        username = username.split(u'\\')[-1]
    domain = domain.upper()
    return win32security.ConvertSidToStringSid(win32security.LookupAccountName(None, domain + u'\\' + username)[0])


def setpassword(name, password):
    '''
    Set a user's password

    CLI Example:

    .. code-block:: bash

        salt '*' user.setpassword name password
    '''
    return update(name=name, password=password)


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
        'net localgroup {0} {1} /add'.format(group, name)
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
        'net localgroup {0} {1} /delete'.format(group, name)
    )
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

    if not update(name=name, home=home):
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
    return update(name=name, profile=profile)


def chfullname(name, fullname):
    '''
    Change the full name of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname user 'First Last'
    '''
    return update(name=name, fullname=fullname)


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
                __salt__['cmd.retcode'](
                        'net localgroup {0} {1} /delete'.format(group, name))

    for group in groups:
        if group in ugrps:
            continue
        __salt__['cmd.retcode'](
                'net localgroup {0} {1} /add'.format(group, name))
    agrps = set(list_groups(name))
    return len(ugrps - agrps) == 0


def info(name):
    '''
    Return user information

    :param name: str
    Username for which to display information

    :returns: dict
    A dictionary containing user information
    - fullname
    - username
    - uid
    - passwd (will always return None)
    - comment (same as description, left here for backwards compatibility)
    - description
    - active
    - logonscript
    - profile
    - home
    - homedrive
    - groups
    - gid

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
        ret['description'] = items['comment']
        ret['active'] = (not bool(items['flags'] & win32netcon.UF_ACCOUNTDISABLE))
        ret['logonscript'] = items['script_path']
        ret['profile'] = items['profile']
        if not ret['profile']:
            ret['profile'] = _get_userprofile_from_registry(name, ret['uid'])
        ret['home'] = items['home_dir']
        ret['homedrive'] = items['home_dir_drive']
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
