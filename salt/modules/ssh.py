'''
Manage client ssh components
'''

import os
import re


def _refine_enc(enc):
    '''
    Return the properly formatted ssh value for the authorized encryption key
    type. ecdsa defaults to 256 bits, must give full ecdsa enc schema string if
    using higher enc. If the type is not found, return ssh-rsa, the ssh default.
    '''
    rsa   = ['r', 'rsa', 'ssh-rsa']
    dss   = ['d', 'dsa', 'dss', 'ssh-dss']
    ecdsa = ['e', 'ecdsa', 'ecdsa-sha2-nistp521', 'ecdsa-sha2-nistp384',
            'ecdsa-sha2-nistp256']

    if enc in rsa:
        return 'ssh-rsa'
    elif enc in dss:
        return 'ssh-dss'
    elif enc in ecdsa:
        # ecdsa defaults to ecdsa-sha2-nistp256
        # otherwise enc string is actual encoding string
        if enc in ['e', 'ecdsa']:
            return 'ecdsa-sha2-nistp256'
        return enc
    else:
        return 'ssh-rsa'


def _format_auth_line(
        key,
        enc,
        comment,
        options):
    '''
    Properly format user input.
    '''
    line = ''
    if options:
        line += '{0} '.format(','.join(options))
    line += '{0} {1} {2}\n'.format(enc, key, comment)
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
        if comps[0][:4:] not in ['ssh-', 'ecds']:
            key_ind = 2
        if comps[key_ind] == key:
            lines.append(auth_line)
        else:
            lines.append(line)
    open(full, 'w+').writelines(lines)


def host_keys(keydir=None):
    '''
    Return the minion's host keys

    CLI Example::

        salt '*' ssh.host_keys
    '''
    # Set up the default keydir - needs to support sshd_config parsing in the
    # future
    if not keydir:
        if __grains__['kernel'] == 'Linux':
            keydir = '/etc/ssh'
    keys = {}
    for fn_ in os.listdir(keydir):
        if fn_.startswith('ssh_host_'):
            top = fn_.split('.')
            comps = fn_.split('_')
            kname = comps[2]
            if len(top) > 1:
                kname += '.{0}'.format(top[1])
            try:
                keys[kname] = open(os.path.join(keydir, fn_), 'r').read()
            except:
                keys[kname] = ''
    return keys


def auth_keys(user, config='.ssh/authorized_keys'):
    '''
    Return the authorized keys for the specified user

    CLI Example::

        salt '*' ssh.auth_keys root
    '''
    ret = {}
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    if not os.path.isfile(full):
        return {}

    return _validate_keys(full)


def _validate_keys(key_file):
    '''
    Return a dict containing validated keys in the passed file
    '''
    ret = {}
    linere = re.compile(r'^(.*?)\s?((?:ssh\-|ecds).+)$')
    try:
        for line in open(key_file, 'r').readlines():
            if line.startswith('#'):
                # Commented Line
                continue

            # get "{options} key"
            ln = re.search(linere, line)
            if not ln:
                # not an auth ssh key, perhaps a blank line
                continue

            opts = ln.group(1)
            comps = ln.group(2).split()

            if len(comps) < 2:
                # Not a valid line
                continue

            if opts:
                # It has options, grab them
                options = opts.split(',')
            else:
                options = []

            enc = comps[0]
            # check if key has a space
            if len(comps) == 3:
                key = comps[1] + ' ' + comps[2]
                comment = ' '.join(comps[3:])
            else:
                key = comps[1]
                comment = ' '.join(comps[2:])

            ret[key] = {'enc': enc,
                        'comment': comment,
                        'options': options}
    except IOError:
        return "fail"

    return ret


def rm_auth_key(user, key, config='.ssh/authorized_keys'):
    '''
    Remove an authorized key from the specified user's authorized key file

    CLI Example::

        salt '*' ssh.rm_auth_key <user> <key>
    '''
    current = auth_keys(user, config)
    linere = re.compile(r'^(.*?)\s?((?:ssh\-|ecds).+)$')
    if key in current:
        # Remove the key
        uinfo = __salt__['user.info'](user)
        full = os.path.join(uinfo['home'], config)
        if not os.path.isfile(full):
            return 'User authorized keys file not present'
        lines = []
        for line in open(full, 'r').readlines():
            if line.startswith('#'):
                # Commented Line
                lines.append(line)
                continue

            # get "{options} key"
            ln = re.search(linere, line)
            if not ln:
                # not an auth ssh key, perhaps a blank line
                continue

            opts = ln.group(1)
            comps = ln.group(2).split()

            if len(comps) < 2:
                # Not a valid line
                lines.append(line)
                continue

            if opts:
                # It has options, grab them
                options = opts.split(',')
            else:
                options = []

            if len(comps) == 3:
                pkey = comps[1] + ' ' + comps[2]
            else:
                pkey = comps[1]

            if pkey == key:
                continue
            else:
                lines.append(line)
        open(full, 'w+').writelines(lines)
        return 'Key removed'
    return 'Key not present'

def set_auth_key_from_file(
        user,
        source,
        config='.ssh/authorized_keys'):
    '''
    Add a key to the authorized_keys file, using a file as the source.

    CLI Example::

        salt '*' ssh.set_auth_key_from_file <user> salt://ssh_keys/<user>.id_rsa.pub
    '''
    # TODO: add support for pulling keys from other file sources as well
    lfile = __salt__['cp.cache_file'](source)
    if not os.path.isfile(lfile):
        return 'fail'

    newkey = {}
    rval = ""
    newkey = _validate_keys(lfile)
    for k in newkey.keys():
        rval += set_auth_key(user, k, newkey[k]['enc'], newkey[k]['comment'], newkey[k]['options'], config)
    # Due to the ability for a single file to have multiple keys, it's possible for a single call
    # to this function to have both "replace" and "new" as possible valid returns. I ordered the
    # following as I thought best.
    if 'fail' in rval:
        return 'fail'
    elif 'replace' in rval:
        return 'replace'
    elif 'new' in rval:
        return 'new'
    else:
        return 'no change'

def set_auth_key(
        user,
        key,
        enc='ssh-rsa',
        comment='',
        options=[],
        config='.ssh/authorized_keys'):
    '''
    Add a key to the authorized_keys file

    CLI Example::

        salt '*' ssh.set_auth_key <user> <key> dsa 'my key' '[]' .ssh/authorized_keys
    '''
    enc = _refine_enc(enc)
    replace = False
    uinfo = __salt__['user.info'](user)
    current = auth_keys(user, config)
    if key in current:
        if not set(current[key]['options']) == set(options):
            replace = True
        if not current[key]['enc'] == enc:
            replace = True
        if not current[key]['comment'] == comment:
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
        if not os.path.isdir(uinfo['home']):
            return 'fail'
        fconfig = os.path.join(uinfo['home'], config)
        if not os.path.isdir(os.path.dirname(fconfig)):
            dpath = os.path.dirname(fconfig)
            os.makedirs(dpath)
            os.chown(dpath, uinfo['uid'], uinfo['gid'])
            os.chmod(dpath, 448)

        if not os.path.isfile(fconfig):
            open(fconfig, 'a+').write('{0}'.format(auth_line))
            os.chown(fconfig, uinfo['uid'], uinfo['gid'])
            os.chmod(fconfig, 384)
        else:
            open(fconfig, 'a+').write('{0}'.format(auth_line))
        return 'new'
