# -*- coding: utf-8 -*-
'''
Return the minions found by looking via pillar with PCRE
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt


log = logging.getLogger(__name__)


def check_minions(expr, delimiter, greedy):
    '''
    Return the minions found by looking via pillar with PCRE
    '''
    return salt.tgt.check_cache_minions(expr, delimiter, greedy, 'pillar', __opts__, regex_match=True)
