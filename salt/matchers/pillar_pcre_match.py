# -*- coding: utf-8 -*-
'''
This is the default pillar PCRE matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated
from salt.defaults import DEFAULT_TARGET_DELIM  # pylint: disable=3rd-party-module-not-gated
import salt.utils.data  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def match(self, tgt, delimiter=DEFAULT_TARGET_DELIM):
    '''
    Reads in the pillar pcre match
    '''
    log.debug('pillar PCRE target: %s', tgt)
    if delimiter not in tgt:
        log.error('Got insufficient arguments for pillar PCRE match '
                  'statement from master')
        return False
    return salt.utils.data.subdict_match(
        self.opts['pillar'], tgt, delimiter=delimiter, regex_match=True
    )
