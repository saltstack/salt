# -*- coding: utf-8 -*-
'''
:maintainer:    SaltStack
:maturity:      new
:platform:      all

Runner functions supporting the Vault modules. Configuration instructions are
documented in the execution module docs.
'''

from __future__ import absolute_import
import base64
import logging
import requests

import salt.crypt
import salt.exceptions


log = logging.getLogger(__name__)


def generate_token(minion_id, signature, impersonated_by_master=False):
    '''
    Generate a Vault token for minion minion_id

    minion_id
        The id of the minion that requests a token

    signature
        Cryptographic signature which validates that the request is indeed sent
        by the minion (or the master, see impersonated_by_master).

    impersonated_by_master
        If the master needs to create a token on behalf of the minion, this is
        True. This happens when the master generates minion pillars.
    '''
    log.debug('Token generation request for {0} (impersonated by master: {1})'.
              format(minion_id, impersonated_by_master))
    _validate_signature(minion_id, signature, impersonated_by_master)

    try:
        config = __opts__['vault']

        url = '{0}/v1/auth/token/create'.format(config['url'])
        headers = {'X-Vault-Token': config['auth']['token']}
        audit_data = {
            'saltstack-jid': globals().get('__jid__', '<no jid set>'),
            'saltstack-minion': minion_id,
            'saltstack-user': globals().get('__user__', '<no user set>')
        }
        payload = {
                    'policies': _get_policies(minion_id, config),
                    'num_uses': 1,
                    'metadata': audit_data
                  }

        log.trace('Sending token creation request to Vault')
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            return {'error': response.reason}

        authData = response.json()['auth']
        return {'token': authData['client_token'], 'url': config['url']}
    except Exception as e:
        return {'error': str(e)}


def show_policies(minion_id):
    '''
    Show the Vault policies that are applied to tokens for the given minion

    minion_id
        The minions id

    CLI Example:

    .. code-block:: bash

        salt-run vault.show_policies myminion
    '''
    config = __opts__['vault']
    return _get_policies(minion_id, config)


def _validate_signature(minion_id, signature, impersonated_by_master):
    '''
    Validate that either minion with id minion_id, or the master, signed the
    request
    '''
    pki_dir = __opts__['pki_dir']
    if impersonated_by_master:
        public_key = '{0}/master.pub'.format(pki_dir)
    else:
        public_key = '{0}/minions/{1}'.format(pki_dir, minion_id)

    log.trace('Validating signature for {0}'.format(minion_id))
    signature = base64.b64decode(signature)
    if not salt.crypt.verify_signature(public_key, minion_id, signature):
        raise salt.exceptions.AuthenticationError(
            'Could not validate token request from {0}'.format(minion_id)
            )
    log.trace('Signature ok')


def _get_policies(minion_id, config):
    '''
    Get the policies that should be applied to a token for minion_id
    '''
    _, grains, _ = salt.utils.minions.get_minion_data(minion_id, __opts__)
    policy_patterns = config.get(
                                 'policies',
                                 ['saltstack/minion/{minion}', 'saltstack/minions']
                                )
    mappings = {'minion': minion_id, 'grains': grains}

    policies = []
    for pattern in policy_patterns:
        policies.append(pattern.format(**mappings))

    log.debug('{0} policies: {1}'.format(minion_id, policies))
    return policies
