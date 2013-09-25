# -*- coding: utf-8 -*-
'''
Manage Windows users with the net user command

NOTE: This currently only works with local user accounts, not domain accounts
'''

# Import salt libs
import salt.utils
from salt._compat import string_types

try:
    import win32net
    import win32netcon
    HAS_WIN32NET_MODS = True
except ImportError:
    HAS_WIN32NET_MODS = False


def __virtual__():
    '''
    Set the user module if the kernel is Windows
    '''
    if HAS_WIN32NET_MODS is True and salt.utils.is_windows():
        return 'user'
    return False


def add(name,
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
    ret = __salt__['cmd.run_all']('net user {0} {1}'.format(name, password))
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

    if __salt__['cmd.retcode']('net user {0} /homedir:{1}'.format(
            name, home)) != 0:
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

    if fullname == pre_info['fullname']:
        return True
    if __salt__['cmd.retcode']('net user {0} /fullname:"{1}"'.format(
            name, fullname)) != 0:
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

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    '''
    ret = {}
    items = {}
    for line in __salt__['cmd.run']('net user {0}'.format(name)).splitlines():
        if 'name could not be found' in line:
            return {}
        if 'successfully' not in line:
            comps = line.split('    ', 1)
            if not len(comps) > 1:
                continue
            items[comps[0].strip()] = comps[1].strip()
    grouplist = []
    groups = items['Local Group Memberships'].split('  ')
    for group in groups:
        if not group:
            continue
        grouplist.append(group.strip(' *'))

    ret['fullname'] = items['Full Name']
    ret['name'] = items['User name']
    ret['comment'] = items['Comment']
    ret['active'] = items['Account active']
    ret['logonscript'] = items['Logon script']
    ret['profile'] = items['User profile']
    ret['home'] = items['Home directory']
    ret['groups'] = grouplist
    ret['gid'] = ''

    return ret


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


def getent():
    '''
    Return the list of all info for all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.getent
    '''
    if 'user.getent' in __context__:
        return __context__['user.getent']

    ret = []
    users = []
    startusers = False
    lines = __salt__['cmd.run']('net user').splitlines()
    for line in lines:
        if '----------' in line:
            startusers = True
            continue
        if startusers:
            if 'successfully' not in line:
                comps = line.split()
                users += comps
                ##if not len(comps) > 1:
                    #continue
                #items[comps[0].strip()] = comps[1].strip()
    #return users
    for user in users:
        stuff = {}
        user_info = __salt__['user.info'](user)
        uid = __salt__['file.user_to_uid'](user_info['name'])

        stuff['gid'] = ''
        stuff['groups'] = user_info['groups']
        stuff['home'] = user_info['home']
        stuff['name'] = user_info['name']
        stuff['passwd'] = ''
        stuff['shell'] = ''
        stuff['uid'] = uid

        ret.append(stuff)

    __context__['user.getent'] = ret
    return ret


def list_users():
    '''
    Return a list of users on Windows
    '''
    res = 1
    users = []
    user_list = []
    try:
        while res:
            (users, _, res) = win32net.NetUserEnum(
                'localhost',
                3,
                win32netcon.FILTER_NORMAL_ACCOUNT,
                res,
                win32netcon.MAX_PREFERRED_LENGTH
            )
            for user in users:
                user_list.append(user['name'])
        return user_list
    except win32net.error:
        pass
