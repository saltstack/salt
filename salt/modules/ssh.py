'''
Manage client ssh components
'''
import os
import re
import binascii
import hashlib


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
            key = comps[1]
            comment = ' '.join(comps[2:])
            fingerprint = _fingerprint(key)
            if fingerprint is None:
                continue

            ret[key] = {'enc': enc,
                        'comment': comment,
                        'options': options,
                        'fingerprint': fingerprint}
    except IOError:
        return {}

    return ret


def _fingerprint(public_key):
    """
    Return a public key fingerprint based on its base64-encoded representation

    The fingerprint string is formatted according to RFC 4716 (ch.4), that is,
    in the form "xx:xx:...:xx"

    If the key is invalid (incorrect base64 string), return None
    """
    try:
        raw_key = public_key.decode('base64')
    except binascii.Error:
        return None
    ret = hashlib.md5(raw_key).hexdigest()
    chunks = [ret[i:i+2] for i in range(0, len(ret), 2)]
    return ':'.join(chunks)


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
            except (IOError, OSError):
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


def check_key_file(user, keysource, config='.ssh/authorized_keys', env='base'):
    '''
    Check a keyfile from a source destination against the local keys and
    return the keys to change
    '''
    ret = {}
    keyfile = __salt__['cp.cache_file'](keysource, env)
    if not keyfile:
        return ret
    s_keys = _validate_keys(keyfile)
    for key in s_keys:
        ret[key] = check_key(
                user,
                key,
                s_keys[key]['enc'],
                s_keys[key]['comment'],
                s_keys[key]['options'],
                config)
    return ret


def check_key(user, key, enc, comment, options, config='.ssh/authorized_keys'):
    '''
    Check to see if a key needs updating, returns "update", "add" or "exists"

    CLI Example::

        salt '*' ssh.check_key <user> <key>
    '''
    current = auth_keys(user, config)
    nline = _format_auth_line(key, enc, comment, options)
    if key in current:
        cline = _format_auth_line(
                key,
                current[key]['enc'],
                current[key]['comment'],
                current[key]['options'])
        if cline != nline:
            return 'update'
    else:
        return 'add'
    return 'exists'


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
        config='.ssh/authorized_keys',
        env='base'):
    '''
    Add a key to the authorized_keys file, using a file as the source.

    CLI Example::

        salt '*' ssh.set_auth_key_from_file <user>\
                salt://ssh_keys/<user>.id_rsa.pub
    '''
    # TODO: add support for pulling keys from other file sources as well
    lfile = __salt__['cp.cache_file'](source, env)
    if not os.path.isfile(lfile):
        return 'fail'

    newkey = {}
    rval = ''
    newkey = _validate_keys(lfile)
    for k in newkey:
        rval += set_auth_key(
                user,
                k,
                newkey[k]['enc'],
                newkey[k]['comment'],
                newkey[k]['options'],
                config
                )
    # Due to the ability for a single file to have multiple keys, it's
    # possible for a single call to this function to have both "replace" and
    # "new" as possible valid returns. I ordered the following as I thought
    # best.
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

        salt '*' ssh.set_auth_key <user> key='<key>' enc='dsa'\
                comment='my key' options='[]' config='.ssh/authorized_keys'
    '''
    if len(key.split()) > 1:
        return 'invalid'

    enc = _refine_enc(enc)
    uinfo = __salt__['user.info'](user)
    status = check_key(user, key, enc, comment, options, config)
    if status == 'update':
        _replace_auth_key(
                user,
                key,
                enc,
                comment,
                options,
                config)
        return 'replace'
    elif status == 'exists':
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
            if os.geteuid() == 0:
                os.chown(dpath, uinfo['uid'], uinfo['gid'])
            os.chmod(dpath, 448)

        if not os.path.isfile(fconfig):
            open(fconfig, 'a+').write('{0}'.format(auth_line))
            if os.geteuid() == 0:
                os.chown(fconfig, uinfo['uid'], uinfo['gid'])
            os.chmod(fconfig, 384)
        else:
            open(fconfig, 'a+').write('{0}'.format(auth_line))
        return 'new'


def _parse_openssh_output(lines):
    '''
    Helper function which parses ssh-keygen -F and ssh-keyscan function output
    and yield dict with keys information, one by one.
    '''
    for line in lines:
        if line.startswith('#'):
            continue
        try:
            hostname, enc, key = line.split()
        except ValueError:  # incorrect format
            continue
        fingerprint = _fingerprint(key)
        if not fingerprint:
            continue
        yield {'hostname': hostname, 'key': key, 'enc': enc,
               'fingerprint': fingerprint}


def get_known_host(user, hostname, config='.ssh/known_hosts'):
    '''
    Return information about known host from the configfile, if any.
    If there is no such key, return None.

    CLI Example::

        salt '*' ssh.get_known_host <user> <hostname>
    '''
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    if not os.path.isfile(full):
        return None
    cmd = 'ssh-keygen -F "{0}" -f "{1}"'.format(hostname, full)
    lines = __salt__['cmd.run'](cmd).splitlines()
    known_hosts = list(_parse_openssh_output(lines))
    return known_hosts[0] if known_hosts else None


def recv_known_host(user, hostname, enc=None, port=None, hash_hostname=False):
    '''
    Retreive information about host public key from remote server

    CLI Example::

        salt '*' ssh.recv_known_host <user> <hostname> enc=<enc> port=<port>
    '''
    chunks = ['ssh-keyscan', ]
    if port:
        chunks += ['-p', str(port)]
    if enc:
        chunks += ['-t', str(enc)]
    if hash_hostname:
        chunks.append('-H')
    chunks.append(str(hostname))
    cmd = ' '.join(chunks)
    lines = __salt__['cmd.run'](cmd).splitlines()
    known_hosts = list(_parse_openssh_output(lines))
    return known_hosts[0] if known_hosts else None


def check_known_host(user, hostname, key=None, fingerprint=None,
                                               config='.ssh/known_hosts'):
    '''
    Check the record in known_hosts file, either by its value or by fingerprint
    (it's enough to set up either key or fingerprint, you don't need to set up
    both).

    If provided key or fingerprint doesn't match with stored value, return
    "update", if no value is found for a given host, return "add", otherwise
    return "exists".

    If neither key, nor fingerprint is defined, then additional validation is
    not performed.

    CLI Example::

        salt '*' ssh.check_known_host <user> <hostname> key='AAAA...FAaQ=='
    '''
    known_host = get_known_host(user, hostname, config=config)
    if not known_host:
        return 'add'
    if key:
        return 'exists' if key == known_host['key'] else 'update'
    elif fingerprint:
        return 'exists' if fingerprint == known_host['fingerprint'] else 'update'
    else:
        return 'exists'


def rm_known_host(user, hostname, config='.ssh/known_hosts'):
    '''
    Remove all keys belonging to hostname from a known_hosts file.

    CLI Example::

        salt '*' ssh.rm_known_host <user> <hostname>
    '''
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    if not os.path.isfile(full):
        return {'status': 'error',
                'error': 'Known hosts file {0} does not exist'.format(full)}
    cmd = 'ssh-keygen -R "{0}" -f "{1}"'.format(hostname, full)
    cmd_result = __salt__['cmd.run'](cmd).strip()
    return {'status': 'removed', 'comment': cmd_result}


def set_known_host(user, hostname,
        fingerprint=None,
        port=None,
        enc=None,
        hash_hostname=True,
        config='.ssh/known_hosts'):
    '''
    Download SSH public key from remote host "hostname", optionally validate
    its fingerprint against "fingerprint" variable and save the record in the
    known_hosts file.

    If such a record does already exists in there, do nothing.


    CLI Example::

        salt '*' ssh.set_known_host <user> fingerprint='xx:xx:..:xx' enc='ssh-rsa'\
                 config='.ssh/known_hosts'
    '''
    update_required = False
    stored_host = get_known_host(user, hostname, config)

    if not stored_host:
        update_required = True
    elif fingerprint and fingerprint != stored_host['fingerprint']:
        update_required = True

    if not update_required:
        return {'status': 'exists', 'key': stored_host}

    remote_host = recv_known_host(user, hostname, enc=enc, port=port,
                                  hash_hostname=True)
    if not remote_host:
        return {'status': 'error',
                'error': 'Unable to receive remote host key'}

    if fingerprint and fingerprint != remote_host['fingerprint']:
        return {'status': 'error',
                'error': ('Remote host public key found but its fingerprint '
                          'does not match one you have provided')}

    # remove everything we had in the config so far
    rm_known_host(user, hostname, config=config)
    # set up new value
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo['home'], config)
    line = '{hostname} {enc} {key}\n'.format(**remote_host)
    with open(full, 'a') as fd:
        fd.write(line)
    if os.geteuid() == 0:
        os.chown(full, uinfo['uid'], uinfo['gid'])
    return {'status': 'updated', 'old': stored_host, 'new': remote_host}

    status = check_known_host(user, hostname, fingerprint=fingerprint,
                                               config=config)
    if status == 'exists':
        return None
