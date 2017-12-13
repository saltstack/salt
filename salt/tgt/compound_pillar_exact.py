# -*- coding: utf-8 -*-
'''
Return the minions found by looking via compound matcher
Disable pillar glob matching
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt


log = logging.getLogger(__name__)


def check_minions(expr, delimiter, greedy):
    '''
    Return the minions found by looking via compound matcher
    Disable pillar glob matching
    '''
    return salt.tgt.check_compound_minions(__opts__, expr, delimiter, greedy, pillar_exact=True)
