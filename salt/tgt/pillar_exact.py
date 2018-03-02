# -*- coding: utf-8 -*-
'''
Return the minions found by looking via pillar
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt


log = logging.getLogger(__name__)


def check_minions(expr, delimiter, greedy):
    '''
    Return the minions found by looking via pillar
    '''
    return salt.tgt.check_cache_minions(__opts__, expr, delimiter, greedy, 'pillar', exact_match=True)
