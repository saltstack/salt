# -*- coding: utf-8 -*-
'''
Manage groups on Synology DSM

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
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

try:
    import grp
except ImportError:
    pass

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    '''
    Set the user module if we are on Synology
    '''
    if __grains__['os_family'] == 'Synology':
        return __virtualname__
    return (False, 'The synology_group execution module cannot be loaded: '
            ' only available on Synology DSM platform')


def add(name, description=None, **kwargs):  # pylint: disable=unused-argument
    '''
    Add the specified group.

    name
        Group name

    description : ''
        Group description

    CLI Examples:

    .. code-block:: bash

        salt '*' group.add foo
        salt '*' group.add foo 'a simple group'
    '''
    ginfo = info(name)
    if ginfo:
        log.error('group {} already exists'.format(name))
        return False

    cmd = ['synogroup', '--add', _cmd_quote(name)]

    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    ret = not out['retcode']

    if description:
        ret = ret and set_description(name, description)

    return ret


def set_description(name, description):
    '''
    Set specified group description.

    name
        Group name

    description
        Group description

    CLI Example:

    .. code-block:: bash

        salt '*' group.set_description foo 'a simple group'
    '''

    cmd = ['synogroup', '--descset',
           _cmd_quote(name), _cmd_quote(description)]

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''

    ginfo = info(name)
    if not ginfo:
        log.error('Group {} does not exist.'.format(name))
        return False

    cmd = ['synogroup', '--del', name]

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

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
        description = _get_description(name)
        return _format_info(grinfo, description)


def _get_description(name):
    '''
    Return description for named group.
    '''
    cmd = ['synogroup', '--descget', name]
    out = __salt__['run.stdout'](cmd, python_shell=False)
    _, description = out.split(':')
    return description.strip('[]')


def _format_info(data, description):
    '''
    Return formatted information in a pretty way.
    '''
    return {'name': data.gr_name,
            'passwd': data.gr_passwd,
            'gid': data.gr_gid,
            'members': data.gr_mem,
            'description': description}


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
        description = _get_description(grinfo.gr_name)
        ret.append(_format_info(grinfo, description))
    __context__['group.getent'] = ret
    return ret


def adduser(name, username):
    '''
    Add a user in the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.adduser foo bar

    Verifies if a valid username 'bar' as a member of an existing group 'foo',
    if not then adds it.
    '''
    ginfo = info(name)
    uinfo = __salt__['user.info'](username)

    if not ginfo:
        log.error('group {} does not exist'.format(name))
    if not uinfo:
        log.error('user {} does not exist'.format(username))

    if not all(ginfo, uinfo):
        return False

    if name in uinfo['groups']:
        return True

    cmd = ['synogroup', '--member', name]
    cmd.extend(set([member
                    for member
                    in ginfo['members']] + [username]))

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']


def deluser(name, username, _root=None):
    '''
    Remove a user from the group.

    CLI Example:

    .. code-block:: bash

         salt '*' group.deluser foo bar

    Removes a member user 'bar' from a group 'foo'. If group is not present
    then returns True.
    '''
    ginfo = info(name)
    uinfo = __salt__['user.info'](username)

    if any(not ginfo,
           not uinfo,
           name not in uinfo['groups']):
        return True

    cmd = ['synogroup', '--member', name]
    cmd.extend([member
                for member
                in ginfo['members']
                if member != username])

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']


def members(name, members_list, _root=None):
    '''
    Replaces members of the group with a provided list.

    CLI Example:

        salt '*' group.members foo 'user1,user2,user3,...'

    Replaces a membership list for a local group 'foo'.
        foo:x:1234:user1,user2,user3,...
    '''
    ginfo = info(name)
    if not ginfo:
        log.error('group {} does not exist'.format(name))
        return False

    cmd = ['synogroup', '--member', name]
    cmd.extend(members_list.split(','))

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)

    return not ret['retcode']
