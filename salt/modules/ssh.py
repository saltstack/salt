'''
Manage client ssh components
'''

import os

def _refine_enc(enc):
    '''
    Return the properly formatted ssh value for the authorized encryption key
    type. If the type is not found, return ssh-rsa, the ssh default.
    '''
    rsa = ['r', 'rsa', 'ssh-rsa']
    dss = ['d', 'dsa', 'dss', 'ssh-dss']
    if rsa.count(enc):
        return 'ssh-rsa'
    elif dss.count(enc):
        return 'ssh-dss'
    else:
        return 'ssh-rsa'

def _format_auth_line(
        key,
        enc,
        comment,
        options):
    line = ''
    if options:
        line += '{0} '.format(','.join(options))
    line += '{0} {1} {2}'.format(enc, key, comment)
    return line

def _replace_auth_key(
        user,
        key,
        enc='ssh-rsa',
        comment='',
        options=[],
        config='.ssh/authorized_keys'):
    '''
    Replace an existing key
    '''
    auth_line = _format_auth_line(
                key,
                enc,
                comment,
                options)
    lines = []
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    for line in open(full, 'r').readlines():
        if line.startswith('#'):
            # Commented Line
            lines.append(line)
            continue
        comps = line.split()
        if len(comps) < 2:
            # Not a valid line
            lines.append(line)
            continue
        key_ind = 1
        if not comps[0].startswith('ssh-'):
            key_ind = 2
        if comps[key_ind] == key:
            lines.append(auth_line)
        else:
            lines.append(line)
    open(full, 'w+').writelines(lines)

def auth_keys(user, config='.ssh/authorized_keys'):
    '''
    Return the authorized keys for the specified user

    CLI Example:
    salt '*' ssh.auth_keys root
    '''
    ret = {}
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    if not os.path.isfile(full):
        return {}
    for line in open(full, 'r').readlines():
        if line.startswith('#'):
            # Commented Line
            continue
        comps = line.split()
        if len(comps) < 2:
            # Not a valid line
            continue
        if not comps[0].startswith('ssh-'):
            # It has options, grab them
            options = comps[0].split(',')
        else:
            options = []
        if not options:
            enc = comps[0]
            key = comps[1]
            comment = ' '.join(comps[2:])
        else:
            enc = comps[1]
            key = comps[2]
            comment = ' '.join(comps[3:])
        ret[key] = {'enc': enc,
                    'comment': comment,
                    'options': options}

    return ret

def set_auth_key(
        user,
        key,
        enc='ssh-rsa',
        comment='',
        options=[],
        config='.ssh/authorized_keys'):
    '''
    Add a key to the authorized_keys file

    CLI Example:
    salt '*' ssh.set_auth_key <user> <key> dsa '[]' .ssh/authorized_keys
    '''
    enc = _refine_enc(enc)
    ret = ''
    replace = False
    uinfo = __salt__['user.info'](user)
    current = auth_keys(user, config)
    if current.has_key(key):
        if not set(current['options']) == set(options):
            replace = True
        if not current['enc'] == enc:
            replace = True
        if not current['comment'] == comment:
            if comment:
                replace = True
        if replace:
            _replace_auth_key(
                    user,
                    key,
                    enc,
                    comment,
                    options,
                    config)
            return 'replace'
        else:
            return 'no change'
    else:
        auth_line = _format_auth_line(
                    key,
                    enc,
                    comment,
                    options)
        open(
            os.path.join(uinfo['home'], config), 'a+').write(
                    '\n{0}'.format(auth_line))
        return 'new'
