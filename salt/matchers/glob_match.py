# -*- coding: utf-8 -*-
'''
This is the default glob matcher function.
'''
from __future__ import absolute_import, print_function, unicode_literals

import fnmatch
from salt.ext import six  # pylint: disable=3rd-party-module-not-gated


def match(tgt):
    '''
    Returns true if the passed glob matches the id
    '''
    minion_id = __opts__.get('minion_id', __opts__['id'])
    if not isinstance(tgt, six.string_types):
        return False

    return fnmatch.fnmatch(minion_id, tgt)
