# -*- coding: utf-8 -*-
'''
Functions for manipulating, inspecting, or otherwise working with data types
and data structures.
'''

from __future__ import absolute_import, print_function, unicode_literals

try:
    from collections.abc import Mapping, MutableMapping, Sequence
except ImportError:
    from collections import Mapping, MutableMapping, Sequence

# Import Salt libs
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
from salt.ext import six


class CaseInsensitiveDict(MutableMapping):
    '''
    Inspired by requests' case-insensitive dict implementation, but works with
    non-string keys as well.
    '''
    def __init__(self, init=None):
        '''
        Force internal dict to be ordered to ensure a consistent iteration
        order, irrespective of case.
        '''
        self._data = OrderedDict()
        self.update(init or {})

    def __len__(self):
        return len(self._data)

    def __setitem__(self, key, value):
        # Store the case-sensitive key so it is available for dict iteration
        self._data[to_lowercase(key)] = (key, value)

    def __delitem__(self, key):
        del self._data[to_lowercase(key)]

    def __getitem__(self, key):
        return self._data[to_lowercase(key)][1]

    def __iter__(self):
        return (item[0] for item in six.itervalues(self._data))

    def __eq__(self, rval):
        if not isinstance(rval, Mapping):
            # Comparing to non-mapping type (e.g. int) is always False
            return False
        return dict(self.items_lower()) == dict(CaseInsensitiveDict(rval).items_lower())

    def __repr__(self):
        return repr(dict(six.iteritems(self)))

    def items_lower(self):
        '''
        Returns a generator iterating over keys and values, with the keys all
        being lowercase.
        '''
        return ((key, val[1]) for key, val in six.iteritems(self._data))

    def copy(self):
        '''
        Returns a copy of the object
        '''
        return CaseInsensitiveDict(six.iteritems(self._data))


def __change_case(data, attr, preserve_dict_class=False):
    try:
        return getattr(data, attr)()
    except AttributeError:
        pass

    data_type = data.__class__

    if isinstance(data, Mapping):
        return (data_type if preserve_dict_class else dict)(
            (__change_case(key, attr, preserve_dict_class),
             __change_case(val, attr, preserve_dict_class))
            for key, val in six.iteritems(data)
        )
    elif isinstance(data, Sequence):
        return data_type(
            __change_case(item, attr, preserve_dict_class) for item in data)
    else:
        return data


def to_lowercase(data, preserve_dict_class=False):
    return __change_case(data, 'lower', preserve_dict_class)


def to_uppercase(data, preserve_dict_class=False):
    return __change_case(data, 'upper', preserve_dict_class)
