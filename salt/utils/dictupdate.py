# -*- coding: utf-8 -*-
'''
Alex Martelli's soulution for recursive dict update from
http://stackoverflow.com/a/3233356
'''
from __future__ import absolute_import

# Import python libs
import collections
import six

# Import salt libs
from salt.utils.odict import OrderedDict


def update(dest, upd):
    for key, val in six.iteritems(upd):
        if isinstance(val, collections.Mapping):
            ret = update(dest.get(key, OrderedDict()), val)
            dest[key] = ret
        else:
            dest[key] = upd[key]
    return dest
