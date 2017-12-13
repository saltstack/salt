# -*- coding: utf-8 -*-
'''
Return the minions found by looking via grains
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt


log = logging.getLogger(__name__)


def check_minions(expr, delimiter, greedy):
    '''
    Return the minions found by looking via grains
    '''
    return salt.tgt.check_cache_minions(expr, delimiter, greedy, 'grains', __opts__)
