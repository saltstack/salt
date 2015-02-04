# -*- coding: utf-8 -*-
import logging
import collections

log = logging.getLogger(__name__)


class LazyDict(collections.MutableMapping):
    '''
    A base class of dict which will lazily load keys once they are needed

    TODO: negative caching? If you ask for 'foo' and it doesn't exist it will
    look EVERY time unless someone calls load_all()
    As of now this is left to the class which inherits from this base
    '''
    def __init__(self):
        self.clear()

    def clear(self):
        '''
        Clear the dict
        '''
        # create a dict to store loaded values in
        self._dict = {}

        # have we already loded everything?
        self.loaded = False

    def _load(self, key):
        '''
        Load a single item if you have it
        '''
        raise NotImplementedError()

    def _load_all(self):
        '''
        Load all of them
        '''
        raise NotImplementedError()

    def _missing(self, key):
        '''
        Wheter or not the key is missing (meaning we know its not there)
        '''
        return False

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __delitem__(self, key):
        del self._dict[key]

    def __getitem__(self, key):
        '''
        Check if the key is ttld out, then do the get
        '''
        if self._missing(key):
            raise KeyError(key)

        if key not in self._dict and not self.loaded:
            # load the item
            if self._load(key):
                log.debug('LazyLoaded {0}'.format(key))
                return self._dict[key]
            else:
                log.debug('Could not LazyLoad {0}'.format(key))
                raise KeyError(key)
        else:
            return self._dict[key]

    def __len__(self):
        # if not loaded,
        if not self.loaded:
            self._load_all()
        return len(self._dict)

    def __iter__(self):
        if not self.loaded:
            self._load_all()
        return iter(self._dict)
