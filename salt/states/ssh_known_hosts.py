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

    example.com:
      ssh_known_hosts:
        - absent
        - user: root
'''
from __future__ import absolute_import

# Import python libs
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError


def present(
        name,
        user=None,
        fingerprint=None,
        key=None,
        port=None,
        enc=None,
        config=None,
        hash_hostname=True,
        hash_known_hosts=True):
    '''
    Verifies that the specified host is known by the specified user

    On many systems, specifically those running with openssh 4 or older, the
    ``enc`` option must be set, only openssh 5 and above can detect the key
    type.

    name
        The name of the remote host (e.g. "github.com")

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

    hash_hostname : True
        Hash all hostnames and addresses in the known hosts file.

        .. deprecated:: Carbon

            Please use hash_known_hosts instead.

    hash_known_hosts : True
        Hash all hostnames and addresses in the known hosts file.
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

    if not hash_hostname:
        salt.utils.warn_until(
            'Carbon',
            'The hash_hostname parameter is misleading as ssh-keygen can only '
            'hash the whole known hosts file, not entries for individual'
            'hosts. Please use hash_known_hosts=False instead.')
        hash_known_hosts = hash_hostname

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
                                                      config=config)
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

    result = __salt__['ssh.set_known_host'](user=user, hostname=name,
                fingerprint=fingerprint,
                key=key,
                port=port,
                enc=enc,
                config=config,
                hash_known_hosts=hash_known_hosts)
    if result['status'] == 'exists':
        return dict(ret,
                    comment='{0} already exists in {1}'.format(name, config))
    elif result['status'] == 'error':
        return dict(ret, result=False, comment=result['error'])
    else:  # 'updated'
        if key:
            new_key = result['new']['key']
            return dict(ret,
                    changes={'old': result['old'], 'new': result['new']},
                    comment='{0}\'s key saved to {1} (key: {2})'.format(
                             name, config, new_key))
        else:
            fingerprint = result['new']['fingerprint']
            return dict(ret,
                    changes={'old': result['old'], 'new': result['new']},
                    comment='{0}\'s key saved to {1} (fingerprint: {2})'.format(
                             name, config, fingerprint))


def absent(name, user=None, config=None):
    '''
    Verifies that the specified host is not known by the given user

    name
        The host name

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

    known_host = __salt__['ssh.get_known_host'](user=user, hostname=name, config=config)
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
