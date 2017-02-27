# -*- coding: utf-8 -*-
'''
Loader mechanism for caching data, with data expiration, etc.

.. versionadded:: 2016.11.0
'''

# Import Python libs
from __future__ import absolute_import
import time

# Import Salt lobs
import salt.loader
import salt.syspaths
from salt.payload import Serial


class Cache(object):
    '''
    Base caching object providing access to the modular cache subsystem.

    Related configuration options:

    :param cache:
        The name of the cache driver to use. This is the name of the python
        module of the `salt.cache` package. Default is `localfs`.

    :param serial:
        The module of `salt.serializers` package that should be used by the cache
        driver to store data.
        If a driver can't use a specific module or uses specific objects storage
        it can ignore this parameter.

    Terminology.

    Salt cache subsystem is organized as a tree with nodes and leafs like a
    filesystem. Cache consists of banks. Each bank can contain a number of
    keys. Each key can contain a dict or any other object serializable with
    `salt.payload.Serial`. I.e. any data object in the cache can be
    addressed by the path to the bank and the key name:
        bank: 'minions/alpha'
        key:  'data'

    Bank names should be formatted in a way that can be used as a
    directory structure. If slashes are included in the name, then they
    refer to a nested structure.

    Key name is a string identifier of a data container (like a file inside a
    directory) which will hold the data.
    '''
    def __init__(self, opts, cachedir=None):
        self.opts = opts
        if cachedir is None:
            self.cachedir = opts.get('cachedir', salt.syspaths.CACHE_DIR)
        else:
            self.cachedir = cachedir
        self.driver = opts['cache']
        self.serial = Serial(opts)
        self._modules = None

    @property
    def modules(self):
        if self._modules is None:
            self._modules = salt.loader.cache(self.opts, self.serial)
        return self._modules

    def cache(self, bank, key, fun, loop_fun=None, **kwargs):
        '''
        Check cache for the data. If it is there, check to see if it needs to
        be refreshed.

        If the data is not there, or it needs to be refreshed, then call the
        callback function (``fun``) with any given ``**kwargs``.

        In some cases, the callback function returns a list of objects which
        need to be processed by a second function. If that is the case, then
        the second function is passed in as ``loop_fun``. Each item in the
        return list from the first function will be the only argument for the
        second function.
        '''
        expire_seconds = kwargs.get('expire', 86400)  # 1 day

        updated = self.updated(bank, key)
        update_cache = False
        if updated is None:
            update_cache = True
        else:
            if int(time.time()) - updated > expire_seconds:
                update_cache = True

        data = self.fetch(bank, key)

        if not data or update_cache is True:
            if loop_fun is not None:
                data = []
                items = fun(**kwargs)
                for item in items:
                    data.append(loop_fun(item))
            else:
                data = fun(**kwargs)
            self.store(bank, key, data)

        return data

    def store(self, bank, key, data):
        '''
        Store data using the specified module

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :param data:
            The data which will be stored in the cache. This data should be
            in a format which can be serialized by msgpack/json/yaml/etc.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'store')
        try:
            return self.modules[fun](bank, key, data, self.cachedir)
        except TypeError:
            return self.modules[fun](bank, key, data)

    def fetch(self, bank, key):
        '''
        Fetch data using the specified module

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Return a python object fetched from the cache or an empty dict if
            the given path or key not found.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'fetch')
        try:
            return self.modules[fun](bank, key, self.cachedir)
        except TypeError:
            return self.modules[fun](bank, key)

    def updated(self, bank, key):
        '''
        Get the last updated epoch for the specified key

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Return an int epoch time in seconds or None if the object wasn't
            found in cache.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'updated')
        try:
            return self.modules[fun](bank, key, self.cachedir)
        except TypeError:
            return self.modules[fun](bank, key)

    def flush(self, bank, key=None):
        '''
        Remove the key from the cache bank with all the key content. If no key is specified remove
        the entire bank with all keys and sub-banks inside.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'flush')
        try:
            return self.modules[fun](bank, key=key, cachedir=self.cachedir)
        except TypeError:
            return self.modules[fun](bank, key=key)

    def list(self, bank):
        '''
        Lists entries stored in the specified bank.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :return:
            An iterable object containing all bank entries. Returns an empty
            iterator if the bank doesn't exists.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'list')
        try:
            return self.modules[fun](bank, self.cachedir)
        except TypeError:
            return self.modules[fun](bank)

    def contains(self, bank, key=None):
        '''
        Checks if the specified bank contains the specified key.

        :param bank:
            The name of the location inside the cache which will hold the key
            and its associated data.

        :param key:
            The name of the key (or file inside a directory) which will hold
            the data. File extensions should not be provided, as they will be
            added by the driver itself.

        :return:
            Returns True if the specified key exists in the given bank and False
            if not.
            If key is None checks for the bank existense.

        :raises SaltCacheError:
            Raises an exception if cache driver detected an error accessing data
            in the cache backend (auth, permissions, etc).
        '''
        fun = '{0}.{1}'.format(self.driver, 'contains')
        try:
            return self.modules[fun](bank, key, self.cachedir)
        except TypeError:
            return self.modules[fun](bank, key)
