# -*- coding: utf-8 -*-
'''
Manage groups on Linux, OpenBSD and NetBSD
'''

# Import python libs
try:
    import grp
except ImportError:
    pass

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

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''
    ret = __salt__['cmd.run_all']('groupdel {0}'.format(name))

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
    __salt__['cmd.run'](cmd)
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
    if __grains__['kernel'] == 'Linux':
        retcode = __salt__['cmd.retcode']('gpasswd --add {0} {1}'.format(
            username, name))
    else:
        retcode = __salt__['cmd.retcode']('usermod -G {0} {1}'.format(
            name, username))

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
    grp_info = __salt__['group.info'](name)
    try:
        if username in grp_info['members']:
            print username
            if __grains__['kernel'] == 'Linux':
                retcode = __salt__['cmd.retcode']('gpasswd --del {0} {1}'
                    .format(username, name))
            elif __grains__['kernel'] == 'OpenBSD':
                cmd = 'usermod -S '
                out = __salt__['cmd.run_stdout']('id -Gn {0}'.format(username))
                for group in out.split(" "):
                    if group != format(name):
                        cmd += '{0},'.format(group)
                retcode = __salt__['cmd.retcode']('{0} {1}'.format(
                    cmd, username))
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
    if __grains__['kernel'] == 'Linux':
        retcode = __salt__['cmd.retcode']('gpasswd --members {0} {1}'.format(
            members_list, name))
    elif __grains__['kernel'] == 'OpenBSD':
        retcode = 1
        grp_info = __salt__['group.info'](name)
        if grp_info and name in grp_info['name']:
            __salt__['cmd.run']('groupdel {0}'.format(name))
            __salt__['cmd.run']('groupadd -g {0} {1}'.format(
                grp_info['gid'], name))
            for user in members_list.split(","):
                if user:
                    retcode = __salt__['cmd.retcode'](
                        'usermod -G {0} {1}'.format(name, user))
                    if not retcode == 0:
                        break
                # provided list is '': users previously deleted from group
                else:
                    retcode = 0

    return not retcode
