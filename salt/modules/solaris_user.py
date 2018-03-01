# -*- coding: utf-8 -*-
'''
Manage users with the useradd command

.. important::

    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.

'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False
import copy
import logging

# Import salt libs
import salt.utils.data
import salt.utils.user
from salt.ext import six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is SunOS
    '''
    if __grains__['kernel'] == 'SunOS' and HAS_PWD:
        return __virtualname__
    return (False, 'The solaris_user execution module failed to load: '
            'only available on Solaris systems with pwd module installed.')


def _get_gecos(name):
    '''
    Retrieve GECOS field info and return it in dictionary form
    '''
    gecos_field = pwd.getpwnam(name).pw_gecos.split(',', 3)
    if not gecos_field:
        return {}
    else:
        # Assign empty strings for any unspecified trailing GECOS fields
        while len(gecos_field) < 4:
            gecos_field.append('')
        return {'fullname': six.text_type(gecos_field[0]),
                'roomnumber': six.text_type(gecos_field[1]),
                'workphone': six.text_type(gecos_field[2]),
                'homephone': six.text_type(gecos_field[3])}


def _build_gecos(gecos_dict):
    '''
    Accepts a dictionary entry containing GECOS field names and their values,
    and returns a full GECOS comment string, to be used with usermod.
    '''
    return '{0},{1},{2},{3}'.format(gecos_dict.get('fullname', ''),
                                    gecos_dict.get('roomnumber', ''),
                                    gecos_dict.get('workphone', ''),
                                    gecos_dict.get('homephone', ''))


def _update_gecos(name, key, value):
    '''
    Common code to change a user's GECOS information
    '''
    if not isinstance(value, six.string_types):
        value = six.text_type(value)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if value == pre_info[key]:
        return True
    gecos_data = copy.deepcopy(pre_info)
    gecos_data[key] = value
    cmd = ['usermod', '-c', _build_gecos(gecos_data), name]
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
        **kwargs):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    if salt.utils.data.is_true(kwargs.pop('system', False)):
        log.warning('solaris_user module does not support the \'system\' '
                    'argument')
    if kwargs:
        log.warning('Invalid kwargs passed to user.add')

    if isinstance(groups, six.string_types):
        groups = groups.split(',')
    cmd = ['useradd']
    if shell:
        cmd.extend(['-s', shell])
    if uid:
        cmd.extend(['-u', uid])
    if gid:
        cmd.extend(['-g', gid])
    if groups:
        cmd.extend(['-G', ','.join(groups)])
    if createhome:
        cmd.append('-m')
    if home is not None:
        cmd.extend(['-d', home])
    if not unique:
        cmd.append('-o')
    cmd.append(name)

    if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
        return False
    else:
        # At this point, the user was successfully created, so return true
        # regardless of the outcome of the below functions. If there is a
        # problem wth changing any of the user's info below, it will be raised
        # in a future highstate call. If anyone has a better idea on how to do
        # this, feel free to change it, but I didn't think it was a good idea
        # to return False when the user was successfully created since A) the
        # user does exist, and B) running useradd again would result in a
        # nonzero exit status and be interpreted as a False result.
        if fullname:
            chfullname(name, fullname)
        if roomnumber:
            chroomnumber(name, roomnumber)
        if workphone:
            chworkphone(name, workphone)
        if homephone:
            chhomephone(name, homephone)
        return True


def delete(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name remove=True force=True
    '''
    if salt.utils.data.is_true(force):
        log.warning(
            'userdel does not support force-deleting user while user is '
            'logged in'
        )
    cmd = ['userdel']
    if remove:
        cmd.append('-r')
    cmd.append(name)
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
    cmd = ['usermod', '-u', uid, name]
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
    cmd = ['usermod', '-g', gid, name]
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
    cmd = ['usermod', '-s', shell, name]
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
    cmd = ['usermod', '-d', home]
    if persist:
        cmd.append('-m')
    cmd.append(name)
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
        groups.update(ugrps)
    cmd = ['usermod', '-G', ','.join(groups), name]
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


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example:

    .. code-block:: bash

        salt '*' user.list_groups foo
    '''
    return salt.utils.user.get_group_list(name)


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
    cmd = ['usermod', '-l', new_name, name]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(new_name).get('name') == new_name
