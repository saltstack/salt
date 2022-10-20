"""
This is the default pcre matcher.
"""

import re


def match(tgt, opts=None, minion_id=None):
    """
    Returns true if the passed pcre regex matches
    """
    if not opts:
        opts = __opts__
    if not minion_id:
        minion_id = opts.get("id")

    return bool(re.match(tgt, minion_id))
