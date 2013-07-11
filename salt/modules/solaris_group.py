'''
Manage groups on Solaris
'''

# Import python libs
import logging

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


try:
    import grp
except ImportError:
    pass


def __virtual__():
    '''
    Set the group module if the kernel is SunOS
    '''
    return 'group' if __grains__['kernel'] == 'SunOS' else False


def add(name, gid=None, **kwargs):
    '''
    Add the specified group

    CLI Example::

        salt '*' group.add foo 3456
    '''
    if salt.utils.is_true(kwargs.pop('system', False)):
        log.warning('solaris_group module does not support the \'system\' '
                    'argument')
    if kwargs:
        raise TypeError('Invalid keyword argument(s): {}'.format(kwargs))

    cmd = 'groupadd '
    if gid:
        cmd += '-g {0} '.format(gid)
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
        return {'name': grinfo.gr_name,
                'passwd': grinfo.gr_passwd,
                'gid': grinfo.gr_gid,
                'members': grinfo.gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    CLI Example::

        salt '*' group.getent
    '''
    if 'group.getent' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []
    for grinfo in grp.getgrall():
        ret.append(info(grinfo.gr_name))

    __context__['group.getent'] = ret
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
