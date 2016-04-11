# -*- coding: utf-8 -*-
'''
Manage groups on Linux, OpenBSD and NetBSD

.. important::
    If you feel that Salt should be using this module to manage groups on a
    minion, and it is using a different module (or gives an error similar to
    *'group.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Import python libs
from __future__ import absolute_import
import logging

try:
    import grp
except ImportError:
    pass

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    '''
    Set the user module if the kernel is Linux or OpenBSD
    '''
    if __grains__['kernel'] in ('Linux', 'OpenBSD', 'NetBSD'):
        return __virtualname__
    return False


def add(name, gid=None, system=False):
    '''
    Add the specified group

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo 3456
    '''
    cmd = 'groupadd '
    if gid:
        cmd += '-g {0} '.format(gid)
    if system and __grains__['kernel'] != 'OpenBSD':
        cmd += '-r '
    cmd += name

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''
    ret = __salt__['cmd.run_all']('groupdel {0}'.format(name), python_shell=False)

    return not ret['retcode']


def info(name):
    '''
    Return information about a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    '''
    try:
        grinfo = grp.getgrnam(name)
    except KeyError:
        return {}
    else:
        return _format_info(grinfo)


def _format_info(data):
    '''
    Return formatted information in a pretty way.
    '''
    return {'name': data.gr_name,
            'passwd': data.gr_passwd,
            'gid': data.gr_gid,
            'members': data.gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    '''
    if 'group.getent' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []
    for grinfo in grp.getgrall():
        ret.append(_format_info(grinfo))
    __context__['group.getent'] = ret
    return ret


def chgid(name, gid):
    '''
    Change the gid for a named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.chgid foo 4376
    '''
    pre_gid = __salt__['file.group_to_gid'](name)
    if gid == pre_gid:
        return True
    cmd = 'groupmod -g {0} {1}'.format(gid, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_gid = __salt__['file.group_to_gid'](name)
    if post_gid != pre_gid:
        return post_gid == gid
    return False


def adduser(name, username):
    '''
    Add a user in the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.adduser foo bar

    Verifies if a valid username 'bar' as a member of an existing group 'foo',
    if not then adds it.
    '''
    on_redhat_5 = __grains__.get('os_family') == 'RedHat' and __grains__.get('osmajorrelease') == '5'

    if __grains__['kernel'] == 'Linux':
        if on_redhat_5:
            cmd = 'gpasswd -a {0} {1}'.format(username, name)
        else:
            cmd = 'gpasswd --add {0} {1}'.format(username, name)
    else:
        cmd = 'usermod -G {0} {1}'.format(name, username)

    retcode = __salt__['cmd.retcode'](cmd, python_shell=False)

    return not retcode


def deluser(name, username):
    '''
    Remove a user from the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.deluser foo bar

    Removes a member user 'bar' from a group 'foo'. If group is not present
    then returns True.
    '''
    on_redhat_5 = __grains__.get('os_family') == 'RedHat' and __grains__.get('osmajorrelease') == '5'

    grp_info = __salt__['group.info'](name)
    try:
        if username in grp_info['members']:
            if __grains__['kernel'] == 'Linux':
                if on_redhat_5:
                    cmd = 'gpasswd -d {0} {1}'.format(username, name)
                else:
                    cmd = 'gpasswd --del {0} {1}'.format(username, name)
                retcode = __salt__['cmd.retcode'](cmd, python_shell=False)
            elif __grains__['kernel'] == 'OpenBSD':
                out = __salt__['cmd.run_stdout']('id -Gn {0}'.format(username),
                                                 python_shell=False)
                cmd = 'usermod -S '
                cmd += ','.join([g for g in out.split() if g != str(name)])
                cmd += ' {0}'.format(username)
                retcode = __salt__['cmd.retcode'](cmd, python_shell=False)
            else:
                log.error('group.deluser is not yet supported on this platform')
                return False
            return not retcode
        else:
            return True
    except Exception:
        return True


def members(name, members_list):
    '''
    Replaces members of the group with a provided list.

    CLI Example:

        salt '*' group.members foo 'user1,user2,user3,...'

    Replaces a membership list for a local group 'foo'.
        foo:x:1234:user1,user2,user3,...
    '''
    on_redhat_5 = __grains__.get('os_family') == 'RedHat' and __grains__.get('osmajorrelease') == '5'

    if __grains__['kernel'] == 'Linux':
        if on_redhat_5:
            cmd = 'gpasswd -M {0} {1}'.format(members_list, name)
        else:
            cmd = 'gpasswd --members {0} {1}'.format(members_list, name)
        retcode = __salt__['cmd.retcode'](cmd, python_shell=False)
    elif __grains__['kernel'] == 'OpenBSD':
        retcode = 1
        grp_info = __salt__['group.info'](name)
        if grp_info and name in grp_info['name']:
            __salt__['cmd.run']('groupdel {0}'.format(name),
                                python_shell=False)
            __salt__['cmd.run']('groupadd -g {0} {1}'.format(
                grp_info['gid'], name), python_shell=False)
            for user in members_list.split(","):
                if user:
                    retcode = __salt__['cmd.retcode'](
                        'usermod -G {0} {1}'.format(name, user),
                        python_shell=False)
                    if not retcode == 0:
                        break
                # provided list is '': users previously deleted from group
                else:
                    retcode = 0
    else:
        log.error('group.members is not yet supported on this platform')
        return False

    return not retcode
