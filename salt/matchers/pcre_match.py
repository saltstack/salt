# -*- coding: utf-8 -*-
'''
This is the default pcre matcher.
'''
from __future__ import absolute_import, print_function, unicode_literals

import re


def match(tgt):
    '''
    Returns true if the passed pcre regex matches
    '''
    return bool(re.match(tgt, __opts__['id']))
