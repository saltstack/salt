# -*- coding: utf-8 -*-
'''
Return minions found by looking at nodegroups
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt
from salt.defaults import DEFAULT_TARGET_DELIM


log = logging.getLogger(__name__)


def check_minions(expr, greedy):
    '''
    Return minions found by looking at nodegroups
    '''
    return salt.tgt.check_compound_minions(__opts__,
                                           salt.tgt.nodegroup_comp(expr, __opts__['nodegroups']),
                                           DEFAULT_TARGET_DELIM,
                                           greedy)
