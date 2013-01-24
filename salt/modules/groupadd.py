'''
Manage groups on Linux and OpenBSD
'''

# Import python libs
try:
    import grp
except ImportError:
    pass


def __virtual__():
    '''
    Set the user module if the kernel is Linux or OpenBSD
    '''
    return 'group' if __grains__['kernel'] in ('Linux', 'OpenBSD') else False


def add(name, gid=None, system=False):
    '''
    Add the specified group

    CLI Example::

        salt '*' group.add foo 3456
    '''
    cmd = 'groupadd '
    if gid:
        cmd += '-g {0} '.format(gid)
    if system:
        cmd += '-r '
    cmd += name

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example::

        salt '*' group.delete foo
    '''
    ret = __salt__['cmd.run_all']('groupdel {0}'.format(name))

    return not ret['retcode']


def info(name):
    '''
    Return information about a group

    CLI Example::

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


def getent():
    '''
    Return info on all groups

    CLI Example::

        salt '*' group.getent
    '''
    if 'groupadd_getent' in __context__:
      return __context__['groupadd_getent']

    ret = []
    for grinfo in grp.getgrall():
        ret.append(_format_info(grinfo))
    __context__['groupadd_getent'] = ret

    return ret


def chgid(name, gid):
    '''
    Change the gid for a named group

    CLI Example::

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
