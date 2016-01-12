# -*- coding: utf-8 -*-
'''
Manage users on Mac OS 10.7+
'''

# Import python libs
from __future__ import absolute_import
try:
    import pwd
except ImportError:
    pass
import logging
import time

# Import 3rdp-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.six import string_types

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    if (__grains__.get('kernel') != 'Darwin' or
            __grains__['osrelease_info'] < (10, 7)):
        return False
    else:
        return __virtualname__


def _flush_dscl_cache():
    '''
    Flush dscl cache
    '''
    __salt__['cmd.run'](['dscacheutil', '-flushcache'], python_shell=False)


def _dscl(cmd, ctype='create'):
    '''
    Run a dscl -create command
    '''
    if __grains__['osrelease_info'] < (10, 8):
        source, noderoot = '.', ''
    else:
        source, noderoot = 'localhost', '/Local/Default'
    if noderoot:
        cmd[0] = noderoot + cmd[0]

    return __salt__['cmd.run_all'](
        ['dscl', source, '-' + ctype] + cmd,
        output_loglevel='quiet' if ctype == 'passwd' else 'debug',
        python_shell=False
    )


def _first_avail_uid():
    uids = set(x.pw_uid for x in pwd.getpwall())
    for idx in range(501, 2 ** 24):
        if idx not in uids:
            return idx


def add(name,
        uid=None,
        gid=None,
        groups=None,
        home=None,
        shell=None,
        fullname=None,
        createhome=True,
        **kwargs):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    if info(name):
        raise CommandExecutionError('User \'{0}\' already exists'.format(name))

    if salt.utils.contains_whitespace(name):
        raise SaltInvocationError('Username cannot contain whitespace')

    if uid is None:
        uid = _first_avail_uid()
    if gid is None:
        gid = 20  # gid 20 == 'staff', the default group
    if home is None:
        home = '/Users/{0}'.format(name)
    if shell is None:
        shell = '/bin/bash'
    if fullname is None:
        fullname = ''

    if not isinstance(uid, int):
        raise SaltInvocationError('uid must be an integer')
    if not isinstance(gid, int):
        raise SaltInvocationError('gid must be an integer')

    name_path = '/Users/{0}'.format(name)
    _dscl([name_path, 'UniqueID', uid])
    _dscl([name_path, 'PrimaryGroupID', gid])
    _dscl([name_path, 'UserShell', shell])
    _dscl([name_path, 'NFSHomeDirectory', home])
    _dscl([name_path, 'RealName', fullname])

    # Make sure home directory exists
    __salt__['file.mkdir'](name)

    # dscl buffers changes, sleep before setting group membership
    time.sleep(1)
    if groups:
        chgroups(name, groups)
    return True


def delete(name, *args):
    '''
    Remove a user from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete foo
    '''
    ### NOTE: *args isn't used here but needs to be included in this function
    ### for compatibility with the user.absent state
    if salt.utils.contains_whitespace(name):
        raise SaltInvocationError('Username cannot contain whitespace')
    if not info(name):
        return True
    # Remove from any groups other than primary group. Needs to be done since
    # group membership is managed separately from users and an entry for the
    # user will persist even after the user is removed.
    chgroups(name, ())
    return _dscl(['/Users/{0}'.format(name)], ctype='delete')['retcode'] == 0


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
    for data in pwd.getpwall():
        ret.append(_format_info(data))
    __context__['user.getent'] = ret
    return ret


def chuid(name, uid):
    '''
    Change the uid for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chuid foo 4376
    '''
    if not isinstance(uid, int):
        raise SaltInvocationError('uid must be an integer')
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if uid == pre_info['uid']:
        return True
    _dscl(
        ['/Users/{0}'.format(name), 'UniqueID', pre_info['uid'], uid],
        ctype='change'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get('uid') == uid


def chgid(name, gid):
    '''
    Change the default group of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    '''
    if not isinstance(gid, int):
        raise SaltInvocationError('gid must be an integer')
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if gid == pre_info['gid']:
        return True
    _dscl(
        ['/Users/{0}'.format(name), 'PrimaryGroupID', pre_info['gid'], gid],
        ctype='change'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get('gid') == gid


def chshell(name, shell):
    '''
    Change the default shell of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chshell foo /bin/zsh
    '''
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if shell == pre_info['shell']:
        return True
    _dscl(
        ['/Users/{0}'.format(name), 'UserShell', pre_info['shell'], shell],
        ctype='change'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get('shell') == shell


def chhome(name, home):
    '''
    Change the home directory of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /Users/foo
    '''
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if home == pre_info['home']:
        return True
    _dscl(
        ['/Users/{0}'.format(name), 'NFSHomeDirectory',
         pre_info['home'], home],
        ctype='change'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(name).get('home') == home


def chfullname(name, fullname):
    '''
    Change the user's Full Name

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname foo 'Foo Bar'
    '''
    if isinstance(fullname, str):
        fullname.decode('utf-8')
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if isinstance(pre_info['fullname'], str):
        pre_info['fullname'] = pre_info['fullname'].decode('utf-8')
    if fullname == pre_info['fullname']:
        return True
    _dscl(
        ['/Users/{0}'.format(name), 'RealName', fullname],
        # use a 'create' command, because a 'change' command would fail if
        # current fullname is an empty string. The 'create' will just overwrite
        # this field.
        ctype='create'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)

    current = info(name).get('fullname')
    if isinstance(current, str):
        current.decode('utf-8')
    return current == fullname


def chgroups(name, groups, append=False):
    '''
    Change the groups to which the user belongs. Note that the user's primary
    group does not have to be one of the groups passed, membership in the
    user's primary group is automatically assumed.

    groups
        Groups to which the user should belong, can be passed either as a
        python list or a comma-separated string

    append
        Instead of removing user from groups not included in the ``groups``
        parameter, just add user to any groups for which they are not members

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root
    '''
    ### NOTE: **args isn't used here but needs to be included in this
    ### function for compatibility with the user.present state
    uinfo = info(name)
    if not uinfo:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    if isinstance(groups, string_types):
        groups = groups.split(',')

    bad_groups = [x for x in groups if salt.utils.contains_whitespace(x)]
    if bad_groups:
        raise SaltInvocationError(
            'Invalid group name(s): {0}'.format(', '.join(bad_groups))
        )
    ugrps = set(list_groups(name))
    desired = set(str(x) for x in groups if bool(str(x)))
    primary_group = __salt__['file.gid_to_group'](uinfo['gid'])
    if primary_group:
        desired.add(primary_group)
    if ugrps == desired:
        return True
    # Add groups from which user is missing
    for group in desired - ugrps:
        _dscl(
            ['/Groups/{0}'.format(group), 'GroupMembership', name],
            ctype='append'
        )
    if not append:
        # Remove from extra groups
        for group in ugrps - desired:
            _dscl(
                ['/Groups/{0}'.format(group), 'GroupMembership', name],
                ctype='delete'
            )
    time.sleep(1)
    return set(list_groups(name)) == desired


def info(name):
    '''
    Return user information

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    '''
    try:
        data = pwd.getpwnam(name)
    except KeyError:
        return {}
    else:
        return _format_info(data)


def _format_info(data):
    '''
    Return user information in a pretty way
    '''
    return {'gid': data.pw_gid,
            'groups': list_groups(data.pw_name),
            'home': data.pw_dir,
            'name': data.pw_name,
            'shell': data.pw_shell,
            'uid': data.pw_uid,
            'fullname': data.pw_gecos}


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    '''
    groups = [group for group in salt.utils.get_group_list(name)
              if not group.startswith('_')]
    return groups


def list_users():
    '''
    Return a list of all users

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_users
    '''
    return sorted([user.pw_name for user in pwd.getpwall()])


def rename(name, new_name):
    '''
    Change the username for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.rename name new_name
    '''
    current_info = info(name)
    if not current_info:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(name))
    new_info = info(new_name)
    if new_info:
        raise CommandExecutionError(
            'User \'{0}\' already exists'.format(new_name)
        )
    _dscl(
        ['/Users/{0}'.format(name), 'RecordName', name, new_name],
        ctype='change'
    )
    # dscl buffers changes, sleep 1 second before checking if new value
    # matches desired value
    time.sleep(1)
    return info(new_name).get('RecordName') == new_name
