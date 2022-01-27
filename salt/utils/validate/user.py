"""
Various user validation utilities
"""

import logging
import re

log = logging.getLogger(__name__)

VALID_USERNAME = re.compile(r"[a-z_][a-z0-9_-]*[$]?", re.IGNORECASE)


def valid_username(user):
    """
    Validates a username based on the guidelines in `useradd(8)`
    """
    if not isinstance(user, str):
        return False

    if len(user) > 32:
        return False

    return VALID_USERNAME.match(user) is not None
