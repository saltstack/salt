# -*- coding: utf-8 -*-
'''
This is the default list matcher.
'''
from __future__ import absolute_import, print_function, unicode_literals


def match(tgt):
    '''
    Determines if this host is on the list
    '''
    try:
        return __opts__['id'] == tgt \
            or ',' + __opts__['id'] + ',' in tgt \
            or tgt.startswith(__opts__['id'] + ',') \
            or tgt.endswith(',' + __opts__['id'])
    except (AttributeError, TypeError):
        return False
