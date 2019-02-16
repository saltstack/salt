# -*- coding: utf-8 -*-
'''
If-Modified-Since caching.
'''
from __future__ import absolute_import
import copy
import logging
import sys
import time
import traceback


import cachetools


import salt.cache
from salt.ext import six


log = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        else:
            log.error("Not using factoried instance of Cache\n %s",
                     "".join(traceback.format_stack()))
        return cls._instances[cls]


DEFAULT_POLICY = {'cache_type': "Cache", 'maxsize': 10}


def cache_from_opts(opts):
    worker_cache_name = opts.get('worker_cache', None)
    if not worker_cache_name:
        return None

    _opts = copy.deepcopy(opts)

    cache_types = {
        'Cache': cachetools.Cache
    }

    policy = _opts.get('worker_cache_policy', copy.copy(DEFAULT_POLICY))
    cache_type_name = policy.pop('cache_type', "Cache")
    cache = cache_types.get(cache_type_name, cachetools.Cache)(**policy)

    if worker_cache_name == 'IMSCache':
        return IMSCache(cache=cache)
    elif worker_cache_name == 'TieredIMSCache':
        tiered_cache_driver = opts.get('worker_cache_tiered', None)
        if tiered_cache_driver:
            _opts['cache'] = tiered_cache_driver
        shared_cache = salt.cache.Cache(_opts)
        shared = PluggableCache(cache=shared_cache)
        cache = IMSCache(cache=cache)
        return TieredIMSCache(cache=cache, shared=shared)
    elif worker_cache_name == 'PluggableCache':
        cache = salt.cache.Cache(_opts)
        return PluggableCache(cache=cache)
    else:
        raise Exception(("Worker cache must be one of (IMSCache, TieredIMSCache)"
                         "Got {}").format(worker_cache_name))


class CacheItem(object):
    def __init__(self, mtime, atime, ttl, data, extra):
        self.mtime = mtime
        self.atime = atime
        self.ttl = ttl
        self.data = data
        self.extra = extra

    @classmethod
    def make(cls, mtime=0, atime=0, ttl=0, data=None, extra=None):
        extra = extra or {}
        return cls(mtime, atime, ttl, data, extra)


class IMSCache(six.with_metaclass(Singleton, object)):
    """In-memory cache supporting IMS."""
    def __init__(self, cache):
        self._cache = cache

    def cache(self, bank, key, fun, **kwargs):
        refresh = False

        now = int(time.time())

        # Get existing, possibly expired, key or make a new onw
        ci = self.fetch_item(bank, key)
        if not ci:
            ci = CacheItem.make()

        # Allow overriding ttl, i.e. to force
        ttl = kwargs.get('expire', ci.ttl)
        if now - ci.mtime > ttl:
            refresh = True

        if ci.data is None or refresh:
            try:
                data = fun(item=ci, **kwargs)
            except Exception as e:
                trace = traceback.format_exc(sys.exc_info())
                log.error("An error occured in cache load function %s\n%s", e,
                          "".join(trace))
                # TODO: configure serve on stale or fail or return None
                return ci.data

            if data is None:
                self.flush(bank, key=key)
                return None

            self.store(bank, key, data, ttl=ttl)

            if isinstance(data, CacheItem):
                return data.data
            else:
                return data
        else:
            return ci.data

    def store_item(self, bank, key, item):
        self._cache[(bank, key)] = item

    def store(self, bank, key, data, ttl=86400):

        if not isinstance(data, CacheItem):
            now = time.time()
            item = CacheItem.make(mtime=now, atime=now, ttl=ttl, data=data)
        else:
            item = data

        self.store_item(bank, key, item)

    def fetch_item(self, bank, key):
        if not self.contains(bank, key):
            return {}

        return self._cache[(bank, key)]

    def fetch(self, bank, key):
        if not self.contains(bank, key):
            return {}

        fetched = self.fetch_item(bank, key)
        return fetched.data

    def updated(self, bank, key):
        if not self.contains(bank, key):
            return None

        return self.fetch_item(bank, key).mtime

    def flush(self, bank, key=None):
        if key is None:
            for _key in self._list(bank):
                del self._cache[(bank, _key)]
        else:
            del self._cache[(bank, key)]

    def _list(self, bank):
        for _bank, key in self._cache:
            if bank == _bank:
                yield key

    def list(self, bank):
        return list(self._list(bank))

    def contains(self, bank, key=None):
        return (bank, key) in self._cache


class PluggableCache(six.with_metaclass(Singleton, IMSCache)):
    def store_item(self, bank, key, data):
        return self._cache.store(bank, key, data.__dict__)

    def fetch_item(self, bank, key):
        d = self._cache.fetch(bank, key)
        ci = CacheItem.make(**d)
        return ci

    def flush(self, bank, key=None):
        self._cache.flush(bank, key=key)

    def list(self, bank):
        return self._cache.list(bank)

    def contains(self, bank, key=None):
        return self._cache.contains(bank, key=key)


class TieredIMSCache(six.with_metaclass(Singleton, IMSCache)):
    def __init__(self, cache, shared):
        self._l1 = cache
        self._l2 = shared

    def store_item(self, bank, key, data):
        self._l2.store_item(bank, key, data)
        self._l1.store_item(bank, key, data)

    def fetch_item(self, bank, key):
        dat = self._l1.fetch_item(bank, key)
        if not dat:
            dat = self._l2.fetch_item(bank, key)
        return dat

    def list(self, bank):
        return self._l2.list(bank)

    def contains(self, bank, key=None):
        return self._l1.contains(bank, key=key) or self._l2.contains(bank,
                                                                     key=key)
