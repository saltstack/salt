# -*- coding: utf-8 -*-p
'''
Return the minions found by looking via a lits
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt
from salt.ext import six


log = logging.getLogger(__name__)


def check_minions(expr):
    '''
    Return the minions found by looking via a list
    '''
    pki_minions = salt.tgt.pki_minions(__opts__)
    if isinstance(expr, six.string_types):
        expr = [m.strip() for m in expr.split(',') if m.strip()]
    return {'minions': [x for x in expr if x in pki_minions],
            'missing': [x for x in expr if x not in pki_minions]}
