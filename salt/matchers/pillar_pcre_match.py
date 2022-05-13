"""
This is the default pillar PCRE matcher.
"""

import logging

import salt.utils.data
from salt.defaults import DEFAULT_TARGET_DELIM

log = logging.getLogger(__name__)


def match(tgt, delimiter=DEFAULT_TARGET_DELIM, opts=None, minion_id=None):
    """
    Reads in the pillar pcre match
    """
    if not opts:
        opts = __opts__
    log.debug("pillar PCRE target: %s", tgt)
    if delimiter not in tgt:
        log.error(
            "Got insufficient arguments for pillar PCRE match statement from master"
        )
        return False

    if "pillar" in opts:
        pillar = opts["pillar"]
    elif "ext_pillar" in opts:
        log.info("No pillar found, fallback to ext_pillar")
        pillar = opts["ext_pillar"]

    return salt.utils.data.subdict_match(
        pillar, tgt, delimiter=delimiter, regex_match=True
    )
