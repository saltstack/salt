'''
Manage the shadow file
'''

# Import python libs
import os
try:
    import spwd
except ImportError:
    pass

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''

    # Disable on Windows, a specific file module exists:
    if salt.utils.is_windows() or __grains__['kernel'] in (
                'SunOS', 'NetBSD'
            ):
        return False
    return 'shadow'


def info(name):
    '''
    Return information for the specified user

    CLI Example::

        salt '*' shadow.info root
    '''
    try:
        data = spwd.getspnam(name)
        ret = {
            'name': data.sp_nam,
            'pwd': data.sp_pwd,
            'lstchg': data.sp_lstchg,
            'min': data.sp_min,
            'max': data.sp_max,
            'warn': data.sp_warn,
            'inact': data.sp_inact,
            'expire': data.sp_expire}
    except KeyError:
        ret = {
            'name': '',
            'pwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_inactdays(name, inactdays):
    '''
    Set the number of days of inactivity after a password has expired before
    the account is locked. See man chage.

    CLI Example::

        salt '*' shadow.set_inactdays username 7
    '''
    pre_info = info(name)
    if inactdays == pre_info['inact']:
        return True
    cmd = 'chage -I {0} {1}'.format(inactdays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['inact'] != pre_info['inact']:
        return post_info['inact'] == inactdays


def set_maxdays(name, maxdays):
    '''
    Set the maximum number of days during which a password is valid.
    See man chage.

    CLI Example::

        salt '*' shadow.set_maxdays username 90
    '''
    pre_info = info(name)
    if maxdays == pre_info['max']:
        return True
    cmd = 'chage -M {0} {1}'.format(maxdays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['max'] != pre_info['max']:
        return post_info['max'] == maxdays


def set_mindays(name, mindays):
    '''
    Set the minimum number of days between password changes. See man chage.

    CLI Example::

        salt '*' shadow.set_mindays username 7
    '''
    pre_info = info(name)
    if mindays == pre_info['min']:
        return True
    cmd = 'chage -m {0} {1}'.format(mindays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['min'] != pre_info['min']:
        return post_info['min'] == mindays
    return False


def set_password(name, password, use_usermod=False):
    '''
    Set the password for a named user. The password must be a properly defined
    hash, the password hash can be generated with this command:
    ``python -c "import crypt, getpass, pwd; print crypt.crypt('password', '\\$6\\$SALTsalt\\$')"``
    Keep in mind that the $6 represents a sha512 hash, if your OS is using a
    different hashing algorithm this needs to be changed accordingly

    CLI Example::

        salt '*' shadow.set_password root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    if not use_usermod:
        # Edit the shadow file directly
        s_file = '/etc/shadow'
        ret = {}
        if not os.path.isfile(s_file):
            return ret
        lines = []
        with salt.utils.fopen(s_file, 'rb') as fp_:
            for line in fp_:
                comps = line.strip().split(':')
                if comps[0] != name:
                    lines.append(line)
                    continue
                comps[1] = password
                line = ':'.join(comps)
                lines.append('{0}\n'.format(line))
        with salt.utils.fopen(s_file, 'w+') as fp_:
            fp_.writelines(lines)
        uinfo = info(name)
        return uinfo['pwd'] == password
    else:
        # Use usermod -p (less secure, but more feature-complete)
        cmd = 'usermod -p {0} {1}'.format(name, password)
        __salt__['cmd.run'](cmd)
        uinfo = info(name)
        return uinfo['pwd'] == password


def set_warndays(name, warndays):
    '''
    Set the number of days of warning before a password change is required.
    See man chage.

    CLI Example::

        salt '*' shadow.set_warndays username 7
    '''
    pre_info = info(name)
    if warndays == pre_info['warn']:
        return True
    cmd = 'chage -W {0} {1}'.format(warndays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['warn'] != pre_info['warn']:
        return post_info['warn'] == warndays
    return False


def set_date(name, date):
    '''
    sets the value for the date the password was last changed to the epoch
    (January 1, 1970). See man chage.

    CLI Example::

        salt '*' shadow.set_date username 0
    '''
    cmd = 'chage -d {0} {1}'.format(date, name)
    __salt__['cmd.run'](cmd)
