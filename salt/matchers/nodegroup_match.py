"""
This is the default nodegroup matcher.
"""

import logging

import salt.loader
import salt.utils.minions

log = logging.getLogger(__name__)


def match(tgt, nodegroups=None, opts=None, minion_id=None):
    """
    This is a compatibility matcher and is NOT called when using
    nodegroups for remote execution, but is called when the nodegroups
    matcher is used in states
    """
    if not opts:
        opts = __opts__
    if not nodegroups:
        log.debug("Nodegroup matcher called with no nodegroups.")
        return False
    if tgt in nodegroups:
        matchers = salt.loader.matchers(opts)
        return matchers["compound_match.match"](
            salt.utils.minions.nodegroup_comp(tgt, nodegroups)
        )
    return False
