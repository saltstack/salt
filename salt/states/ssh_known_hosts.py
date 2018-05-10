# -*- coding: utf-8 -*-
'''
Control of SSH known_hosts entries
==================================

Manage the information stored in the known_hosts files.

.. code-block:: yaml

    github.com:
      ssh_known_hosts:
        - present
        - user: root
        - fingerprint: 16:27:ac:a5:76:28:2d:36:63:1b:56:4d:eb:df:a6:48
        - fingerprint_hash_type: md5

    example.com:
      ssh_known_hosts:
        - absent
        - user: root
'''
from __future__ import absolute_import, unicode_literals, print_function

# Import Python libs
import os

# Import Salt libs
import salt.utils.platform
from salt.exceptions import CommandNotFoundError

# Define the state's virtual name
__virtualname__ = 'ssh_known_hosts'


def __virtual__():
    '''
    Does not work on Windows, requires ssh module functions
    '''
    if salt.utils.platform.is_windows():
        return False, 'ssh_known_hosts: Does not support Windows'

    return __virtualname__


def present(
        name,
        user=None,
        fingerprint=None,
        key=None,
        port=None,
        enc=None,
        config=None,
        hash_known_hosts=True,
        timeout=5,
        fingerprint_hash_type=None):
    '''
    Verifies that the specified host is known by the specified user

    On many systems, specifically those running with openssh 4 or older, the
    ``enc`` option must be set, only openssh 5 and above can detect the key
    type.

    name
        The name of the remote host (e.g. "github.com")
        Note that only a single hostname is supported, if foo.example.com and
        bar.example.com have the same host you will need two separate Salt
        States to represent them.

    user
        The user who owns the ssh authorized keys file to modify

    fingerprint
        The fingerprint of the key which must be present in the known_hosts
        file (optional if key specified)

    key
        The public key which must be present in the known_hosts file
        (optional if fingerprint specified)

    port
        optional parameter, port which will be used to when requesting the
        public key from the remote host, defaults to port 22.

    enc
        Defines what type of key is being used, can be ed25519, ecdsa ssh-rsa
        or ssh-dss

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

    fingerprint_hash_type
        The public key fingerprint hash type that the public key fingerprint
        was originally hashed with. This defaults to ``sha256`` if not specified.

        .. versionadded:: 2016.11.4
        .. versionchanged:: 2017.7.0: default changed from ``md5`` to ``sha256``

    '''
    ret = {'name': name,
           'changes': {},
           'result': None if __opts__['test'] else True,
           'comment': ''}

    if not user:
        config = config or '/etc/ssh/ssh_known_hosts'
    else:
        config = config or '.ssh/known_hosts'

    if not user and not os.path.isabs(config):
        comment = 'If not specifying a "user", specify an absolute "config".'
        ret['result'] = False
        return dict(ret, comment=comment)

    if __opts__['test']:
        if key and fingerprint:
            comment = 'Specify either "key" or "fingerprint", not both.'
            ret['result'] = False
            return dict(ret, comment=comment)
        elif key and not enc:
            comment = 'Required argument "enc" if using "key" argument.'
            ret['result'] = False
            return dict(ret, comment=comment)

        try:
            result = __salt__['ssh.check_known_host'](user, name,
                                                      key=key,
                                                      fingerprint=fingerprint,
                                                      config=config,
                                                      port=port,
                                                      fingerprint_hash_type=fingerprint_hash_type)
        except CommandNotFoundError as err:
            ret['result'] = False
            ret['comment'] = 'ssh.check_known_host error: {0}'.format(err)
            return ret

        if result == 'exists':
            comment = 'Host {0} is already in {1}'.format(name, config)
            ret['result'] = True
            return dict(ret, comment=comment)
        elif result == 'add':
            comment = 'Key for {0} is set to be added to {1}'.format(name,
                                                                     config)
            return dict(ret, comment=comment)
        else:  # 'update'
            comment = 'Key for {0} is set to be updated in {1}'.format(name,
                                                                     config)
            return dict(ret, comment=comment)

    result = __salt__['ssh.set_known_host'](
        user=user,
        hostname=name,
        fingerprint=fingerprint,
        key=key,
        port=port,
        enc=enc,
        config=config,
        hash_known_hosts=hash_known_hosts,
        timeout=timeout,
        fingerprint_hash_type=fingerprint_hash_type)
    if result['status'] == 'exists':
        return dict(ret,
                    comment='{0} already exists in {1}'.format(name, config))
    elif result['status'] == 'error':
        return dict(ret, result=False, comment=result['error'])
    else:  # 'updated'
        if key:
            new_key = result['new'][0]['key']
            return dict(ret,
                    changes={'old': result['old'], 'new': result['new']},
                    comment='{0}\'s key saved to {1} (key: {2})'.format(
                             name, config, new_key))
        else:
            fingerprint = result['new'][0]['fingerprint']
            return dict(ret,
                    changes={'old': result['old'], 'new': result['new']},
                    comment='{0}\'s key saved to {1} (fingerprint: {2})'.format(
                             name, config, fingerprint))


def absent(name, user=None, config=None):
    '''
    Verifies that the specified host is not known by the given user

    name
        The host name
        Note that only single host names are supported.  If foo.example.com
        and bar.example.com are the same machine and you need to exclude both,
        you will need one Salt state for each.

    user
        The user who owns the ssh authorized keys file to modify

    config
        The location of the authorized keys file relative to the user's home
        directory, defaults to ".ssh/known_hosts". If no user is specified,
        defaults to "/etc/ssh/ssh_known_hosts". If present, must be an
        absolute path when a user is not specified.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if not user:
        config = config or '/etc/ssh/ssh_known_hosts'
    else:
        config = config or '.ssh/known_hosts'

    if not user and not os.path.isabs(config):
        comment = 'If not specifying a "user", specify an absolute "config".'
        ret['result'] = False
        return dict(ret, comment=comment)

    known_host = __salt__['ssh.get_known_host_entries'](user=user, hostname=name, config=config)
    if not known_host:
        return dict(ret, comment='Host is already absent')

    if __opts__['test']:
        comment = 'Key for {0} is set to be removed from {1}'.format(name,
                                                                     config)
        ret['result'] = None
        return dict(ret, comment=comment)

    rm_result = __salt__['ssh.rm_known_host'](user=user, hostname=name, config=config)
    if rm_result['status'] == 'error':
        return dict(ret, result=False, comment=rm_result['error'])
    else:
        return dict(ret,
                    changes={'old': known_host, 'new': None},
                    result=True,
                    comment=rm_result['comment'])
