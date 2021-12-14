"""
This is the default glob matcher function.
"""

import fnmatch
import logging

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Returns true if the passed glob matches the id
    """
    if not opts:
        opts = __opts__
    if not minion_id:
        minion_id = opts.get("minion_id", opts["id"])
    if not isinstance(tgt, str):
        return False

    return fnmatch.fnmatch(minion_id, tgt)
