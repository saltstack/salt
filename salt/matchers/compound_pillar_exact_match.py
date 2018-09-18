# -*- coding: utf-8 -*-
'''
This is the default pillar exact matcher for compound matches.

There is no minion-side equivalent for this, so consequently there is no ``match()``
function below, only an ``mmatch()``
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging

import salt.utils.minions

log = logging.getLogger(__name__)


def mmatch(expr, delimiter, greedy):
    '''
    Return the minions found by looking via pillar
    '''
    ckminions = salt.utils.minions.CkMinions()
    return ckminions._check_compound_minions(expr, delimiter, greedy,
                                             exact_match=True)
