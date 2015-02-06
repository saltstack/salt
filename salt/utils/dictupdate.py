# -*- coding: utf-8 -*-
'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''

# Import python libs
from __future__ import absolute_import
import collections

# Import 3rd-party libs
import salt.ext.six as six


def update(dest, upd):
    for key, val in six.iteritems(upd):
        if isinstance(val, collections.Mapping):
            ret = update(dest.get(key, {}), val)
            dest[key] = ret
        else:
            dest[key] = upd[key]
    return dest


def merge(d1, d2):
    md = {}
    for key, val in six.iteritems(d1):
        if key in d2:
            md[key] = [val, d2[key]]
        else:
            md[key] = val
    return md
