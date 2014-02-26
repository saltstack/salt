# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.datafreeze
    ~~~~~~~~~~~~~~~~~~~~~

    Built-in data types freeze
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

    def __repr__(self):
        return repr(self.__obj)

    def __getitem__(self, key):
        return self.__obj[key]


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

    def __repr__(self):
        return repr(self.__obj)

    def __getitem__(self, key):
        return self.__obj[key]


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

    def __repr__(self):
        return repr(self.__obj)

    def __contains__(self, key):
        return key in self.__obj


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
