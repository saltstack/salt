# -*- coding: utf-8 -*-
'''
Manage users with the useradd command

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import, print_function, unicode_literals

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False
import logging
import copy

# Import salt libs
import salt.utils.files
import salt.utils.decorators.path
import salt.utils.locales
import salt.utils.stringutils
import salt.utils.user
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is Linux, OpenBSD, NetBSD or AIX
    '''

    if HAS_PWD and __grains__['kernel'] in ('Linux', 'OpenBSD', 'NetBSD', 'AIX'):
        return __virtualname__
    return (False, 'useradd execution module not loaded: either pwd python library not available or system not one of Linux, OpenBSD, NetBSD or AIX')


def _quote_username(name):
    '''
    Usernames can only contain ascii chars, so make sure we return a str type
    '''
    if not isinstance(name, six.string_types):
        return str(name)  # future lint: disable=blacklisted-function
    else:
        return salt.utils.stringutils.to_str(name)


def _get_gecos(name):
    '''
    Retrieve GECOS field info and return it in dictionary form
    '''
    gecos_field = salt.utils.stringutils.to_unicode(
        pwd.getpwnam(_quote_username(name)).pw_gecos).split(',', 3)
    if not gecos_field:
        return {}
    else:
        # Assign empty strings for any unspecified trailing GECOS fields
        while len(gecos_field) < 4:
            gecos_field.append('')
        return {'fullname': salt.utils.locales.sdecode(gecos_field[0]),
                'roomnumber': salt.utils.locales.sdecode(gecos_field[1]),
                'workphone': salt.utils.locales.sdecode(gecos_field[2]),
                'homephone': salt.utils.locales.sdecode(gecos_field[3])}


def _build_gecos(gecos_dict):
    '''
    Accepts a dictionary entry containing GECOS field names and their values,
    and returns a full GECOS comment string, to be used with usermod.
    '''
    return '{0},{1},{2},{3}'.format(gecos_dict.get('fullname', ''),
                                    gecos_dict.get('roomnumber', ''),
                                    gecos_dict.get('workphone', ''),
                                    gecos_dict.get('homephone', ''))


def _update_gecos(name, key, value, root=None):
    '''
    Common code to change a user's GECOS information
    '''
    if value is None:
        value = ''
    elif not isinstance(value, six.string_types):
        value = six.text_type(value)
    else:
        value = salt.utils.stringutils.to_unicode(value)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if value == pre_info[key]:
        return True
    gecos_data = copy.deepcopy(pre_info)
    gecos_data[key] = value

    cmd = ['usermod', '-c', _build_gecos(gecos_data), name]

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

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
        loginclass=None,
        root=None,
        nologinit=False):
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
        cmd.extend(['-u', uid])
    if gid not in (None, ''):
        cmd.extend(['-g', gid])
    elif groups is not None and name in groups:
        defs_file = '/etc/login.defs'
        if __grains__['kernel'] != 'OpenBSD':
            try:
                with salt.utils.files.fopen(defs_file) as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if 'USERGROUPS_ENAB' not in line[:15]:
                            continue

                        if 'yes' in line:
                            cmd.extend([
                                '-g', __salt__['file.group_to_gid'](name)
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
                with salt.utils.files.fopen(usermgmt_file) as fp_:
                    for line in fp_:
                        line = salt.utils.stringutils.to_unicode(line)
                        if 'group' not in line[:5]:
                            continue

                        cmd.extend([
                            '-g', line.split()[-1]
                        ])

                        # We found what we wanted, let's break out of the loop
                        break
            except OSError:
                # /etc/usermgmt.conf not present: defaults will be used
                pass

    if createhome:
        cmd.append('-m')
    elif (__grains__['kernel'] != 'NetBSD'
            and __grains__['kernel'] != 'OpenBSD'):
        cmd.append('-M')

    if nologinit:
        cmd.append('-l')

    if home is not None:
        cmd.extend(['-d', home])

    if not unique and __grains__['kernel'] != 'AIX':
        cmd.append('-o')

    if (system
        and __grains__['kernel'] != 'NetBSD'
        and __grains__['kernel'] != 'OpenBSD'):
        cmd.append('-r')

    if __grains__['kernel'] == 'OpenBSD':
        if loginclass is not None:
            cmd.extend(['-L', loginclass])

    cmd.append(name)

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

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


def delete(name, remove=False, force=False, root=None):
    '''
    Remove a user from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' user.delete name remove=True force=True
    '''
    cmd = ['userdel']

    if remove:
        cmd.append('-r')

    if force and __grains__['kernel'] != 'OpenBSD' and __grains__['kernel'] != 'AIX':
        cmd.append('-f')

    cmd.append(name)

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

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

        if 'var/mail' in ret['stderr'] or 'var/spool/mail' in ret['stderr']:
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
    cmd = ['usermod', '-u', uid, name]
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('uid') == uid


def chgid(name, gid, root=None):
    '''
    Change the default group of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    '''
    pre_info = info(name)
    if gid == pre_info['gid']:
        return True
    cmd = ['usermod', '-g', gid, name]

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('gid') == gid


def chshell(name, shell, root=None):
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

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('shell') == shell


def chhome(name, home, persist=False, root=None):
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
    cmd = ['usermod', '-d', home]

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

    if persist and __grains__['kernel'] != 'OpenBSD':
        cmd.append('-m')
    cmd.append(name)
    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('home') == home


def chgroups(name, groups, append=False, root=None):
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
        if append and __grains__['kernel'] != 'AIX':
            cmd.append('-a')
        cmd.append('-G')
    else:
        if append:
            cmd.append('-G')
        else:
            cmd.append('-S')

    if append and __grains__['kernel'] == 'AIX':
        cmd.extend([','.join(ugrps) + ',' + ','.join(groups), name])
    else:
        cmd.extend([','.join(groups), name])

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

    result = __salt__['cmd.run_all'](cmd, python_shell=False)
    # try to fallback on gpasswd to add user to localgroups
    # for old lib-pamldap support
    if __grains__['kernel'] != 'OpenBSD' and __grains__['kernel'] != 'AIX':
        if result['retcode'] != 0 and 'not found in' in result['stderr']:
            ret = True
            for group in groups:
                cmd = ['gpasswd', '-a', name, group]
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


def chloginclass(name, loginclass, root=None):
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

    cmd = ['usermod', '-L', loginclass, name]

    if root is not None:
        cmd.extend(('-R', root))

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
        data = pwd.getpwnam(_quote_username(name))
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
            except (ValueError, IndexError):
                continue
    else:
        ret = ''
    return ret


def _format_info(data):
    '''
    Return user information in a pretty way
    '''
    # Put GECOS info into a list
    gecos_field = salt.utils.stringutils.to_unicode(data.pw_gecos).split(',', 3)
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


@salt.utils.decorators.path.which('id')
def primary_group(name):
    '''
    Return the primary group of the named user

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' user.primary_group saltadmin
    '''
    return __salt__['cmd.run'](['id', '-g', '-n', name])


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


def rename(name, new_name, root=None):
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

    if root is not None and __grains__['kernel'] != 'AIX':
        cmd.extend(('-R', root))

    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('name') == new_name
