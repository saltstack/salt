# -*- coding: utf-8 -*-
'''
This is the default pcre matcher.

NOTE: These functions are converted to methods on the Matcher class during master and minion startup.
This is why they all take `self` but are not defined inside a `class:` declaration.
'''
from __future__ import absolute_import, print_function, unicode_literals

import re


def match(self, tgt):
    '''
    Returns true if the passed pcre regex matches
    '''
    return bool(re.match(tgt, self.opts['id']))
