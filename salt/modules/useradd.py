'''
Manage users with the useradd command
'''

# Import python libs
try:
    import grp
    import pwd
except ImportError:
    pass
import logging
import copy

# Import salt libs
import salt.utils
from salt._compat import string_types

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the user module if the kernel is Linux or OpenBSD
    and remove some of the functionality on OS X
    '''
    # XXX: Why are these imports in __virtual__?
    import sys
    from salt._compat import callable
    if __grains__['kernel'] == 'Darwin':
        mod = sys.modules[__name__]
        for attr in dir(mod):
            if callable(getattr(mod, attr)):
                if not attr in ('_format_info', 'getent', 'info',
                                'list_groups', 'list_users', '__virtual__'):
                    delattr(mod, attr)
    return (
        'user' if __grains__['kernel'] in ('Linux', 'Darwin', 'OpenBSD',
                                           'NetBSD')
        else False
    )


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
    and returns a full GECOS comment string, to be used with usermod.
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
        system=False,
        fullname='',
        roomnumber='',
        workphone='',
        homephone='',
        createhome=True):
    '''
    Add a user to the minion

    CLI Example::

        salt '*' user.add name <uid> <gid> <groups> <home> <shell>
    '''
    cmd = 'useradd '
    if shell:
        cmd += '-s {0} '.format(shell)
    if uid not in (None, ''):
        cmd += '-u {0} '.format(uid)
    if gid not in (None, ''):
        cmd += '-g {0} '.format(gid)
    elif groups is not None and name in groups:
        def usergroups():
            retval = False
            try:
                for line in salt.utils.fopen('/etc/login.defs'):
                    if 'USERGROUPS_ENAB' in line[:15]:
                        if "yes" in line:
                            retval = True
            except Exception:
                log.debug('Error reading /etc/login.defs', exc_info=True)
            return retval
        if usergroups():
            cmd += '-g {0} '.format(__salt__['file.group_to_gid'](name))
     
    if createhome:
        cmd += '-m '
    elif createhome is False:
        cmd += '-M '
    
    if home is not None:
        cmd += '-d {0} '.format(home)

    if not unique:
        cmd += '-o '
    if system:
        if not __grains__['kernel'] == 'NetBSD':
            cmd += '-r '
    cmd += name
    ret = __salt__['cmd.run_all'](cmd)['retcode']
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


def delete(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example::

        salt '*' user.delete name remove=True force=True
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
    if 'user.getent' in __context__:
        return __context__['user.getent']

    ret = []
    for data in pwd.getpwall():
        ret.append(_format_info(data))
    __context__['user.getent'] = ret
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
    cmd = 'usermod '
    if append:
        cmd += '-a '
    cmd += '-G "{0}" {1}'.format(','.join(groups), name)
    return not __salt__['cmd.retcode'](cmd)


def chfullname(name, fullname):
    '''
    Change the user's Full Name

    CLI Example::

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
    cmd = 'usermod -c "{0}" {1}'.format(_build_gecos(gecos_field), name)
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
    roomnumber = str(roomnumber)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if roomnumber == pre_info['roomnumber']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['roomnumber'] = roomnumber
    cmd = 'usermod -c "{0}" {1}'.format(_build_gecos(gecos_field), name)
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
    workphone = str(workphone)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if workphone == pre_info['workphone']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['workphone'] = workphone
    cmd = 'usermod -c "{0}" {1}'.format(_build_gecos(gecos_field), name)
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
    homephone = str(homephone)
    pre_info = _get_gecos(name)
    if not pre_info:
        return False
    if homephone == pre_info['homephone']:
        return True
    gecos_field = copy.deepcopy(pre_info)
    gecos_field['homephone'] = homephone
    cmd = 'usermod -c "{0}" {1}'.format(_build_gecos(gecos_field), name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['homephone'] != pre_info['homephone']:
        return post_info['homephone'] == homephone
    return False


def info(name):
    '''
    Return user information

    CLI Example::

        salt '*' user.info root
    '''
    try:
        data = pwd.getpwnam(name)
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


def list_groups(name):
    '''
    Return a list of groups the named user belongs to

    CLI Example::

        salt '*' user.list_groups foo
    '''
    ugrp = set()

    # Add the primary user's group
    try:
        ugrp.add(grp.getgrgid(pwd.getpwnam(name).pw_gid).gr_name)
    except KeyError:
        # The user's applied default group is undefined on the system, so
        # it does not exist
        pass

    groups = grp.getgrall()

    # Now, all other groups the user belongs to
    for group in groups:
        if name in group.gr_mem:
            ugrp.add(group.gr_name)

    return sorted(list(ugrp))


def list_users():
    '''
    Return a list of all users

    CLI Example::

        salt '*' user.list_users
    '''
    return sorted([user.pw_name for user in pwd.getpwall()])
