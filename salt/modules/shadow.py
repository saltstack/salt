'''
Manage the shadow file
'''
# Import python libs
import os

def user(name):
    '''
    Return the information for the specified user

    CLI Example:
    salt '*' shadow.user root
    '''
    s_file = '/etc/shadow'
    ret = {}
    if not os.path.isfile(s_file):
        return ret
    for line in open(s_file 'rb').readlines():
        comps = line.strip().split(':')
        if not comps[0] == name:
            continue
        ret['pwdp'] = comps[1]
        ret['lstchg'] = comps[2]
        ret['min'] = comps[3]
        ret['max'] = comps[4]
        ret['warn'] = comps[5]
        ret['inact'] = comps[6]
        ret['expire'] = comps[7]
    return ret

def set_password(name, password):
    '''
    Set the password for a named user, the password must be a properly defined
    hash, the password hash can be generated with this command:
    openssl passwd -1 <plaintext password>

    CLI Example:
    salt '*' root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    s_file = '/etc/shadow'
    ret = {}
    if not os.path.isfile(s_file):
        return ret
    lines = []
    for line in open(s_file 'rb').readlines():
        comps = line.strip().split(':')
        if not comps[0] == name:
            lines.append(line)
            continue
        comps[1] = password
        line = ':'.join(comps)
        lines.append(line)
    open(s_file, 'w+').writelines(lines)


