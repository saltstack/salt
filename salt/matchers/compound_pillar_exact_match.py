# -*- coding: utf-8 -*-
'''
This is the default pillar exact matcher for compound matches.

There is no minion-side equivalent for this, so consequently there is no ``match()``
function below, only an ``mmatch()``

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated
from salt.defaults import DEFAULT_TARGET_DELIM  # pylint: disable=3rd-party-module-not-gated
import salt.utils.data  # pylint: disable=3rd-party-module-not-gated

log = logging.getLogger(__name__)


def mmatch(self, expr, delimiter, greedy):
    '''
    Return the minions found by looking via pillar
    '''
    return self._check_compound_minions(expr,
                                        delimiter,
                                        greedy,
                                        exact_match=True)
