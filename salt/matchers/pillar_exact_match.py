"""
This is the default pillar exact matcher.
"""

import logging

import salt.utils.data

log = logging.getLogger(__name__)


def match(tgt, delimiter=":", opts=None, minion_id=None):
    """
    Reads in the pillar match, no globbing, no PCRE
    """
    if not opts:
        opts = __opts__
    log.debug("pillar target: %s", tgt)
    if delimiter not in tgt:
        log.error("Got insufficient arguments for pillar match statement from master")
        return False

    if "pillar" in opts:
        pillar = opts["pillar"]
    elif "ext_pillar" in opts:
        log.info("No pillar found, fallback to ext_pillar")
        pillar = opts["ext_pillar"]

    return salt.utils.data.subdict_match(
        pillar, tgt, delimiter=delimiter, exact_match=True
    )
