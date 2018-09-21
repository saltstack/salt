# -*- coding: utf-8 -*-
'''
This is the default list matcher.
'''
from __future__ import absolute_import, print_function, unicode_literals
import collections
import salt.ext.six as six  # pylint: disable=3rd-party-module-not-gated


def match(tgt):
    '''
    Determines if this host is on the list
    '''
    try:
        if isinstance(tgt, collections.Sequence) and not isinstance(tgt, six.string_types):
            result = bool(__opts__['id'] in tgt)
        else:
            result = __opts__['id'] == tgt \
                or ',' + __opts__['id'] + ',' in tgt \
                or tgt.startswith(__opts__['id'] + ',') \
                or tgt.endswith(',' + __opts__['id'])
        return result

    except (AttributeError, TypeError):
        return False
