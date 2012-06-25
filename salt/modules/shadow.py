'''
Manage the shadow file
'''

import os
try:
    import spwd
except ImportError:
    pass

def __virtual__():
    '''
    Only work on posix-like systems
    '''

    # Disable on Windows, a specific file module exists:
    if __grains__['os'] == 'Windows':
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
    Set the number of days of inactivity after a password has expired before the account is locked. See man chage.

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
    Set the maximum number of days during which a password is valid. See man chage.

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

def set_password(name, password):
    '''
    Set the password for a named user. The password must be a properly defined
    hash, the password hash can be generated with this command:
    ``openssl passwd -1 <plaintext password>``

    CLI Example::

        salt '*' shadow.set_password root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    s_file = '/etc/shadow'
    ret = {}
    if not os.path.isfile(s_file):
        return ret
    lines = []
    for line in open(s_file, 'rb').readlines():
        comps = line.strip().split(':')
        if not comps[0] == name:
            lines.append(line)
            continue
        comps[1] = password
        line = ':'.join(comps)
        lines.append('{0}\n'.format(line))
    open(s_file, 'w+').writelines(lines)
    uinfo = info(name)
    return uinfo['pwd'] == password

def set_warndays(name, warndays):
    '''
    Set the number of days of warning before a password change is required. See man chage.

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
