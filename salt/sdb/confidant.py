# -*- coding: utf-8 -*-
'''
An SDB module for getting credentials from confidant.

Configuring the Confidant module
================================

The module can be configured via sdb in the minion config:

.. code-block:: yaml

  confidant:
    driver: confidant
    # The URL of the confidant web service
    url: 'https://confidant-production.example.com'
    # The context to use for KMS authentication
    auth_context:
      from: example-production-iad
      to: confidant-production-iad
      user_type: service
    # The KMS master key to use for authentication
    auth_key: "alias/authnz"
    # Cache file for KMS auth token
    token_cache_file: /run/confidant/confidant_token
    # The duration of the validity of a token, in minutes
    token_duration: 60
    # key, keyid and region can be defined in the profile, but it's generally
    # best to use IAM roles or environment variables for AWS auth.
    keyid: 98nh9h9h908h09kjjk
    key: jhf908gyeghehe0he0g8h9u0j0n0n09hj09h0
    region: us-east-1

:depends: confidant-common, confidant-client

Module Documentation
====================
'''
from __future__ import absolute_import

# Import python libs
import logging
import copy

# Import third party libs
try:
    import confidant.client
    import confidant.formatter
    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

# Set up logging
log = logging.getLogger(__name__)

__virtualname__ = 'confidant'


def __virtual__():
    '''
    Only return if requests and boto are installed.
    '''
    if HAS_LIBS:
        return __virtualname__
    else:
        return False


def get(key, profile=None):
    '''
    Read pillar data from Confidant via its API.

    CLI Example:

        salt myminion sdb.get 'sdb://confidant/credentials'

    Valid keys are: credentials, credentials_metadata, result. credentials
    returns a dict of joined credential_pairs, credentials_metadata returns a
    dict of metadata relevant to the credentials mapped to the confidant
    service, and result returns a bool that can be used to determine if the sdb
    call succeded or failed to fetch credentials from confidant (or from local
    cache). If result is false, the data in credentials or credentials_metadata
    can't be trusted.
    '''
    # default to returning failure
    ret = {'result': False, 'credentials': None, 'credentials_metadata': None}
    profile_data = copy.deepcopy(profile)
    if profile_data.get('disabled', False):
        ret['result'] = True
        return ret.get(key)
    token_version = profile_data.get('token_version', 1)
    try:
        url = profile_data['url']
        auth_key = profile_data['auth_key']
        auth_context = profile_data['auth_context']
        role = auth_context['from']
    except (KeyError, TypeError):
        msg = ('profile has undefined url, auth_key or auth_context')
        log.debug(msg)
        return ret.get(key)
    region = profile_data.get('region', 'us-east-1')
    token_duration = profile_data.get('token_duration', 60)
    retries = profile_data.get('retries', 5)
    token_cache_file = profile_data.get('token_cache_file')
    backoff = profile_data.get('backoff', 1)
    client = confidant.client.ConfidantClient(
        url,
        auth_key,
        auth_context,
        token_lifetime=token_duration,
        token_version=token_version,
        token_cache_file=token_cache_file,
        region=region,
        retries=retries,
        backoff=backoff
    )
    try:
        data = client.get_service(
            role,
            decrypt_blind=True
        )
    except confidant.client.TokenCreationError:
        return ret.get(key)
    if not data['result']:
        return ret.get(key)
    ret = confidant.formatter.combined_credential_pair_format(data)
    ret['result'] = True
    return ret.get(key)
