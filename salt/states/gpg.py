# -*- coding: utf-8 -*-
'''
Management of the GPG keychains
==============================

.. versionadded:: 2016.3.0

'''


from __future__ import absolute_import
from salt.ext.six import string_types

import logging
log = logging.getLogger(__name__)

_VALID_TRUST_VALUES = ['expired',
                       'unknown',
                       'not_trusted',
                       'marginally',
                       'fully',
                       'ultimately']

TRUST_MAP = {
    'expired': 'Expired',
    'unknown': 'Unknown',
    'not_trusted': 'Not Trusted',
    'marginally': 'Marginally',
    'fully': 'Fully Trusted',
    'ultimately': 'Ultimately Trusted'
}


def present(name,
            keys=None,
            user=None,
            keyserver=None,
            gnupghome=None,
            trust=None,
            **kwargs):
    '''
    Ensure GPG public key is present in keychain

    name
        The unique name or keyid for the GPG public key.

    keys
        The keyId or keyIds to add to the GPG keychain.

    user
        Add GPG keys to the user's keychain

    keyserver
        The keyserver to retrieve the keys from.

    gnupghome
        Override GNUPG Home directory

    trust
        Trust level for the key in the keychain,
        ignored by default.  Valid trust levels:
        expired, unknown, not_trusted, marginally,
        fully, ultimately


    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    _current_keys = __salt__['gpg.list_keys']()

    current_keys = {}
    for key in _current_keys:
        keyid = key['keyid']
        current_keys[keyid] = {}
        current_keys[keyid]['trust'] = key['trust']

    if not keys:
        keys = name

    if isinstance(keys, string_types):
        keys = [keys]

    for key in keys:
        if key in current_keys.keys():
            if trust:
                if trust in _VALID_TRUST_VALUES:
                    if current_keys[key]['trust'] != TRUST_MAP[trust]:
                        # update trust level
                        result = __salt__['gpg.trust_key'](keyid=key,
                                                           trust_level=trust,
                                                           user=user,
                                                           )
                        if 'result' in result and not result['result']:
                            ret['result'] = result['result']
                            ret['comment'].append(result['comment'])
                        else:
                            ret['comment'].append('Set trust level for {0} to {1}'.format(key, trust))
                    else:
                        ret['comment'].append('GPG Public Key {0} already in correct trust state'.format(key))
                else:
                    ret['comment'].append('Invalid trust level {0}'.format(trust))

            ret['comment'].append('GPG Public Key {0} already in keychain '.format(key))

        else:
            result = __salt__['gpg.receive_keys'](keyserver,
                                                  key,
                                                  user,
                                                  gnupghome,
                                                  )
            if 'result' in result and not result['result']:
                ret['result'] = result['result']
                ret['comment'].append(result['comment'])
            else:
                ret['comment'].append('Adding {0} to GPG keychain'.format(name))

            if trust:
                if trust in _VALID_TRUST_VALUES:
                    result = __salt__['gpg.trust_key'](keyid=key,
                                                       trust_level=trust,
                                                       user=user,
                                                       )
                    if 'result' in result and not result['result']:
                        ret['result'] = result['result']
                        ret['comment'].append(result['comment'])
                    else:
                        ret['comment'].append('Set trust level for {0} to {1}'.format(key, trust))
                else:
                    ret['comment'].append('Invalid trust level {0}'.format(trust))

        ret['comment'] = '\n'.join(ret['comment'])
    return ret


def absent(name,
           keys=None,
           user=None,
           gnupghome=None,
           **kwargs):
    '''
    Ensure GPG public key is absent in keychain

    name
        The unique name or keyid for the GPG public key.

    keys
        The keyId or keyIds to add to the GPG keychain.

    user
        Add GPG keys to the user's keychain

    gnupghome
        Override GNUPG Home directory

    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': []}

    _current_keys = __salt__['gpg.list_keys']()

    current_keys = []
    for key in _current_keys:
        current_keys.append(key['keyid'])

    if not keys:
        keys = name

    if isinstance(keys, string_types):
        keys = [keys]

    for key in keys:
        if key in current_keys:
            result = __salt__['gpg.delete_key'](key,
                                                user,
                                                gnupghome,
                                                )
            if 'result' in result and not result['result']:
                ret['result'] = result['result']
                ret['comment'].append(result['comment'])
            else:
                ret['comment'].append('Deleting {0} from GPG keychain'.format(name))
        else:
            ret['comment'].append('{0} not found in GPG keychain'.format(name))
        ret['comment'] = '\n'.join(ret['comment'])
    return ret
