# -*- coding: utf-8 -*-
'''
This is the default data matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
import logging
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated

import salt.utils.data  # pylint: disable=3rd-party-module-not-gated
import salt.utils.minions  # pylint: disable=3rd-party-module-not-gated
import salt.utils.network  # pylint: disable=3rd-party-module-not-gated
import salt.loader  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def match(self, tgt):
    '''
    Match based on the local data store on the minion
    '''
    if self.functions is None:
        utils = salt.loader.utils(self.opts)
        self.functions = salt.loader.minion_mods(self.opts, utils=utils)
    comps = tgt.split(':')
    if len(comps) < 2:
        return False
    val = self.functions['data.getval'](comps[0])
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
    return bool(fnmatch.fnmatch(
        val,
        comps[1],
    ))
