# -*- coding: utf-8 -*-
'''
Connection library for GitHub
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function
import logging

# Import Salt libs
import salt.utils.json
import salt.utils.http

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def get_user_pubkeys(users):
    '''
    Retrieve a set of public keys from GitHub for the specified list of users.
    Expects input in list format. Optionally, a value in the list may be a dict
    whose value is a list of key IDs to be returned. If this is not done, then
    all keys will be returned.

    Some example data structures that coupld be passed in would look like:

    .. code_block:: yaml

        ['user1', 'user2', 'user3']

        [
            'user1': [
                '12345',
                '67890',
            ],
            'user2',
            'user3',
        ]
    '''
    if not isinstance(users, list):
        return {'Error': 'A list of users is expected'}

    ret = {}
    for user in users:
        key_ids = []
        if isinstance(user, dict):
            tmp_user = next(six.iterkeys(user))
            key_ids = user[tmp_user]
            user = tmp_user

        url = 'https://api.github.com/users/{0}/keys'.format(user)
        result = salt.utils.http.query(
            url,
            'GET',
            decode=False,
            text=True,
        )

        keys = salt.utils.json.loads(result['text'])

        ret[user] = {}
        for key in keys:
            if len(key_ids) > 0:
                if six.text_type(key['id']) in key_ids:
                    ret[user][key['id']] = key['key']
            else:
                ret[user][key['id']] = key['key']

    return ret
