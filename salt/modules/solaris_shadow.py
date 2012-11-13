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

    return 'shadow' if __grains__['kernel'] == 'SunOS' else False 


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


def set_maxdays(name, maxdays):
    '''
    Set the maximum number of days during which a password is valid. See man passwd.

    CLI Example::

        salt '*' shadow.set_maxdays username 90
    '''
    pre_info = info(name)
    if maxdays == pre_info['max']:
        return True
    cmd = 'passwd -x {0} {1}'.format(maxdays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['max'] != pre_info['max']:
        return post_info['max'] == maxdays


def set_mindays(name, mindays):
    '''
    Set the minimum number of days between password changes. See man passwd.

    CLI Example::

        salt '*' shadow.set_mindays username 7
    '''
    pre_info = info(name)
    if mindays == pre_info['min']:
        return True
    cmd = 'passwd -n {0} {1}'.format(mindays, name)
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
    with open(s_file, 'rb') as f:
        for line in f:
            comps = line.strip().split(':')
            if not comps[0] == name:
                lines.append(line)
                continue
            comps[1] = password
            line = ':'.join(comps)
            lines.append('{0}\n'.format(line))
    with open(s_file, 'w+') as f: f.writelines(lines)
    uinfo = info(name)
    return uinfo['pwd'] == password


def set_warndays(name, warndays):
    '''
    Set the number of days of warning before a password change is required. See man passwd.

    CLI Example::

        salt '*' shadow.set_warndays username 7
    '''
    pre_info = info(name)
    if warndays == pre_info['warn']:
        return True
    cmd = 'passwd -w {0} {1}'.format(warndays, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['warn'] != pre_info['warn']:
        return post_info['warn'] == warndays
    return False
