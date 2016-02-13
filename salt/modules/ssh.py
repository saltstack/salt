# -*- coding: utf-8 -*-
'''
Manage client ssh components

.. note::

    This module requires the use of MD5 hashing. Certain security audits may
    not permit the use of MD5. For those cases, this module should be disabled
    or removed.
'''

from __future__ import absolute_import

# Import python libs
import binascii
import hashlib
import logging
import os
import re
import subprocess

# Import salt libs
import salt.utils
import salt.utils.files
import salt.utils.decorators as decorators
from salt.exceptions import (
    SaltInvocationError,
    CommandExecutionError,
)
from salt.ext.six.moves import range

log = logging.getLogger(__name__)
DEFAULT_SSH_PORT = 22


def __virtual__():
    # TODO: This could work on windows with some love
    if salt.utils.is_windows():
        return (False, 'The module cannot be loaded on windows.')
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
    ed25519 = ['ed25519', 'ssh-ed25519']

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
    elif enc in ed25519:
        return 'ssh-ed25519'
    else:
        raise CommandExecutionError(
            'Incorrect encryption key type \'{0}\'.'.format(enc)
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


def _expand_authorized_keys_path(path, user, home):
    '''
    Expand the AuthorizedKeysFile expression. Defined in man sshd_config(5)
    '''
    converted_path = ''
    had_escape = False
    for char in path:
        if had_escape:
            had_escape = False
            if char == '%':
                converted_path += '%'
            elif char == 'u':
                converted_path += user
            elif char == 'h':
                converted_path += home
            else:
                error = 'AuthorizedKeysFile path: unknown token character "%{0}"'.format(char)
                raise CommandExecutionError(error)
            continue
        elif char == '%':
            had_escape = True
        else:
            converted_path += char
    if had_escape:
        error = "AuthorizedKeysFile path: Last character can't be escape character"
        raise CommandExecutionError(error)
    return converted_path


def _get_config_file(user, config):
    '''
    Get absolute path to a user's ssh_config.
    '''
    uinfo = __salt__['user.info'](user)
    if not uinfo:
        raise CommandExecutionError('User \'{0}\' does not exist'.format(user))
    home = uinfo['home']
    config = _expand_authorized_keys_path(config, user, home)
    if not os.path.isabs(config):
        config = os.path.join(home, config)
    return config


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
    full = _get_config_file(user, config)

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


def _get_known_hosts_file(config=None, user=None):
    if user:
        config = config or '.ssh/known_hosts'
    else:
        config = config or '/etc/ssh/ssh_known_hosts'

    if os.path.isabs(config):
        full = config
    else:
        if user:
            uinfo = __salt__['user.info'](user)
            if not uinfo:
                return {'status': 'error',
                        'error': 'User {0} does not exist'.format(user)}
            full = os.path.join(uinfo['home'], config)
        else:
            return {
                'status': 'error',
                'error': 'Cannot determine absolute path to file.'
            }

    return full


def host_keys(keydir=None, private=True):
    '''
    Return the minion's host keys

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.host_keys
        salt '*' ssh.host_keys keydir=/etc/ssh
        salt '*' ssh.host_keys keydir=/etc/ssh private=False
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
            if fn_.endswith('.pub') is False and private is False:
                log.info(
                    'Skipping private key file {0} as private is set to False'
                    .format(fn_)
                )
                continue

            top = fn_.split('.')
            comps = top[0].split('_')
            kname = comps[2]
            if len(top) > 1:
                kname += '.{0}'.format(top[1])
            try:
                with salt.utils.fopen(os.path.join(keydir, fn_), 'r') as _fh:
                    # As of RFC 4716 "a key file is a text file, containing a
                    # sequence of lines", although some SSH implementations
                    # (e.g. OpenSSH) manage their own format(s).  Please see
                    # #20708 for a discussion about how to handle SSH key files
                    # in the future
                    keys[kname] = _fh.readline()
                    # only read the whole file if it is not in the legacy 1.1
                    # binary format
                    if keys[kname] != "SSH PRIVATE KEY FILE FORMAT 1.1\n":
                        keys[kname] += _fh.read()
                    keys[kname] = keys[kname].strip()
            except (IOError, OSError):
                keys[kname] = ''
    return keys


def auth_keys(user=None, config='.ssh/authorized_keys'):
    '''
    Return the authorized keys for users

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.auth_keys
        salt '*' ssh.auth_keys root
        salt '*' ssh.auth_keys user=root
        salt '*' ssh.auth_keys user="[user1, user2]"
    '''
    if not user:
        user = __salt__['user.list_users']()

    old_output_when_one_user = False
    if not isinstance(user, list):
        user = [user]
        old_output_when_one_user = True

    keys = {}
    for u in user:
        full = None
        try:
            full = _get_config_file(u, config)
        except CommandExecutionError:
            pass

        if full and os.path.isfile(full):
            keys[u] = _validate_keys(full)

    if old_output_when_one_user:
        if user[0] in keys:
            return keys[user[0]]
        else:
            return {}

    return keys


def check_key_file(user,
                   source,
                   config='.ssh/authorized_keys',
                   saltenv='base'):
    '''
    Check a keyfile from a source destination against the local keys and
    return the keys to change

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_key_file root salt://ssh/keyfile
    '''
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


def check_key(user, key, enc, comment, options, config='.ssh/authorized_keys',
              cache_keys=None):
    '''
    Check to see if a key needs updating, returns "update", "add" or "exists"

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.check_key <user> <key> <enc> <comment> <options>
    '''
    if cache_keys is None:
        cache_keys = []
    enc = _refine_enc(enc)
    current = auth_keys(user, config)
    nline = _format_auth_line(key, enc, comment, options)

    # Removing existing keys from the auth_keys isn't really a good idea
    # in fact
    #
    # as:
    #   - We can have non-salt managed keys in that file
    #   - We can have multiple states defining keys for an user
    #     and with such code only one state will win
    #     the remove all-other-keys war
    #
    # if cache_keys:
    #     for pub_key in set(current).difference(set(cache_keys)):
    #         rm_auth_key(user, pub_key)

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


def rm_auth_key_from_file(user,
             source,
             config='.ssh/authorized_keys',
             saltenv='base'):
    '''
    Remove an authorized key from the specified user's authorized key file,
    using a file as source

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_auth_key_from_file <user> salt://ssh_keys/<user>.id_rsa.pub
    '''
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
            rval += rm_auth_key(
                user,
                key,
                config
            )
        # Due to the ability for a single file to have multiple keys, it's
        # possible for a single call to this function to have both "replace"
        # and "new" as possible valid returns. I ordered the following as I
        # thought best.
        if 'Key not removed' in rval:
            return 'Key not removed'
        elif 'Key removed' in rval:
            return 'Key removed'
        else:
            return 'Key not present'


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
        full = _get_config_file(user, config)

        # Return something sensible if the file doesn't exist
        if not os.path.isfile(full):
            return 'Authorized keys file {0} not present'.format(full)

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
            log.warning('Could not read/write key file: {0}'.format(str(exc)))
            return 'Key not removed'
        return 'Key removed'
    # TODO: Should this function return a simple boolean?
    return 'Key not present'


def set_auth_key_from_file(user,
                           source,
                           config='.ssh/authorized_keys',
                           saltenv='base'):
    '''
    Add a key to the authorized_keys file, using a file as the source.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key_from_file <user> salt://ssh_keys/<user>.id_rsa.pub
    '''
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
                config,
                list(s_keys.keys())
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
        config='.ssh/authorized_keys',
        cache_keys=None):
    '''
    Add a key to the authorized_keys file. The "key" parameter must only be the
    string of text that is the encoded key. If the key begins with "ssh-rsa"
    or ends with user@host, remove those from the key before passing it to this
    function.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_auth_key <user> '<key>' enc='dsa'
    '''
    if cache_keys is None:
        cache_keys = []
    if len(key.split()) > 1:
        return 'invalid'

    enc = _refine_enc(enc)
    uinfo = __salt__['user.info'](user)
    if not uinfo:
        return 'fail'
    status = check_key(user, key, enc, comment, options, config, cache_keys)
    if status == 'update':
        _replace_auth_key(user, key, enc, comment, options or [], config)
        return 'replace'
    elif status == 'exists':
        return 'no change'
    else:
        auth_line = _format_auth_line(key, enc, comment, options)
        fconfig = _get_config_file(user, config)
        # Fail if the key lives under the user's homedir, and the homedir
        # doesn't exist
        udir = uinfo.get('home', '')
        if fconfig.startswith(udir) and not os.path.isdir(udir):
            return 'fail'
        if not os.path.isdir(os.path.dirname(fconfig)):
            dpath = os.path.dirname(fconfig)
            os.makedirs(dpath)
            if os.geteuid() == 0:
                os.chown(dpath, uinfo['uid'], uinfo['gid'])
            os.chmod(dpath, 448)
            # If SELINUX is available run a restorecon on the file
            rcon = salt.utils.which('restorecon')
            if rcon:
                cmd = [rcon, dpath]
                subprocess.call(cmd)

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
            # If SELINUX is available run a restorecon on the file
            rcon = salt.utils.which('restorecon')
            if rcon:
                cmd = [rcon, fconfig]
                subprocess.call(cmd)
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
def get_known_host(user, hostname, config=None, port=None):
    '''
    Return information about known host from the configfile, if any.
    If there is no such key, return None.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.get_known_host <user> <hostname>
    '''
    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    ssh_hostname = _hostname_and_port_to_ssh_hostname(hostname, port)
    cmd = ['ssh-keygen', '-F', ssh_hostname, '-f', full]
    lines = __salt__['cmd.run'](cmd,
                                ignore_retcode=True,
                                python_shell=False).splitlines()
    known_hosts = list(_parse_openssh_output(lines))
    return known_hosts[0] if known_hosts else None


@decorators.which('ssh-keyscan')
def recv_known_host(hostname,
                    enc=None,
                    port=None,
                    hash_hostname=True,
                    hash_known_hosts=True,
                    timeout=5):
    '''
    Retrieve information about host public key from remote server

    hostname
        The name of the remote host (e.g. "github.com")

    enc
        Defines what type of key is being used, can be ed25519, ecdsa ssh-rsa
        or ssh-dss

    port
        optional parameter, denoting the port of the remote host, which will be
        used in case, if the public key will be requested from it. By default
        the port 22 is used.

    hash_hostname : True
        Hash all hostnames and addresses in the known hosts file.

        .. deprecated:: Carbon

            Please use hash_known_hosts instead.

    hash_known_hosts : True
        Hash all hostnames and addresses in the known hosts file.

    timeout : int
        Set the timeout for connection attempts.  If ``timeout`` seconds have
        elapsed since a connection was initiated to a host or since the last
        time anything was read from that host, then the connection is closed
        and the host in question considered unavailable.  Default is 5 seconds.

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.recv_known_host <hostname> enc=<enc> port=<port>
    '''

    if not hash_hostname:
        salt.utils.warn_until(
            'Carbon',
            'The hash_hostname parameter is misleading as ssh-keygen can only '
            'hash the whole known hosts file, not entries for individual '
            'hosts. Please use hash_known_hosts=False instead.')
        hash_known_hosts = hash_hostname

    # The following list of OSes have an old version of openssh-clients
    # and thus require the '-t' option for ssh-keyscan
    need_dash_t = ('CentOS-5',)

    cmd = ['ssh-keyscan']
    if port:
        cmd.extend(['-p', port])
    if enc:
        cmd.extend(['-t', enc])
    if not enc and __grains__.get('osfinger') in need_dash_t:
        cmd.extend(['-t', 'rsa'])
    if hash_known_hosts:
        cmd.append('-H')
    cmd.extend(['-T', str(timeout)])
    cmd.append(hostname)
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    known_hosts = list(_parse_openssh_output(lines))
    return known_hosts[0] if known_hosts else None


def check_known_host(user=None, hostname=None, key=None, fingerprint=None,
                     config=None, port=None):
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
    if not hostname:
        return {'status': 'error',
                'error': 'hostname argument required'}
    if not user:
        config = config or '/etc/ssh/ssh_known_hosts'
    else:
        config = config or '.ssh/known_hosts'

    known_host = get_known_host(user, hostname, config=config, port=port)

    if not known_host or 'fingerprint' not in known_host:
        return 'add'
    if key:
        return 'exists' if key == known_host['key'] else 'update'
    elif fingerprint:
        return ('exists' if fingerprint == known_host['fingerprint']
                else 'update')
    else:
        return 'exists'


def rm_known_host(user=None, hostname=None, config=None, port=None):
    '''
    Remove all keys belonging to hostname from a known_hosts file.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.rm_known_host <user> <hostname>
    '''
    if not hostname:
        return {'status': 'error',
                'error': 'hostname argument required'}

    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    if not os.path.isfile(full):
        return {'status': 'error',
                'error': 'Known hosts file {0} does not exist'.format(full)}

    ssh_hostname = _hostname_and_port_to_ssh_hostname(hostname, port)
    cmd = ['ssh-keygen', '-R', ssh_hostname, '-f', full]
    cmd_result = __salt__['cmd.run'](cmd, python_shell=False)
    # ssh-keygen creates a new file, thus a chown is required.
    if os.geteuid() == 0 and user:
        uinfo = __salt__['user.info'](user)
        os.chown(full, uinfo['uid'], uinfo['gid'])
    return {'status': 'removed', 'comment': cmd_result}


def set_known_host(user=None,
                   hostname=None,
                   fingerprint=None,
                   key=None,
                   port=None,
                   enc=None,
                   hash_hostname=True,
                   config=None,
                   hash_known_hosts=True,
                   timeout=5):
    '''
    Download SSH public key from remote host "hostname", optionally validate
    its fingerprint against "fingerprint" variable and save the record in the
    known_hosts file.

    If such a record does already exists in there, do nothing.

    user
        The user who owns the ssh authorized keys file to modify

    hostname
        The name of the remote host (e.g. "github.com")

    fingerprint
        The fingerprint of the key which must be presented in the known_hosts
        file (optional if key specified)

    key
        The public key which must be presented in the known_hosts file
        (optional if fingerprint specified)

    port
        optional parameter, denoting the port of the remote host, which will be
        used in case, if the public key will be requested from it. By default
        the port 22 is used.

    enc
        Defines what type of key is being used, can be ed25519, ecdsa ssh-rsa
        or ssh-dss

    hash_hostname : True
        Hash all hostnames and addresses in the known hosts file.

        .. deprecated:: Carbon

            Please use hash_known_hosts instead.

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/known_hosts". If no user is specified,
        defaults to "/etc/ssh/ssh_known_hosts". If present, must be an
        absolute path when a user is not specified.

    hash_known_hosts : True
        Hash all hostnames and addresses in the known hosts file.

    timeout : int
        Set the timeout for connection attempts.  If ``timeout`` seconds have
        elapsed since a connection was initiated to a host or since the last
        time anything was read from that host, then the connection is closed
        and the host in question considered unavailable.  Default is 5 seconds.

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.set_known_host <user> fingerprint='xx:xx:..:xx' enc='ssh-rsa' config='.ssh/known_hosts'
    '''
    if not hostname:
        return {'status': 'error',
                'error': 'hostname argument required'}

    if not hash_hostname:
        salt.utils.warn_until(
            'Carbon',
            'The hash_hostname parameter is misleading as ssh-keygen can only '
            'hash the whole known hosts file, not entries for individual '
            'hosts. Please use hash_known_hosts=False instead.')
        hash_known_hosts = hash_hostname

    if port is not None and port != DEFAULT_SSH_PORT and hash_known_hosts:
        return {'status': 'error',
                'error': 'argument port can not be used in '
                'conjunction with argument hash_known_hosts'}

    update_required = False
    check_required = False
    stored_host = get_known_host(user, hostname, config, port)

    if not stored_host:
        update_required = True
    elif fingerprint and fingerprint != stored_host['fingerprint']:
        update_required = True
    elif key and key != stored_host['key']:
        update_required = True
    elif key != stored_host['key']:
        check_required = True

    if not update_required and not check_required:
        return {'status': 'exists', 'key': stored_host['key']}

    if not key:
        remote_host = recv_known_host(hostname,
                                      enc=enc,
                                      port=port,
                                      hash_known_hosts=hash_known_hosts,
                                      timeout=timeout)
        if not remote_host:
            return {'status': 'error',
                    'error': 'Unable to receive remote host key'}

        if fingerprint and fingerprint != remote_host['fingerprint']:
            return {'status': 'error',
                    'error': ('Remote host public key found but its fingerprint '
                              'does not match one you have provided')}

        if check_required:
            if remote_host['key'] == stored_host['key']:
                return {'status': 'exists', 'key': stored_host['key']}

    # remove everything we had in the config so far
    rm_known_host(user, hostname, config=config)
    # set up new value

    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full

    if key:
        remote_host = {'hostname': hostname, 'enc': enc, 'key': key}

    if hash_known_hosts or port in [DEFAULT_SSH_PORT, None] or ':' in remote_host['hostname']:
        line = '{hostname} {enc} {key}\n'.format(**remote_host)
    else:
        remote_host['port'] = port
        line = '[{hostname}]:{port} {enc} {key}\n'.format(**remote_host)

    # ensure ~/.ssh exists
    ssh_dir = os.path.dirname(full)
    if user:
        uinfo = __salt__['user.info'](user)

    try:
        log.debug('Ensuring ssh config dir "{0}" exists'.format(ssh_dir))
        os.makedirs(ssh_dir)
    except OSError as exc:
        if exc.args[1] == 'Permission denied':
            log.error('Unable to create directory {0}: '
                      '{1}'.format(ssh_dir, exc.args[1]))
        elif exc.args[1] == 'File exists':
            log.debug('{0} already exists, no need to create '
                      'it'.format(ssh_dir))
    else:
        # set proper ownership/permissions
        if user:
            os.chown(ssh_dir, uinfo['uid'], uinfo['gid'])
            os.chmod(ssh_dir, 0o700)

    # write line to known_hosts file
    try:
        with salt.utils.fopen(full, 'a') as ofile:
            ofile.write(line)
    except (IOError, OSError) as exception:
        raise CommandExecutionError(
            "Couldn't append to known hosts file: '{0}'".format(exception)
        )

    if os.geteuid() == 0 and user:
        os.chown(full, uinfo['uid'], uinfo['gid'])
    os.chmod(full, 0o644)

    if key and hash_known_hosts:
        cmd_result = __salt__['ssh.hash_known_hosts'](user=user, config=full)

    return {'status': 'updated', 'old': stored_host, 'new': remote_host}


def user_keys(user=None, pubfile=None, prvfile=None):
    '''

    Return the user's ssh keys on the minion

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.user_keys
        salt '*' ssh.user_keys user=user1
        salt '*' ssh.user_keys user=user1 pubfile=/home/user1/.ssh/id_rsa.pub prvfile=/home/user1/.ssh/id_rsa
        salt '*' ssh.user_keys user=user1 prvfile=False
        salt '*' ssh.user_keys user="['user1','user2'] pubfile=id_rsa.pub prvfile=id_rsa

    As you can see you can tell Salt not to read from the user's private (or
    public) key file by setting the file path to ``False``. This can be useful
    to prevent Salt from publishing private data via Salt Mine or others.
    '''
    if not user:
        user = __salt__['user.list_users']()

    if not isinstance(user, list):
        # only one so convert to list
        user = [user]

    keys = {}
    for u in user:
        keys[u] = {}
        userinfo = __salt__['user.info'](u)

        if 'home' not in userinfo:
            # no home directory, skip
            continue

        userKeys = []

        if pubfile:
            userKeys.append(pubfile)
        elif pubfile is not False:
            # Add the default public keys
            userKeys += ['id_rsa.pub', 'id_dsa.pub',
                         'id_ecdsa.pub', 'id_ed25519.pub']

        if prvfile:
            userKeys.append(prvfile)
        elif prvfile is not False:
            # Add the default private keys
            userKeys += ['id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519']

        for key in userKeys:
            if key.startswith('/'):
                keyname = os.path.basename(key)
                fn_ = key
            else:
                # if not full path, assume key is in .ssh
                # in user's home directory
                keyname = key
                fn_ = '{0}/.ssh/{1}'.format(userinfo['home'], key)

            if os.path.exists(fn_):
                try:
                    with salt.utils.fopen(fn_, 'r') as _fh:
                        keys[u][keyname] = ''.join(_fh.readlines())
                except (IOError, OSError):
                    pass

    # clean up any empty items
    _keys = {}
    for key in keys:
        if keys[key]:
            _keys[key] = keys[key]
    return _keys


@decorators.which('ssh-keygen')
def hash_known_hosts(user=None, config=None):
    '''

    Hash all the hostnames in the known hosts file.

    .. versionadded:: 2014.7.0

    user
        hash known hosts of this user

    config
        path to known hosts file: can be absolute or relative to user's home
        directory

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.hash_known_hosts

    '''
    full = _get_known_hosts_file(config=config, user=user)

    if isinstance(full, dict):
        return full  # full contains error information

    if not os.path.isfile(full):
        return {'status': 'error',
                'error': 'Known hosts file {0} does not exist'.format(full)}
    cmd = ['ssh-keygen', '-H', '-f', full]
    cmd_result = __salt__['cmd.run'](cmd, python_shell=False)
    # ssh-keygen creates a new file, thus a chown is required.
    if os.geteuid() == 0 and user:
        uinfo = __salt__['user.info'](user)
        os.chown(full, uinfo['uid'], uinfo['gid'])
    return {'status': 'updated', 'comment': cmd_result}


def _hostname_and_port_to_ssh_hostname(hostname, port=DEFAULT_SSH_PORT):
    if not port or port == DEFAULT_SSH_PORT:
        return hostname
    else:
        return '[{0}]:{1}'.format(hostname, port)


def key_is_encrypted(key):
    '''
    .. versionadded:: 2015.8.7

    Function to determine whether or not a private key is encrypted with a
    passphrase.

    Checks key for a ``Proc-Type`` header with ``ENCRYPTED`` in the value. If
    found, returns ``True``, otherwise returns ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' ssh.key_is_encrypted /root/id_rsa
    '''
    try:
        with salt.utils.fopen(key, 'r') as fp_:
            key_data = fp_.read()
    except (IOError, OSError) as exc:
        # Raise a CommandExecutionError
        salt.utils.files.process_read_exception(exc, key)

    is_private_key = re.search(r'BEGIN (?:\w+\s)*PRIVATE KEY', key_data)
    is_encrypted = 'ENCRYPTED' in key_data
    del key_data

    if not is_private_key:
        raise CommandExecutionError('{0} is not a private key'.format(key))

    return is_encrypted
