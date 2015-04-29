# -*- coding: utf-8 -*-
'''
Manage users with the useradd command
'''

# Import python libs
from __future__ import absolute_import
import copy
import logging
try:
    import pwd
except ImportError:
    pass

# Import 3rd party libs
import salt.ext.six as six

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the user module if the kernel is FreeBSD
    '''
    return __virtualname__ if __grains__['kernel'] == 'FreeBSD' else False


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
    and returns a full GECOS comment string, to be used with pw usermod.
    '''
    return '{0},{1},{2},{3}'.format(gecos_dict.get('fullname', ''),
                                    gecos_dict.get('roomnumber', ''),
                                    gecos_dict.get('workphone', ''),
                                    gecos_dict.get('homephone', ''))


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
    kwargs = salt.utils.clean_kwargs(**kwargs)
    if salt.utils.is_true(kwargs.pop('system', False)):
        log.warning('pw_user module does not support the \'system\' argument')
    if kwargs:
        log.warning('Invalid kwargs passed to user.add')

    if isinstance(groups, six.string_types):
        groups = groups.split(',')
    cmd = 'pw useradd '
    if uid:
        cmd += '-u {0} '.format(uid)
    if gid:
        cmd += '-g {0} '.format(gid)
    if groups:
        cmd += '-G {0} '.format(','.join(groups))
    if home is not None:
        cmd += '-d {0} '.format(home)
    if createhome is True:
        cmd += '-m '
    if shell:
        cmd += '-s {0} '.format(shell)
    if not salt.utils.is_true(unique):
        cmd += '-o '
    gecos_field = '{0},{1},{2},{3}'.format(fullname,
                                           roomnumber,
                                           workphone,
                                           homephone)
    cmd += '-c "{0}" '.format(gecos_field)
    cmd += '-n {0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']


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
    cmd = 'pw userdel '
    if remove:
        cmd += '-r '
    cmd += '-n ' + name

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']


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
    if uid == pre_info['uid']:
        return True
    cmd = 'pw usermod -u {0} -n {1}'.format(uid, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['uid'] != pre_info['uid']:
        return post_info['uid'] == uid
    return False


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
    cmd = 'pw usermod -g {0} -n {1}'.format(gid, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['gid'] != pre_info['gid']:
        return post_info['gid'] == gid
    return False


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
    cmd = 'pw usermod -s {0} -n {1}'.format(shell, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['shell'] != pre_info['shell']:
        return post_info['shell'] == shell
    return False


def chhome(name, home, persist=False):
    '''
    Change the home directory of the user, pass true for persist to copy files
    to the new home dir

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /home/users/foo True
    '''
    pre_info = info(name)
    if home == pre_info['home']:
        return True
    cmd = 'pw usermod {0} -d {1}'.format(name, home)
    if persist:
        cmd += ' -m '
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['home'] != pre_info['home']:
        return post_info['home'] == home
    return False


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

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
    cmd = 'pw usermod -G {0} -n {1}'.format(','.join(groups), name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def chfullname(name, fullname):
    '''
    Change the user's Full Name

    CLI Example:

    .. code-block:: bash

        salt '*' user.chfullname foo "Foo Bar"
    '''
    fullname = str(fullname)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if fullname == pre_info['fullname']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['fullname'] = fullname
    cmd = 'pw usermod {0} -c "{1}"'.format(name, _build_gecos(gecos_field))
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['fullname'] != pre_info['fullname']:
        return post_info['fullname'] == fullname
    return False


def chroomnumber(name, roomnumber):
    '''
    Change the user's Room Number

    CLI Example:

    .. code-block:: bash

        salt '*' user.chroomnumber foo 123
    '''
    roomnumber = str(roomnumber)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if roomnumber == pre_info['roomnumber']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['roomnumber'] = roomnumber
    cmd = 'pw usermod {0} -c "{1}"'.format(name, _build_gecos(gecos_field))
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['roomnumber'] != pre_info['roomnumber']:
        return post_info['roomnumber'] == roomnumber
    return False


def chworkphone(name, workphone):
    '''
    Change the user's Work Phone

    CLI Example:

    .. code-block:: bash

        salt '*' user.chworkphone foo "7735550123"
    '''
    workphone = str(workphone)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if workphone == pre_info['workphone']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['workphone'] = workphone
    cmd = 'pw usermod {0} -c "{1}"'.format(name, _build_gecos(gecos_field))
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['workphone'] != pre_info['workphone']:
        return post_info['workphone'] == workphone
    return False


def chhomephone(name, homephone):
    '''
    Change the user's Home Phone

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhomephone foo "7735551234"
    '''
    homephone = str(homephone)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if homephone == pre_info['homephone']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['homephone'] = homephone
    cmd = 'pw usermod {0} -c "{1}"'.format(name, _build_gecos(gecos_field))
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['homephone'] != pre_info['homephone']:
        return post_info['homephone'] == homephone
    return False


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
        raise CommandExecutionError('User {0!r} does not exist'.format(name))
    new_info = info(new_name)
    if new_info:
        raise CommandExecutionError('User {0!r} already exists'.format(new_name))
    cmd = 'pw usermod -l {0} -n {1}'.format(new_name, name)
    __salt__['cmd.run'](cmd)
    post_info = info(new_name)
    if post_info['name'] != current_info['name']:
        return post_info['name'] == new_name
    return False
