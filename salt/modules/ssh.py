# -*- coding: utf-8 -*-
'''
Manage client ssh components
'''

# Import python libs
import os
import re
import hashlib
import binascii
import logging

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import (
    SaltInvocationError,
    CommandExecutionError,
)

log = logging.getLogger(__name__)


def __virtual__():
    # TODO: This could work on windows with some love
    if salt.utils.is_windows():
        return False
    return True


def _refine_enc(enc):
    '''
    Return the properly formatted ssh value for the authorized encryption key
    type. ecdsa defaults to 256 bits, must give full ecdsa enc schema string
    if using higher enc. If the type is not found, raise CommandExecutionError.
    '''

    rsa = ['r', 'rsa', 'ssh-rsa']
    dss = ['d', 'dsa', 'dss', 'ssh-dss']
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
        raise CommandExecutionError(
            'Incorrect encryption key type {0!r}.'.format(enc)
        )


def _format_auth_line(key, enc, comment, options):
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
        options=None,
        config='.ssh/authorized_keys'):
    '''
    Replace an existing key
    '''

    auth_line = _format_auth_line(key, enc, comment, options or [])

    lines = []
    uinfo = __salt__['user.info'](user)
    if not uinfo:
        raise CommandExecutionError('User {0!r} does not exist'.format(user))

    full = os.path.join(uinfo['home'], config)

    try:
        # open the file for both reading AND writing
        with salt.utils.fopen(full, 'r') as _fh:
            for line in _fh:
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
            _fh.close()
            # Re-open the file writable after properly closing it
            with salt.utils.fopen(full, 'w') as _fh:
                # Write out any changes
                _fh.writelines(lines)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(
            'Problem reading or writing to key file: {0}'.format(exc)
        )


def _validate_keys(key_file):
    '''
    Return a dict containing validated keys in the passed file
    '''
    ret = {}
    linere = re.compile(r'^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$')

    try:
        with salt.utils.fopen(key_file, 'r') as _fh:
            for line in _fh:
                if line.startswith('#'):
                    # Commented Line
                    continue

                # get "{options} key"
                search = re.search(linere, line)
                if not search:
                    # not an auth ssh key, perhaps a blank line
                    continue

                opts = search.group(1)
                comps = search.group(2).split()

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
    except (IOError, OSError):
        raise CommandExecutionError(
            'Problem reading ssh key file {0}'.format(key_file)
        )

    return ret


def _fingerprint(public_key):
    '''
    Return a public key fingerprint based on its base64-encoded representation

    The fingerprint string is formatted according to RFC 4716 (ch.4), that is,
    in the form "xx:xx:...:xx"

    If the key is invalid (incorrect base64 string), return None
    '''
    try:
        raw_key = public_key.decode('base64')
    except binascii.Error:
        return None
    ret = hashlib.md5(raw_key).hexdigest()
    chunks = [ret[i:i + 2] for i in range(0, len(ret), 2)]
    return ':'.join(chunks)


def host_keys(keydir=None):
    '''
    Return the minion's host keys

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.host_keys
    '''
    # TODO: support parsing sshd_config for the key directory
    if not keydir:
        if __grains__['kernel'] == 'Linux':
            keydir = '/etc/ssh'
        else:
            # If keydir is None, os.listdir() will blow up
            raise SaltInvocationError('ssh.host_keys: Please specify a keydir')
    keys = {}
    for fn_ in os.listdir(keydir):
        if fn_.startswith('ssh_host_'):
            top = fn_.split('.')
            comps = fn_.split('_')
            kname = comps[2]
            if len(top) > 1:
                kname += '.{0}'.format(top[1])
            try:
                with salt.utils.fopen(os.path.join(keydir, fn_), 'r') as _fh:
                    keys[kname] = _fh.readline().strip()
            except (IOError, OSError):
                keys[kname] = ''
    return keys


def auth_keys(user, config='.ssh/authorized_keys'):
    '''
    Return the authorized keys for the specified user

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.auth_keys root
    '''
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo.get('home', ''), config)
    if not uinfo or not os.path.isfile(full):
        return {}

    return _validate_keys(full)


def check_key_file(user,
                   source,
                   config='.ssh/authorized_keys',
                   saltenv='base',
                   env=None):
    '''
    Check a keyfile from a source destination against the local keys and
    return the keys to change

    CLI Example:

    .. code-block:: bash

        salt '*' root salt://ssh/keyfile
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    keyfile = __salt__['cp.cache_file'](source, saltenv)
    if not keyfile:
        return {}
    s_keys = _validate_keys(keyfile)
    if not s_keys:
        err = 'No keys detected in {0}. Is file properly ' \
              'formatted?'.format(source)
        log.error(err)
        __context__['ssh_auth.error'] = err
        return {}
    else:
        ret = {}
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

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_key <user> <key> <enc> <comment> <options>
    '''
    enc = _refine_enc(enc)
    current = auth_keys(user, config)
    nline = _format_auth_line(key, enc, comment, options)
    if key in current:
        cline = _format_auth_line(key,
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

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_auth_key <user> <key>
    '''
    current = auth_keys(user, config)
    linere = re.compile(r'^(.*?)\s?((?:ssh\-|ecds)[\w-]+\s.+)$')
    if key in current:
        # Remove the key
        uinfo = __salt__['user.info'](user)
        if not uinfo:
            return 'User {0} does not exist'.format(user)
        full = os.path.join(uinfo.get('home', ''), config)

        # Return something sensible if the file doesn't exist
        if not os.path.isfile(full):
            return 'Authorized keys file {1} not present'.format(full)

        lines = []
        try:
            # Read every line in the file to find the right ssh key
            # and then write out the correct one. Open the file once
            with salt.utils.fopen(full, 'r') as _fh:
                for line in _fh:
                    if line.startswith('#'):
                        # Commented Line
                        lines.append(line)
                        continue

                    # get "{options} key"
                    search = re.search(linere, line)
                    if not search:
                        # not an auth ssh key, perhaps a blank line
                        continue

                    comps = search.group(2).split()

                    if len(comps) < 2:
                        # Not a valid line
                        lines.append(line)
                        continue

                    pkey = comps[1]

                    # This is the key we are "deleting", so don't put
                    # it in the list of keys to be re-added back
                    if pkey == key:
                        continue

                    lines.append(line)

            # Let the context manager do the right thing here and then
            # re-open the file in write mode to save the changes out.
            with salt.utils.fopen(full, 'w') as _fh:
                _fh.writelines(lines)
        except (IOError, OSError) as exc:
            log.warn('Could not read/write key file: {0}'.format(str(exc)))
            return 'Key not removed'
        return 'Key removed'
    # TODO: Should this function return a simple boolean?
    return 'Key not present'


def set_auth_key_from_file(user,
                          source,
                          config='.ssh/authorized_keys',
                          saltenv='base',
                          env=None):
    '''
    Add a key to the authorized_keys file, using a file as the source.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key_from_file <user>\
                salt://ssh_keys/<user>.id_rsa.pub
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    # TODO: add support for pulling keys from other file sources as well
    lfile = __salt__['cp.cache_file'](source, saltenv)
    if not os.path.isfile(lfile):
        raise CommandExecutionError(
            'Failed to pull key file from salt file server'
        )

    s_keys = _validate_keys(lfile)
    if not s_keys:
        err = (
            'No keys detected in {0}. Is file properly formatted?'.format(
                source
            )
        )
        log.error(err)
        __context__['ssh_auth.error'] = err
        return 'fail'
    else:
        rval = ''
        for key in s_keys:
            rval += set_auth_key(
                user,
                key,
                s_keys[key]['enc'],
                s_keys[key]['comment'],
                s_keys[key]['options'],
                config
            )
        # Due to the ability for a single file to have multiple keys, it's
        # possible for a single call to this function to have both "replace"
        # and "new" as possible valid returns. I ordered the following as I
        # thought best.
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
        options=None,
        config='.ssh/authorized_keys'):
    '''
    Add a key to the authorized_keys file. The "key" parameter must only be the
    string of text that is the encoded key. If the key begins with "ssh-rsa"
    or ends with user@host, remove those from the key before passing it to this
    function.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key <user> '<key>' enc='dsa'
    '''
    if len(key.split()) > 1:
        return 'invalid'

    enc = _refine_enc(enc)
    uinfo = __salt__['user.info'](user)
    if not uinfo:
        return 'fail'
    status = check_key(user, key, enc, comment, options, config)
    if status == 'update':
        _replace_auth_key(user, key, enc, comment, options or [], config)
        return 'replace'
    elif status == 'exists':
        return 'no change'
    else:
        auth_line = _format_auth_line(key, enc, comment, options)
        if not os.path.isdir(uinfo.get('home', '')):
            return 'fail'
        fconfig = os.path.join(uinfo['home'], config)
        if not os.path.isdir(os.path.dirname(fconfig)):
            dpath = os.path.dirname(fconfig)
            os.makedirs(dpath)
            if os.geteuid() == 0:
                os.chown(dpath, uinfo['uid'], uinfo['gid'])
            os.chmod(dpath, 448)

        if not os.path.isfile(fconfig):
            new_file = True
        else:
            new_file = False

        try:
            with salt.utils.fopen(fconfig, 'a+') as _fh:
                if new_file is False:
                    # Let's make sure we have a new line at the end of the file
                    _fh.seek(1024, 2)
                    if not _fh.read(1024).rstrip(' ').endswith('\n'):
                        _fh.seek(0, 2)
                        _fh.write('\n')
                _fh.write('{0}'.format(auth_line))
        except (IOError, OSError) as exc:
            msg = 'Could not write to key file: {0}'
            raise CommandExecutionError(msg.format(str(exc)))

        if new_file:
            if os.geteuid() == 0:
                os.chown(fconfig, uinfo['uid'], uinfo['gid'])
            os.chmod(fconfig, 384)
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


@decorators.which('ssh-keygen')
def get_known_host(user, hostname, config='.ssh/known_hosts'):
    '''
    Return information about known host from the configfile, if any.
    If there is no such key, return None.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.get_known_host <user> <hostname>
    '''
    uinfo = __salt__['user.info'](user)
    full = os.path.join(uinfo.get('home', ''), config)
    if not uinfo or not os.path.isfile(full):
        return None
    cmd = 'ssh-keygen -F "{0}" -f "{1}"'.format(hostname, full)
    lines = __salt__['cmd.run'](cmd).splitlines()
    known_hosts = list(_parse_openssh_output(lines))
    return known_hosts[0] if known_hosts else None


@decorators.which('ssh-keyscan')
def recv_known_host(hostname, enc=None, port=None, hash_hostname=False):
    '''
    Retrieve information about host public key from remote server

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.recv_known_host <hostname> enc=<enc> port=<port>
    '''
    # The following list of OSes have an old version of openssh-clients
    # and thus require the '-t' option for ssh-keyscan
    need_dash_t = ['CentOS-5']

    chunks = ['ssh-keyscan']
    if port:
        chunks += ['-p', str(port)]
    if enc:
        chunks += ['-t', str(enc)]
    if not enc and __grains__.get('osfinger') in need_dash_t:
        chunks += ['-t', 'rsa']
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

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_known_host <user> <hostname> key='AAAA...FAaQ=='
    '''
    known_host = get_known_host(user, hostname, config=config)
    if not known_host:
        return 'add'
    if key:
        return 'exists' if key == known_host['key'] else 'update'
    elif fingerprint:
        return ('exists' if fingerprint == known_host['fingerprint']
                else 'update')
    else:
        return 'exists'


def rm_known_host(user, hostname, config='.ssh/known_hosts'):
    '''
    Remove all keys belonging to hostname from a known_hosts file.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_known_host <user> <hostname>
    '''
    uinfo = __salt__['user.info'](user)
    if not uinfo:
        return {'status': 'error',
                'error': 'User {0} does not exist'.format(user)}
    full = os.path.join(uinfo.get('home', ''), config)
    if not os.path.isfile(full):
        return {'status': 'error',
                'error': 'Known hosts file {0} does not exist'.format(full)}
    cmd = 'ssh-keygen -R "{0}" -f "{1}"'.format(hostname, full)
    cmd_result = __salt__['cmd.run'](cmd)
    # ssh-keygen creates a new file, thus a chown is required.
    if os.geteuid() == 0:
        os.chown(full, uinfo['uid'], uinfo['gid'])
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


    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_known_host <user> fingerprint='xx:xx:..:xx' \
                 enc='ssh-rsa' config='.ssh/known_hosts'
    '''
    update_required = False
    stored_host = get_known_host(user, hostname, config)

    if not stored_host:
        update_required = True
    elif fingerprint and fingerprint != stored_host['fingerprint']:
        update_required = True

    if not update_required:
        return {'status': 'exists', 'key': stored_host}

    remote_host = recv_known_host(hostname,
                                  enc=enc,
                                  port=port,
                                  hash_hostname=hash_hostname)
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
    if not uinfo:
        return {'status': 'error',
                'error': 'User {0} does not exist'.format(user)}
    full = os.path.join(uinfo['home'], config)
    line = '{hostname} {enc} {key}\n'.format(**remote_host)

    # ensure ~/.ssh exists
    ssh_dir = os.path.dirname(full)
    try:
        log.debug('Ensuring ssh config dir "{0}" exists'.format(ssh_dir))
        os.makedirs(ssh_dir)
    except OSError as exc:
        if exc[1] == 'Permission denied':
            log.error('Unable to create directory {0}: '
                      '{1}'.format(ssh_dir, exc[1]))
        elif exc[1] == 'File exists':
            log.debug('{0} already exists, no need to create '
                      'it'.format(ssh_dir))
    else:
        # set proper ownership/permissions
        os.chown(ssh_dir, uinfo['uid'], uinfo['gid'])
        os.chmod(ssh_dir, 0700)

    # write line to known_hosts file
    try:
        with salt.utils.fopen(full, 'a') as ofile:
            ofile.write(line)
    except (IOError, OSError) as exception:
        raise CommandExecutionError(
            "Couldn't append to known hosts file: '{0}'".format(exception)
        )

    if os.geteuid() == 0:
        os.chown(full, uinfo['uid'], uinfo['gid'])
    return {'status': 'updated', 'old': stored_host, 'new': remote_host}
