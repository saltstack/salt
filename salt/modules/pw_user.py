# -*- coding: utf-8 -*-
'''
Manage users with the pw command

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Notes:
# ------
#
# Format of the master.passwd file:
#
# - name      User's login name.
# - password  User's encrypted password.
# - uid       User's id.
# - gid       User's login group id.
# - class     User's login class.
# - change    Password change time.
# - expire    Account expiration time.
# - gecos     General information about the user.
# - home_dir  User's home directory.
# - shell     User's login shell.
#
# The usershow command allows viewing of an account in a format that is
# identical to the format used in /etc/master.passwd (with the password field
# replaced with a ‘*’.)
#
# Example:
# % pw usershow -n someuser
# someuser:*:1001:1001::0:0:SomeUser Name:/home/someuser:/bin/sh

# Import python libs
from __future__ import absolute_import
import copy
import logging
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

# Import 3rd party libs
import salt.ext.six as six

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
from salt.utils import locales

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is FreeBSD or DragonFly
    '''
    if HAS_PWD and __grains__['kernel'] in ('FreeBSD', 'DragonFly'):
        return __virtualname__
    return (False, 'The pw_user execution module cannot be loaded: the pwd python module is not available or the system is not FreeBSD.')


def _get_gecos(name):
    '''
    Retrieve GECOS field info and return it in dictionary form
    '''
    try:
        gecos_field = pwd.getpwnam(name).pw_gecos.split(',', 3)
    except KeyError:
        raise CommandExecutionError(
            'User \'{0}\' does not exist'.format(name)
        )
    if not gecos_field:
        return {}
    else:
        # Assign empty strings for any unspecified trailing GECOS fields
        while len(gecos_field) < 4:
            gecos_field.append('')
        return {'fullname': locales.sdecode(gecos_field[0]),
                'roomnumber': locales.sdecode(gecos_field[1]),
                'workphone': locales.sdecode(gecos_field[2]),
                'homephone': locales.sdecode(gecos_field[3])}


def _build_gecos(gecos_dict):
    '''
    Accepts a dictionary entry containing GECOS field names and their values,
    and returns a full GECOS comment string, to be used with pw usermod.
    '''
    return u'{0},{1},{2},{3}'.format(gecos_dict.get('fullname', ''),
                                    gecos_dict.get('roomnumber', ''),
                                    gecos_dict.get('workphone', ''),
                                    gecos_dict.get('homephone', ''))


def _update_gecos(name, key, value):
    '''
    Common code to change a user's GECOS information
    '''
    if not isinstance(value, six.string_types):
        value = str(value)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if value == pre_info[key]:
        return True
    gecos_data = copy.deepcopy(pre_info)
    gecos_data[key] = value
    cmd = ['pw', 'usermod', name, '-c', _build_gecos(gecos_data)]
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    return _get_gecos(name).get(key) == value


def add(name,
        uid=None,
        gid=None,
        groups=None,
        home=None,
        shell=None,
        unique=True,
        fullname='',
        roomnumber='',
        workphone='',
        homephone='',
        createhome=True,
        loginclass=None,
        **kwargs):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    if salt.utils.is_true(kwargs.pop('system', False)):
        log.warning('pw_user module does not support the \'system\' argument')
    if kwargs:
        log.warning('Invalid kwargs passed to user.add')

    if isinstance(groups, six.string_types):
        groups = groups.split(',')
    cmd = ['pw', 'useradd']
    if uid:
        cmd.extend(['-u', uid])
    if gid:
        cmd.extend(['-g', gid])
    if groups:
        cmd.extend(['-G', ','.join(groups)])
    if home is not None:
        cmd.extend(['-d', home])
    if createhome is True:
        cmd.append('-m')
    if loginclass:
        cmd.extend(['-L', loginclass])
    if shell:
        cmd.extend(['-s', shell])
    if not salt.utils.is_true(unique):
        cmd.append('-o')
    gecos_field = _build_gecos({'fullname': fullname,
                                'roomnumber': roomnumber,
                                'workphone': workphone,
                                'homephone': homephone})
    cmd.extend(['-c', gecos_field])
    cmd.extend(['-n', name])
    return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


def delete(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name remove=True force=True
    '''
    if salt.utils.is_true(force):
        log.error('pw userdel does not support force-deleting user while '
                  'user is logged in')
    cmd = ['pw', 'userdel']
    if remove:
        cmd.append('-r')
    cmd.extend(['-n', name])
    return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


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
        ret.append(info(data.pw_name))
    __context__['user.getent'] = ret
    return ret


def chuid(name, uid):
    '''
    Change the uid for a named user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chuid foo 4376
    '''
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError(
            'User \'{0}\' does not exist'.format(name)
        )
    if uid == pre_info['uid']:
        return True
    cmd = ['pw', 'usermod', '-u', uid, '-n', name]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('uid') == uid


def chgid(name, gid):
    '''
    Change the default group of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    '''
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError(
            'User \'{0}\' does not exist'.format(name)
        )
    if gid == pre_info['gid']:
        return True
    cmd = ['pw', 'usermod', '-g', gid, '-n', name]
    __salt__['cmd.run'](cmd, python_shell=False)
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
        raise CommandExecutionError(
            'User \'{0}\' does not exist'.format(name)
        )
    if shell == pre_info['shell']:
        return True
    cmd = ['pw', 'usermod', '-s', shell, '-n', name]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('shell') == shell


def chhome(name, home, persist=False):
    '''
    Set a new home directory for an existing user

    name
        Username to modify

    home
        New home directory to set

    persist : False
        Set to ``True`` to prevent configuration files in the new home
        directory from being overwritten by the files from the skeleton
        directory.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /home/users/foo True
    '''
    pre_info = info(name)
    if not pre_info:
        raise CommandExecutionError(
            'User \'{0}\' does not exist'.format(name)
        )
    if home == pre_info['home']:
        return True
    cmd = ['pw', 'usermod', name, '-d', home]
    if persist:
        cmd.append('-m')
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('home') == home


def chgroups(name, groups, append=False):
    '''
    Change the groups to which a user belongs

    name
        Username to modify

    groups
        List of groups to set for the user. Can be passed as a comma-separated
        list or a Python list.

    append : False
        Set to ``True`` to append these groups to the user's existing list of
        groups. Otherwise, the specified groups will replace any existing
        groups for the user.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root True
    '''
    if isinstance(groups, six.string_types):
        groups = groups.split(',')
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True
    if append:
        groups += ugrps
    cmd = ['pw', 'usermod', '-G', ','.join(groups), '-n', name]
    return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


def chfullname(name, fullname):
    '''
    Change the user's Full Name

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname foo "Foo Bar"
    '''
    return _update_gecos(name, 'fullname', fullname)


def chroomnumber(name, roomnumber):
    '''
    Change the user's Room Number

    CLI Example:

    .. code-block:: bash

        salt '*' user.chroomnumber foo 123
    '''
    return _update_gecos(name, 'roomnumber', roomnumber)


def chworkphone(name, workphone):
    '''
    Change the user's Work Phone

    CLI Example:

    .. code-block:: bash

        salt '*' user.chworkphone foo "7735550123"
    '''
    return _update_gecos(name, 'workphone', workphone)


def chhomephone(name, homephone):
    '''
    Change the user's Home Phone

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhomephone foo "7735551234"
    '''
    return _update_gecos(name, 'homephone', homephone)


def chloginclass(name, loginclass, root=None):
    '''
    Change the default login class of the user

    .. versionadded:: 2016.3.5

    CLI Example:

    .. code-block:: bash

        salt '*' user.chloginclass foo staff
    '''
    if loginclass == get_loginclass(name):
        return True

    cmd = ['pw', 'usermod', '-L', '{0}'.format(loginclass),
           '-n', '{0}'.format(name)]

    __salt__['cmd.run'](cmd, python_shell=False)

    return get_loginclass(name) == loginclass


def info(name):
    '''
    Return user information

    CLI Example:

    .. code-block:: bash

        salt '*' user.info root
    '''
    ret = {}
    try:
        data = pwd.getpwnam(name)
        ret['gid'] = data.pw_gid
        ret['groups'] = list_groups(name)
        ret['home'] = data.pw_dir
        ret['name'] = data.pw_name
        ret['passwd'] = data.pw_passwd
        ret['shell'] = data.pw_shell
        ret['uid'] = data.pw_uid
        # Put GECOS info into a list
        gecos_field = data.pw_gecos.split(',', 3)
        # Assign empty strings for any unspecified GECOS fields
        while len(gecos_field) < 4:
            gecos_field.append('')
        ret['fullname'] = gecos_field[0]
        ret['roomnumber'] = gecos_field[1]
        ret['workphone'] = gecos_field[2]
        ret['homephone'] = gecos_field[3]
    except KeyError:
        return {}
    return ret


def get_loginclass(name):
    '''
    Get the login class of the user

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.get_loginclass foo

    '''

    userinfo = __salt__['cmd.run_stdout'](['pw', 'usershow', '-n', name])
    userinfo = userinfo.split(':')

    return {'loginclass': userinfo[4] if len(userinfo) == 10 else ''}


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    '''
    return salt.utils.get_group_list(name)


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
    cmd = ['pw', 'usermod', '-l', new_name, '-n', name]
    __salt__['cmd.run'](cmd)
    post_info = info(new_name)
    if post_info['name'] != current_info['name']:
        return post_info['name'] == new_name
    return False
