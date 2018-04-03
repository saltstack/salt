# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.utils.immutabletypes
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Immutable types
'''
from __future__ import absolute_import, unicode_literals

# Import python libs
import collections


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
        return freeze(self.__obj[key])

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

    def __add__(self, other):
        return self.__obj + other

    def __radd__(self, other):
        return other + self.__obj

    def __getitem__(self, key):
        return freeze(self.__obj[key])

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


def freeze(obj):
    '''
    Freeze python types by turning them into immutable structures.
    '''
    if isinstance(obj, dict):
        return ImmutableDict(obj)
    if isinstance(obj, list):
        return ImmutableList(obj)
    if isinstance(obj, set):
        return ImmutableSet(obj)
    return obj
