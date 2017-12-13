# -*- coding: utf-8 -*-
'''
Return the minions found by looking via regular expressions
'''

# Import python libs
from __future__ import absolute_import
import logging
import re

# Import salt libs
import salt.tgt

log = logging.getLogger(__name__)


def check_minions(expr):
    '''
    Return the minions found by looking via regular expressions
    '''
    pki_minions = salt.tgt.pki_minions(__opts__)
    reg = re.compile(expr)
    return {'minions': [m for m in pki_minions if reg.match(m)],
            'missing': []}
