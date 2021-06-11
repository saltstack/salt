"""
This is the default grains matcher function.
"""

import logging

import salt.utils.data
from salt.defaults import DEFAULT_TARGET_DELIM

log = logging.getLogger(__name__)


def match(tgt, delimiter=DEFAULT_TARGET_DELIM, opts=None, minion_id=None):
    """
    Reads in the grains glob match
    """
    if not opts:
        opts = __opts__

    log.debug("grains target: %s", tgt)
    if delimiter not in tgt:
        log.error("Got insufficient arguments for grains match statement from master")
        return False

    return salt.utils.data.subdict_match(opts["grains"], tgt, delimiter=delimiter)
