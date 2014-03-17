# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.immutabletypes
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Immutable types
'''

# Import python libs
import collections

# Import salt libs
from salt.utils.lazyproxy import LazyLoadProxy


class ImmutableDict(collections.Mapping):
    '''
    An immutable dictionary implementation
    '''

    def __init__(self, obj):
        self.__obj = obj

    def __len__(self):
        return len(self.__obj)

    def __iter__(self):
        return iter(self.__obj)

    def __getitem__(self, key):
        return ImmutableLazyProxy(self.__obj[key])

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, repr(self.__obj))


class ImmutableList(collections.Sequence):
    '''
    An immutable list implementation
    '''

    def __init__(self, obj):
        self.__obj = obj

    def __len__(self):
        return len(self.__obj)

    def __iter__(self):
        return iter(self.__obj)

    def _get_raw(self, other):
        if isinstance(other, ImmutableLazyProxy):
            other = other.__obj
        return other

    def __add__(self, other):
        return self.__obj + self._get_raw(other)

    def __radd__(self, other):
        return self._get_raw(other) + self.__obj

    def __getitem__(self, key):
        return ImmutableLazyProxy(self.__obj[key])

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, repr(self.__obj))


class ImmutableSet(collections.Set):
    '''
    An immutable set implementation
    '''

    def __init__(self, obj):
        self.__obj = obj

    def __len__(self):
        return len(self.__obj)

    def __iter__(self):
        return iter(self.__obj)

    def __contains__(self, key):
        return key in self.__obj

    def __repr__(self):
        return '<{0} {1}>'.format(self.__class__.__name__, repr(self.__obj))


class ImmutableLazyProxy(LazyLoadProxy):
    '''
    LazyProxy which will return an immutable type when requested
    '''

    def __init__(self, obj):
        def __immutable_selection(obj):
            if isinstance(obj, dict):
                return ImmutableDict(obj)
            if isinstance(obj, list):
                return ImmutableList(obj)
            if isinstance(obj, set):
                return ImmutableSet(obj)
            return obj

        super(ImmutableLazyProxy, self).__init__(
            lambda: __immutable_selection(obj)
        )
