'''
Manage users with the useradd command
'''
try:
    import grp
    import pwd
except ImportError:
    pass

from salt._compat import string_types, callable


def __virtual__():
    '''
    Set the user module if the kernel is Linux
    '''
    import sys
    if __grains__['kernel'] == 'Darwin':
        mod = sys.modules[__name__]
        for attr in dir(mod):

            if callable(getattr(mod, attr)):
                if not attr in ('getent', 'info', 'list_groups', '__virtual__'):
                    delattr(mod, attr)
    return 'user' if __grains__['kernel'] in ('Linux', 'Darwin') else False


def add(name,
        uid=None,
        gid=None,
        groups=None,
        home=True,
        shell=None,
        fullname=None,
        roomnumber=None,
        workphone=None,
        homephone=None,
        other=None,
        unique=True,
        system=False):
    '''
    Add a user to the minion

    CLI Example::

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    if isinstance(groups, string_types):
        groups = groups.split(',')
    cmd = 'useradd '
    if shell:
        cmd += '-s {0} '.format(shell)
    if uid:
        cmd += '-u {0} '.format(uid)
    if gid:
        cmd += '-g {0} '.format(gid)
    if groups:
        cmd += '-G {0} '.format(','.join(groups))
    if home:
        if home is not True:
            cmd += '-d {0} '.format(home)
        else:
            if not system:
                cmd += '-m '
    if not unique:
        cmd += '-o '
    if system:
        cmd += '-r '
    cmd += name
    ret = __salt__['cmd.retcode'](cmd)
    if ret != 0:
        return False
    else:
        # At this point, the user was successfully created, so return true
        # regardless of the outcome of the below functions. If there is a
        # problem wth changing any of the user's info below, it will be raised
        # in a future highstate call. If anyone has a better idea on how to do
        # this, feel free to change it, but I didn't think it was a good idea
        # to return False when the user was successfully created since A) the
        # user does exist, and B) running useradd again would result in a
        # nonzero exit status and be interpreted as a False result.
        if fullname:
            chfullname(name, fullname)
        if roomnumber:
            chroomnumber(name, roomnumber)
        if workphone:
            chworkphone(name, workphone)
        if homephone:
            chhomephone(name, homephone)
        if other:
            chother(name, other)
        return True


def delete(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example::

        salt '*' user.delete name True True
    '''
    cmd = 'userdel '
    if remove:
        cmd += '-r '
    if force:
        cmd += '-f '
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
    cmd = 'usermod -u {0} {1}'.format(uid, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['uid'] != pre_info['uid']:
        return post_info['uid'] == uid
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
    cmd = 'usermod -g {0} {1}'.format(gid, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['gid'] != pre_info['gid']:
        return post_info['gid'] == gid
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
    cmd = 'usermod -s {0} {1}'.format(shell, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['shell'] != pre_info['shell']:
        return post_info['shell'] == shell
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
    cmd = 'usermod -d {0} '.format(home)
    if persist:
        cmd += ' -m '
    cmd += name
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['home'] != pre_info['home']:
        return post_info['home'] == home
    return False


def chgroups(name, groups, append=False):
    '''
    Change the groups this user belongs to, add append to append the specified
    groups

    CLI Example::

        salt '*' user.chgroups foo wheel,root True
    '''
    if isinstance(groups, string_types):
        groups = groups.split(',')
    ugrps = set(list_groups(name))
    if ugrps == set(groups):
        return True
    cmd = 'usermod -G {0} {1} '.format(','.join(groups), name)
    if append:
        cmd += '-a'
    __salt__['cmd.run'](cmd)
    agrps = set(list_groups(name))
    return len(ugrps - agrps) == 0


def chfullname(name, fullname):
    '''
    Change the users Full Name

    CLI Example::

        salt '*' user.chfullname foo "Foo Bar"
    '''
    pre_info = info(name)
    if fullname == pre_info['fullname']:
        return True
    cmd = 'chfn -f "{0}" {1}'.format(fullname, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['fullname'] != pre_info['fullname']:
        return post_info['fullname'] == fullname
    return False


def chroomnumber(name, roomnumber):
    '''
    Change the user's Room Number

    CLI Example::

        salt '*' user.chroomnumber foo 123
    '''
    pre_info = info(name)
    if roomnumber == pre_info['roomnumber']:
        return True
    cmd = 'chfn -r "{0}" {1}'.format(roomnumber, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['roomnumber'] != pre_info['roomnumber']:
        return post_info['roomnumber'] == roomnumber
    return False


def chworkphone(name, workphone):
    '''
    Change the user's Work Phone

    CLI Example::

        salt '*' user.chworkphone foo "7735550123"
    '''
    pre_info = info(name)
    if workphone == pre_info['workphone']:
        return True
    cmd = 'chfn -w "{0}" {1}'.format(workphone, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['workphone'] != pre_info['workphone']:
        return post_info['workphone'] == workphone
    return False


def chhomephone(name, homephone):
    '''
    Change the user's Home Phone

    CLI Example::

        salt '*' user.chhomephone foo "7735551234"
    '''
    pre_info = info(name)
    if homephone == pre_info['homephone']:
        return True
    cmd = 'chfn -h "{0}" {1}'.format(homephone, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['homephone'] != pre_info['homephone']:
        return post_info['homephone'] == homephone
    return False


def chother(name, other):
    '''
    Change the user's "Other" GECOS field

    CLI Example::

        salt '*' user.chother foo "fax=7735555678"
    '''
    pre_info = info(name)
    if other == pre_info['other']:
        return True
    cmd = 'chfn -o "{0}" {1}'.format(other, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['other'] != pre_info['other']:
        return post_info['other'] == other
    return False


def info(name):
    '''
    Return user information

    CLI Example::

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
        gecos_field = data.pw_gecos.split(',', 4)
        # Assign empty strings for any unspecified GECOS fields
        while len(gecos_field) < 5:
            gecos_field.append('')
        ret['fullname'] = gecos_field[0]
        ret['roomnumber'] = gecos_field[1]
        ret['workphone'] = gecos_field[2]
        ret['homephone'] = gecos_field[3]
        ret['other'] = gecos_field[4]
    except KeyError:
        ret['gid'] = ''
        ret['groups'] = ''
        ret['home'] = ''
        ret['name'] = ''
        ret['passwd'] = ''
        ret['shell'] = ''
        ret['uid'] = ''
        ret['fullname'] = ''
        ret['roomnumber'] = ''
        ret['workphone'] = ''
        ret['homephone'] = ''
        ret['other'] = ''
    return ret


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example::

        salt '*' user.list_groups foo
    '''
    ugrp = set()

    for group in grp.getgrall():
        if name in group.gr_mem:
            ugrp.add(group.gr_name)

    return sorted(list(ugrp))
