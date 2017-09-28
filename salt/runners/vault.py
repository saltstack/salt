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
import string
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
    mappings = {'minion': minion_id, 'grains': grains or {}}

    policies = []
    for pattern in policy_patterns:
        try:
            for expanded_pattern in _expand_pattern_lists(pattern, **mappings):
                policies.append(
                                expanded_pattern.format(**mappings)
                                                .lower()  # Vault requirement
                               )
        except KeyError:
            log.warning('Could not resolve policy pattern {0}'.format(pattern))

    log.debug('{0} policies: {1}'.format(minion_id, policies))
    return policies


def _expand_pattern_lists(pattern, **mappings):
    '''
    Expands the pattern for any list-valued mappings, such that for any list of
    length N in the mappings present in the pattern, N copies of the pattern are
    returned, each with an element of the list substituted.

    pattern:
        A pattern to expand, for example ``by-role/{grains[roles]}``

    mappings:
        A dictionary of variables that can be expanded into the pattern.

    Example: Given the pattern `` by-role/{grains[roles]}`` and the below grains

    .. code-block:: yaml

        grains:
            roles:
                - web
                - database

    This function will expand into two patterns,
    ``[by-role/web, by-role/database]``.

    Note that this method does not expand any non-list patterns.
    '''
    expanded_patterns = []
    f = string.Formatter()
    '''
    This function uses a string.Formatter to get all the formatting tokens from
    the pattern, then recursively replaces tokens whose expanded value is a
    list. For a list with N items, it will create N new pattern strings and
    then continue with the next token. In practice this is expected to not be
    very expensive, since patterns will typically involve a handful of lists at
    most.
    '''  # pylint: disable=W0105
    for (_, field_name, _, _) in f.parse(pattern):
        if field_name is None:
            continue
        (value, _) = f.get_field(field_name, None, mappings)
        if isinstance(value, list):
            token = '{{{0}}}'.format(field_name)
            expanded = [pattern.replace(token, str(elem)) for elem in value]
            for expanded_item in expanded:
                result = _expand_pattern_lists(expanded_item, **mappings)
                expanded_patterns += result
            return expanded_patterns
    return [pattern]
