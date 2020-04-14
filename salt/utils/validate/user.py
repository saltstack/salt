# -*- coding: utf-8 -*-
"""
Various user validation utilities
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import re

from salt.ext import six

log = logging.getLogger(__name__)

VALID_USERNAME = re.compile(r"[a-z_][a-z0-9_-]*[$]?", re.IGNORECASE)


def valid_username(user):
    """
    Validates a username based on the guidelines in `useradd(8)`
    """
    if not isinstance(user, six.string_types):
        return False

    if len(user) > 32:
        return False

    return VALID_USERNAME.match(user) is not None
