"""
This is the default pillar matcher function.
"""

import logging

import salt.utils.data
from salt.defaults import DEFAULT_TARGET_DELIM

log = logging.getLogger(__name__)


def match(tgt, delimiter=DEFAULT_TARGET_DELIM, opts=None, minion_id=None):
    """
    Reads in the pillar glob match
    """
    if not opts:
        opts = __opts__
    log.debug("pillar target: %s", tgt)
    if delimiter not in tgt:
        log.error("Got insufficient arguments for pillar match statement from master")
        return False

    if opts.get("pillar"):
        pillar = opts["pillar"]
    elif "__pillar__" in globals():
        pillar = __pillar__
        if hasattr(pillar, "value"):
            pillar = pillar.value()
    elif opts.get("ext_pillar"):
        pillar = opts["ext_pillar"]
    else:
        pillar = {}

    return salt.utils.data.subdict_match(pillar, tgt, delimiter=delimiter)
