# -*- coding: utf-8 -*-
from __future__ import absolute_import
from collections import MutableMapping
import threading


class DictThread(MutableMapping):
    '''
    Transparent dictionary providing different copies of data depending on the
    current thread name.
    '''
    local = threading.local()

    @classmethod
    def wrap(cls, obj, name):
        '''
        Wraps dict with DictThread object.
        '''
        if isinstance(obj, cls):
            return obj
        else:
            return cls(obj, name)

    def __init__(self, data, name):
        '''
        Constructor
        '''
        self.name = name
        self.update(data)

    def _dict(self):
        '''
        Return current thread unique ID for mapping
        '''
        local = DictThread.local
        if not hasattr(local, 'data'):
            local.data = {}
        data = local.data
        if self.name not in data:
            data[self.name] = {}
        return data[self.name]

    def __getitem__(self, key):
        return self._dict()[key]

    def __setitem__(self, key, value):
        self._dict()[key] = value

    def __delitem__(self, key):
        del self._dict()[key]

    def __iter__(self):
        return iter(self._dict())

    def __len__(self):
        return len(self._dict())

    def __nonzero__(self):
        return self._dict().__nonzero__()

    def __str__(self):
        return str(self._dict())
