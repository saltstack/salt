# -*- coding: utf-8 -*-
"""
This is the default data matcher.
"""
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import logging

import salt.loader  # pylint: disable=3rd-party-module-not-gated
import salt.utils.data  # pylint: disable=3rd-party-module-not-gated
import salt.utils.minions  # pylint: disable=3rd-party-module-not-gated
import salt.utils.network  # pylint: disable=3rd-party-module-not-gated
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def match(tgt, functions=None, opts=None):
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
            if fnmatch.fnmatch(six.text_type(member).lower(), comps[1].lower()):
                return True
        return False
    if isinstance(val, dict):
        if comps[1] in val:
            return True
        return False
    return bool(fnmatch.fnmatch(val, comps[1],))
