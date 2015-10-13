# -*- coding: utf-8 -*-
from __future__ import absolute_import
from collections import MutableMapping
from threading import currentThread, RLock


class DictThread(MutableMapping):
    '''
    Transparent dictionary providing different copies of data depending on the
    current thread name.
    '''
    def __init__(self, *args, **kwargs):
        '''
        Constructor
        '''
        self.__lock = RLock()
        with self.__lock:
            if len(args) == 1 and isinstance(args[0], DictThread):
                self._tmap = args[0]._tmap
                self.update(dict(**kwargs))
            elif len(args) == 1 and isinstance(args[0], bool):
                self._tmap = dict()
            else:
                self._tmap = dict()
                self.update(dict(*args, **kwargs))
            self.__init_current__()

    def __init_current__(self):
        '''
        Add new empty dict for current thread
        '''
        tkey = self.__tkey__()
        if tkey not in self._tmap:
            # There is no mapping for current thread yet
            with self.__lock:
                # Don't need to re-check here because each thread manage it's
                # own key only
                self._tmap[tkey] = dict()

    def __tkey__(self):
        '''
        Return current thread unique ID for mapping
        '''
        return currentThread().name

    def __getitem__(self, key):
        return self._tmap[self.__tkey__()][key]

    def __setitem__(self, key, value):
        self.__init_current__()
        self._tmap[self.__tkey__()][key] = value

    def __delitem__(self, key):
        del self._tmap[self.__tkey__()][key]

    def __iter__(self):
        return iter(self._tmap[self.__tkey__()])

    def __len__(self):
        return len(self._tmap[self.__tkey__()])

    def __nonzero__(self):
        tkey = self.__tkey__()
        return tkey in self._tmap and bool(self._tmap[self.__tkey__()])

    def __str__(self):
        return str(self._tmap)

    def assign_current(self, dictionary):
        '''
        Assign dictionary for current thread
        '''
        with self.__lock:
            tkey = self.__tkey__()
            if isinstance(dictionary, DictThread):
                self._tmap[tkey] = dictionary.get_current(tkey) or dict()
            else:
                self._tmap[tkey] = dictionary

    def get_current(self, default=None):
        '''
        Get dictionary for current thread
        '''
        return self._tmap.get(self.__tkey__(), default=default)
