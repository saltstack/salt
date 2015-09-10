# -*- coding: utf-8 -*-
'''
Manage users with the useradd command
'''
from __future__ import absolute_import

# Import python libs
import re

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False
import logging
import copy

# Import salt libs
import salt.utils
from salt.ext import six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

RETCODE_12_ERROR_REGEX = re.compile(
    r'userdel(.*)warning(.*)/var/mail(.*)No such file or directory'
)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is Linux, OpenBSD or NetBSD
    '''

    if HAS_PWD and __grains__['kernel'] in ('Linux', 'OpenBSD', 'NetBSD'):
        return __virtualname__
    return False


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
        return {'fullname': str(gecos_field[0]),
                'roomnumber': str(gecos_field[1]),
                'workphone': str(gecos_field[2]),
                'homephone': str(gecos_field[3])}


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
        value = str(value)
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
        system=False,
        fullname='',
        roomnumber='',
        workphone='',
        homephone='',
        createhome=True,
        loginclass=None):
    '''
    Add a user to the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    cmd = ['useradd']
    if shell:
        cmd.extend(['-s', shell])
    if uid not in (None, ''):
        cmd.extend(['-u', str(uid)])
    if gid not in (None, ''):
        cmd.extend(['-g', str(gid)])
    elif groups is not None and name in groups:
        defs_file = '/etc/login.defs'
        if __grains__['kernel'] != 'OpenBSD':
            try:
                with salt.utils.fopen(defs_file) as fp_:
                    for line in fp_:
                        if 'USERGROUPS_ENAB' not in line[:15]:
                            continue

                        if 'yes' in line:
                            cmd.extend([
                                '-g', str(__salt__['file.group_to_gid'](name))
                            ])

                        # We found what we wanted, let's break out of the loop
                        break
            except OSError:
                log.debug(
                    'Error reading ' + defs_file,
                    exc_info_on_loglevel=logging.DEBUG
                )
        else:
            usermgmt_file = '/etc/usermgmt.conf'
            try:
                with salt.utils.fopen(usermgmt_file) as fp_:
                    for line in fp_:
                        if 'group' not in line[:5]:
                            continue

                        for val in line.split(' '):
                            cmd.extend([
                                '-g', str(val[1])
                            ])

                        # We found what we wanted, let's break out of the loop
                        break
            except OSError:
                # /etc/usermgmt.conf not present: defaults will be used
                pass

    if salt.utils.is_true(createhome):
        if createhome:
            cmd.append('-m')
        elif (__grains__['kernel'] != 'NetBSD'
                and __grains__['kernel'] != 'OpenBSD'):
            cmd.append('-M')

    if home is not None:
        cmd.extend(['-d', home])

    if not unique:
        cmd.append('-o')

    if (system
        and __grains__['kernel'] != 'NetBSD'
        and __grains__['kernel'] != 'OpenBSD'):
        cmd.append('-r')

    if __grains__['kernel'] == 'OpenBSD':
        if loginclass is not None:
            cmd.extend(['-L', loginclass])

    cmd.append(name)

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] != 0:
        return False

    # At this point, the user was successfully created, so return true
    # regardless of the outcome of the below functions. If there is a
    # problem wth changing any of the user's info below, it will be raised
    # in a future highstate call. If anyone has a better idea on how to do
    # this, feel free to change it, but I didn't think it was a good idea
    # to return False when the user was successfully created since A) the
    # user does exist, and B) running useradd again would result in a
    # nonzero exit status and be interpreted as a False result.
    if groups:
        chgroups(name, groups)
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
    cmd = ['userdel']

    if remove:
        cmd.append('-r')

    if force and __grains__['kernel'] != 'OpenBSD':
        cmd.append('-f')

    cmd.append(name)

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    if ret['retcode'] == 0:
        # Command executed with no errors
        return True

    if ret['retcode'] == 12:
        # There's a known bug in Debian based distributions, at least, that
        # makes the command exit with 12, see:
        #  https://bugs.launchpad.net/ubuntu/+source/shadow/+bug/1023509
        if __grains__['os_family'] not in ('Debian',):
            return False

        if RETCODE_12_ERROR_REGEX.match(ret['stderr']) is not None:
            # We've hit the bug, let's log it and not fail
            log.debug(
                'While the userdel exited with code 12, this is a known bug on '
                'debian based distributions. See http://goo.gl/HH3FzT'
            )
            return True

    return False


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
    pre_info = info(name)
    if uid == pre_info['uid']:
        return True
    cmd = ['usermod', '-u', '{0}'.format(uid), name]
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
    if gid == pre_info['gid']:
        return True
    cmd = ['usermod', '-g', '{0}'.format(gid), name]
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
    if shell == pre_info['shell']:
        return True
    cmd = ['usermod', '-s', shell, name]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('shell') == shell


def chhome(name, home, persist=False):
    '''
    Change the home directory of the user, pass True for persist to move files
    to the new home directory if the old home directory exist.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /home/users/foo True
    '''
    pre_info = info(name)
    if home == pre_info['home']:
        return True
    cmd = ['usermod', '-d', '{0}'.format(home)]
    if persist and __grains__['kernel'] != 'OpenBSD':
        cmd.append('-m')
    cmd.append(name)
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('home') == home


def chgroups(name, groups, append=False):
    '''
    Change the groups to which this user belongs

    name
        User to modify

    groups
        Groups to set for the user

    append : False
        If ``True``, append the specified group(s). Otherwise, this function
        will replace the user's groups with the specified group(s).

    CLI Examples:

    .. code-block:: bash

        salt '*' user.chgroups foo wheel,root
        salt '*' user.chgroups foo wheel,root append=True
    '''
    if isinstance(groups, six.string_types):
        groups = groups.split(',')
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True
    cmd = ['usermod']
    if __grains__['kernel'] != 'OpenBSD':
        if append:
            cmd.append('-a')
    else:
        if append:
            cmd.append('-G')
        else:
            cmd.append('-S')
    if __grains__['kernel'] != 'OpenBSD':
        cmd.append('-G')
    cmd.extend([','.join(groups), name])
    result = __salt__['cmd.run_all'](cmd, python_shell=False)
    # try to fallback on gpasswd to add user to localgroups
    # for old lib-pamldap support
    if __grains__['kernel'] != 'OpenBSD':
        if result['retcode'] != 0 and 'not found in' in result['stderr']:
            ret = True
            for group in groups:
                cmd = ['gpasswd', '-a', '{0}'.format(name), '{1}'.format(group)]
                if __salt__['cmd.retcode'](cmd, python_shell=False) != 0:
                    ret = False
            return ret
    return result['retcode'] == 0


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

        salt '*' user.chworkphone foo 7735550123
    '''
    return _update_gecos(name, 'workphone', workphone)


def chhomephone(name, homephone):
    '''
    Change the user's Home Phone

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhomephone foo 7735551234
    '''
    return _update_gecos(name, 'homephone', homephone)


def chloginclass(name, loginclass):
    '''
    Change the default login class of the user

    .. note::
        This function only applies to OpenBSD systems.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chloginclass foo staff
    '''
    if __grains__['kernel'] != 'OpenBSD':
        return False
    if loginclass == get_loginclass(name):
        return True
    cmd = ['usermod', '-L', '{0}'.format(loginclass), '{0}'.format(name)]
    __salt__['cmd.run'](cmd, python_shell=False)
    return get_loginclass(name) == loginclass


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


def get_loginclass(name):
    '''
    Get the login class of the user

    .. note::
        This function only applies to OpenBSD systems.

    CLI Example:

    .. code-block:: bash

        salt '*' user.get_loginclass foo
    '''
    if __grains__['kernel'] != 'OpenBSD':
        return False
    userinfo = __salt__['cmd.run_stdout'](
        ['userinfo', name],
        python_shell=False)
    for line in userinfo.splitlines():
        if line.startswith('class'):
            try:
                ret = line.split(None, 1)[1]
                break
            except ValueError:
                continue
    else:
        ret = ''
    return ret


def _format_info(data):
    '''
    Return user information in a pretty way
    '''
    # Put GECOS info into a list
    gecos_field = data.pw_gecos.split(',', 3)
    # Make sure our list has at least four elements
    while len(gecos_field) < 4:
        gecos_field.append('')

    return {'gid': data.pw_gid,
            'groups': list_groups(data.pw_name),
            'home': data.pw_dir,
            'name': data.pw_name,
            'passwd': data.pw_passwd,
            'shell': data.pw_shell,
            'uid': data.pw_uid,
            'fullname': gecos_field[0],
            'roomnumber': gecos_field[1],
            'workphone': gecos_field[2],
            'homephone': gecos_field[3]}


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
    cmd = ['usermod', '-l', '{0}'.format(new_name), '{0}'.format(name)]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('name') == new_name
