"""
This is the default data matcher.
"""

import fnmatch
import logging

import salt.loader
import salt.utils.data
import salt.utils.minions
import salt.utils.network

log = logging.getLogger(__name__)


def match(tgt, functions=None, opts=None, minion_id=None):
    """
    Match based on the local data store on the minion
    """
    if not opts:
        opts = __opts__
    if functions is None:
        utils = salt.loader.utils(opts)
        functions = salt.loader.minion_mods(opts, utils=utils)
    comps = tgt.split(":")
    if len(comps) < 2:
        return False
    val = functions["data.getval"](comps[0])
    if val is None:
        # The value is not defined
        return False
    if isinstance(val, list):
        # We are matching a single component to a single list member
        for member in val:
            if fnmatch.fnmatch(str(member).lower(), comps[1].lower()):
                return True
        return False
    if isinstance(val, dict):
        if comps[1] in val:
            return True
        return False
    return bool(fnmatch.fnmatch(val, comps[1]))
