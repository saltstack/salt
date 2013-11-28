# -*- coding: utf-8 -*-
'''
Various user validation utilities
'''

# Import python libs
import re
import logging
import salt._compat

log = logging.getLogger(__name__)

VALID_USERNAME = re.compile(r'[a-z_][a-z0-9_-]*[$]?', re.IGNORECASE)


def valid_username(user):
    '''
    Validates a username based on the guidelines in `useradd(8)`
    '''
    if not isinstance(user, salt._compat.string_types):
        return False

    if len(user) > 32:
        return False

    return VALID_USERNAME.match(user) is not None
