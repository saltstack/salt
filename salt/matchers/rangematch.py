# -*- coding: utf-8 -*-
'''
This is the default range matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging

HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    pass

log = logging.getLogger(__name__)


def range_match(self, tgt):
    '''
    Matches based on range cluster
    '''
    if HAS_RANGE:
        range_ = seco.range.Range(self.opts['range_server'])
        try:
            return self.opts['grains']['fqdn'] in range_.expand(tgt)
        except seco.range.RangeException as exc:
            log.debug('Range exception in compound match: %s', exc)
            return False
    return False
