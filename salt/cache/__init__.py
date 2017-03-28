# -*- coding: utf-8 -*-
'''
Loader mechanism for caching data, with data expiration, etc.

.. versionadded:: 2016.11.0
'''

# Import Python libs
from __future__ import absolute_import
import logging
import time

# Import Salt lobs
from salt.ext import six
from salt.payload import Serial
from salt.utils.odict import OrderedDict
import salt.loader
import salt.syspaths

log = logging.getLogger(__name__)


def factory(opts, **kwargs):
    '''
    Creates and returns the cache class.
    If memory caching is enabled by opts MemCache class will be instantiated.
    If not Cache class will be returned.
    '''
    if opts.get('memcache_expire_seconds', 0):
        cls = MemCache
    else:
        cls = Cache
    return cls(opts, **kwargs)


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
    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.driver = opts['cache']
        self.serial = Serial(opts)
        self._modules = None
        self._kwargs = kwargs

    def __lazy_init(self):
        self._modules = salt.loader.cache(self.opts, self.serial)
        fun = '{0}.init_kwargs'.format(self.driver)
        if fun in self.modules:
            self._kwargs = self.modules[fun](self._kwargs)
        else:
            self._kwargs = {}

    @property
    def modules(self):
        if self._modules is None:
            self.__lazy_init()
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
        fun = '{0}.store'.format(self.driver)
        return self.modules[fun](bank, key, data, **self._kwargs)

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
        fun = '{0}.fetch'.format(self.driver)
        return self.modules[fun](bank, key, **self._kwargs)

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
        fun = '{0}.updated'.format(self.driver)
        return self.modules[fun](bank, key, **self._kwargs)

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
        fun = '{0}.flush'.format(self.driver)
        return self.modules[fun](bank, key=key, **self._kwargs)

    def ls(self, bank):
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
        fun = '{0}.ls'.format(self.driver)
        return self.modules[fun](bank, **self._kwargs)

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
        fun = '{0}.contains'.format(self.driver)
        return self.modules[fun](bank, key, **self._kwargs)


class MemCache(Cache):
    '''
    Short-lived in-memory cache store keeping values on time and/or size (count)
    basis.
    '''
    # {<storage_id>: odict({<key>: [atime, data], ...}), ...}
    data = {}

    def __init__(self, opts, **kwargs):
        super(MemCache, self).__init__(opts, **kwargs)
        self.expire = opts.get('memcache_expire_seconds', 10)
        self.max = opts.get('memcache_max_items', 1024)
        self.cleanup = opts.get('memcache_full_cleanup', False)
        self.debug = opts.get('memcache_debug', False)
        if self.debug:
            self.call = 0
            self.hit = 0
        self._storage = None

    @classmethod
    def __cleanup(cls, expire):
        now = time.time()
        for storage in six.itervalues(cls.data):
            for key, data in list(storage.items()):
                if data[0] + expire < now:
                    del storage[key]

    def _get_storage_id(self):
        fun = '{0}.storage_id'.format(self.driver)
        if fun in self.modules:
            return self.modules[fun](self.kwargs)
        else:
            return self.driver

    @property
    def storage(self):
        if self._storage is None:
            storage_id = self._get_storage_id()
            if storage_id not in MemCache.data:
                MemCache.data[storage_id] = OrderedDict()
            self._storage = MemCache.data[storage_id]
        return self._storage

    def fetch(self, bank, key):
        if self.debug:
            self.call += 1
        now = time.time()
        record = self.storage.pop((bank, key), None)
        # Have a cached value for the key
        if record is not None and record[0] + self.expire >= now:
            if self.debug:
                self.hit += 1
                log.trace('MemCache stats (call/hit/rate): '
                          '{0}/{1}/{2}'.format(self.call,
                                               self.hit,
                                               float(self.hit) / self.call))
            # update atime and return
            record[0] = now
            self.storage[(bank, key)] = record
            return record[1]

        # Have no value for the key or value is expired
        data = super(MemCache, self).fetch(bank, key)
        self.storage[(bank, key)] = [now, data]
        return data

    def store(self, bank, key, data):
        self.storage.pop((bank, key), None)
        super(MemCache, self).store(bank, key, data)
        if len(self.storage) >= self.max:
            if self.cleanup:
                MemCache.__cleanup(self.expire)
            else:
                self.storage.popitem(last=False)
        self.storage[(bank, key)] = [time.time(), data]

    def flush(self, bank, key=None):
        self.storage.pop((bank, key), None)
        super(MemCache, self).flush(bank, key)
