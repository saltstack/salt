# -*- coding: utf-8 -*-
'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''

# Import python libs
import collections


def update(dest, upd):
    for key, val in upd.iteritems():
        if isinstance(val, collections.Mapping):
            ret = update(dest.get(key, {}), val)
            dest[key] = ret
        elif key:
            dest[key] = upd[key]
    return dest


def merge(d1, d2):
    md = {}
    for k, v in d1.iteritems():
        if k in d2:
            md[k] = [v, d2[k]]
        else:
            md[k] = v
    return md
