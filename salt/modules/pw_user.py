'''
Manage users with the useradd command
'''

import grp
import os
import pwd


def __virtual__():
    '''
    Set the user module if the kernel is Linux
    '''
    return 'user' if __grains__['kernel'] == 'FreeBSD' else False


def add(name,
        uid=None,
        gid=None,
        groups=None,
        home=False,
        shell='/bin/false'):
    '''
    Add a user to the minion

    CLI Example::

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    if isinstance(groups, basestring):
        groups = groups.split(',')
    cmd = 'pw useradd -s {0} '.format(shell)
    if uid:
        cmd += '-u {0} '.format(uid)
    if gid:
        cmd += '-g {0} '.format(gid)
    if groups:
        cmd += '-G {0} '.format(','.join(groups))
    if home:
        cmd += '-m -b {0} '.format(os.dirname(home))
    cmd += '-n {0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example::

        salt '*' user.delete name True True
    '''
    cmd = 'pw userdel '
    if remove:
        cmd += '-r '
    cmd += name

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def getent():
    '''
    Return the list of all info for all users

    CLI Example::

        salt '*' user.getent
    '''
    ret = []
    for data in pwd.getpwall():
        ret.append(info(data.pw_name))
    return ret


def chuid(name, uid):
    '''
    Change the uid for a named user

    CLI Example::

        salt '*' user.chuid foo 4376
    '''
    pre_info = info(name)
    if uid == pre_info['uid']:
        return True
    cmd = 'pw usermod -u {0} {1}'.format(uid, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['uid'] != pre_info['uid']:
        if post_info['uid'] == uid:
            return True
    return False


def chgid(name, gid):
    '''
    Change the default group of the user

    CLI Example::

        salt '*' user.chgid foo 4376
    '''
    pre_info = info(name)
    if gid == pre_info['gid']:
        return True
    cmd = 'pw usermod -g {0} {1}'.format(gid, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['gid'] != pre_info['gid']:
        if post_info['gid'] == gid:
            return True
    return False


def chshell(name, shell):
    '''
    Change the default shell of the user

    CLI Example::

        salt '*' user.chshell foo /bin/zsh
    '''
    pre_info = info(name)
    if shell == pre_info['shell']:
        return True
    cmd = 'pw usermod -s {0} {1}'.format(shell, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['shell'] != pre_info['shell']:
        if post_info['shell'] == shell:
            return True
    return False


def chhome(name, home, persist=False):
    '''
    Change the home directory of the user, pass true for persist to copy files
    to the new home dir

    CLI Example::

        salt '*' user.chhome foo /home/users/foo True
    '''
    pre_info = info(name)
    if home == pre_info['home']:
        return True
    cmd = 'pw usermod -d {0} '.format(home)
    if persist:
        cmd += ' -m '
    cmd += name
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['home'] != pre_info['home']:
        if post_info['home'] == home:
            return True
    return False


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

    CLI Example::

        salt '*' user.chgroups foo wheel,root True
    '''
    if isinstance(groups, basestring):
        groups = groups.split(',')
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True
    cmd = 'pw usermod -G {0} {1} '.format(','.join(groups), name)
    if append:
        cmd += '-a'
    __salt__['cmd.run'](cmd)
    agrps = set(list_groups(name))
    if ugrps.difference(agrps):
        return True
    return False


def info(name):
    '''
    Return user information

    CLI Example::

        salt '*' user.info root
    '''
    ret = {}
    data = pwd.getpwnam(name)
    ret['name'] = data.pw_name
    ret['passwd'] = data.pw_passwd
    ret['uid'] = data.pw_uid
    ret['gid'] = data.pw_gid
    ret['home'] = data.pw_dir
    ret['shell'] = data.pw_shell
    ret['groups'] = list_groups(name)
    return ret


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example::

        salt '*' user.groups foo
    '''
    ugrp = set()
    for group in grp.getgrall():
        if group.gr_mem.count(name):
            ugrp.add(group.gr_name)
    return sorted(list(ugrp))
