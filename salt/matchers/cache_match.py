# -*- coding: utf-8 -*-
'''
This is the default cache matcher function.  It only exists for the master,
this is why there is only a ``mmatch()`` but not ``match()``.
'''
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
from salt.defaults import DEFAULT_TARGET_DELIM  # pylint: disable=3rd-party-module-not-gated

import salt.utils.data  # pylint: disable=3rd-party-module-not-gated
import salt.utils.minions

log = logging.getLogger(__name__)


def mmatch(expr,
           delimiter,
           greedy,
           search_type,
           regex_match=False,
           exact_match=False):
    '''
    Helper function to search for minions in master caches
    If 'greedy' return accepted minions that matched by the condition or absent in the cache.
    If not 'greedy' return the only minions have cache data and matched by the condition.
    '''
    ckminions = salt.utils.minions.CkMinions

    return ckminions._check_cache_minions(expr, delimiter, greedy,
                                          search_type, regex_match=regex_match,
                                          exact_match=exact_match)
