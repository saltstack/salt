# -*- coding: utf-8 -*-
'''
Manage users on Synology DSM

.. important::
    If you feel that Salt should be using this module to manage users on a
    minion, and it is using a different module (or gives an error similar to
    *'user.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import
import uuid
import string

try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False
import logging
import copy

# Import salt libs
import salt.utils.decorators.path
import salt.utils.locales

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'user'


def __virtual__():
    '''
    Set the group module if we are on Synology
    '''

    if all(HAS_PWD,
           __grains__['os_family'] == 'Synology'):
        return __virtualname__
    return (False, 'useradd execution module not loaded: either pwd python '
            'library not available or non-Synology system')


def _quote_username(name):
    if isinstance(name, int):
        name = "{0}".format(name)

    return name


def _get_gecos(name):
    '''
    Retrieve GECOS field info and return it in dictionary form
    '''
    gecos_field = pwd.getpwnam(_quote_username(name)).pw_gecos.split(',', 3)
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
    return u'{0},{1},{2},{3}'.format(gecos_dict.get('fullname', ''),
                                     gecos_dict.get('roomnumber', ''),
                                     gecos_dict.get('workphone', ''),
                                     gecos_dict.get('homephone', ''))


def _syno_get_user(name):
    '''
    Parse Synology user informations and return them
    in dictionary form.
    '''
    def _c(s):
        return s.strip('[] ').lower()
    cmd = ['synouser', '--get', name]
    user = __salt__['cmd.run_stdout'](cmd, python_shell=False)
    out = dict(map(_c, s.split(':')) for s in user.split('\n') if ':' in s)
    groups = [s.split()[1] for s in user.split('\n') if s.startswith('(')]
    out['expired'] = out['expired'] != 'false'
    out['member of'] = groups
    for int_value in ('alloc size', 'primary gid', 'user uid'):
        out[int_value] = int(out[int_value])
    return out


def _update_gecos(name, key, value, root=None):
    '''
    Common code to change a user's GECOS information
    '''

    if value is None:
        value = ''
    elif not isinstance(value, six.string_types):
        value = str(value)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if value == pre_info[key]:
        return True
    gecos_data = copy.deepcopy(pre_info)
    gecos_data[key] = value

    user_info = _syno_get_user(name)
    cmd = ['synouser', '--modify', name,
           _build_gecos(gecos_data),
           int(user_info['expired']),
           user_info['user mail']]

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
    cmd = ['synouser', '--add',
           name, uuid.uuid4(),
           fullname, '0', 'user@localhost', '0'
           ]

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
    if remove:
        cmd = ['synouser', '--del', name]
    else:
        # XXX: rename user ?
        user_info = _syno_get_user(name)
        gecos_data = _get_gecos(name)
        cmd = ['synouser', '--modify', name,
               _build_gecos(gecos_data),
               1,
               user_info['user mail']]

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
    log.error('user.chuid is not yet supported on this platform')
    return False


def chgid(name, gid, root=None):
    '''
    Change the default group of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chgid foo 4376
    '''
    log.error('user.chgid is not yet supported on this platform')
    return False


def chshell(name, shell, root=None):
    '''
    Change the default shell of the user

    CLI Example:

    .. code-block:: bash

        salt '*' user.chshell foo /bin/zsh
    '''
    log.error('user.chshell is not yet supported on this platform')
    return False


def chhome(name, home, persist=False, root=None):
    '''
    Change the home directory of the user, pass True for persist to move files
    to the new home directory if the old home directory exist.

    CLI Example:

    .. code-block:: bash

        salt '*' user.chhome foo /home/users/foo True
    '''
    log.error('user.chhome is not yet supported on this platform')
    return False


def _syno_manage_group(action, group, name):
    '''
    Modify group membership on a Synology NAS

    :param action: either `remove` or `add`
    :param group: group name we are changing
    :param name: username to add/remove
    '''
    cmd = ['synogroup', '--get', group]
    ret = __salt__['cmd.run_stdout'](cmd, python_shell=False)
    group_users = set(x.split(':')[1].strip('[]')
                      for x
                      in ret.split('\n')
                      if x
                      and x[0] in string.digits)
    getattr(group_users, action)(name)
    cmd = ['synogroup', '--member', group, ' '.join(group_users)]
    return __salt__['cmd.retcode'](cmd, python_shell=False)


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

    rets = []
    groups = set(groups)

    if not append:
        for group in ugrps - groups:
            rets += _syno_manage_group('remove', group, name)

    for group in groups - ugrps:
        rets += _syno_manage_group('add', group, name)

    return not any(rets)


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
    return salt.utils.get_group_list(name)


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
    cmd = ['synouser', '--rename', name, new_name]

    __salt__['cmd.run'](cmd, python_shell=False)
    return info(name).get('name') == new_name
