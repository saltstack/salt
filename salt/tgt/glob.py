# -*- coding: utf-8 -*-
'''
Return the minions found by looking via globs
'''

# Import python libs
from __future__ import absolute_import
import fnmatch
import logging

# Import salt libs
import salt.tgt


log = logging.getLogger(__name__)


def check_minions(expr):
    '''
    Return the minions found by looking via globs
    '''
    pki_minions = salt.tgt.pki_minions(__opts__)
    return {'minions': fnmatch.filter(pki_minions, expr), 'missing': []}
