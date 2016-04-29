# -*- coding: utf-8 -*-
'''
Loader mechanism for caching data, with data expirations, etc.

.. versionadded:: carbon
'''
from __future__ import absolute_import
import os
import time
from salt.loader import LazyLoader

class Cache(object):
    '''
    Main caching object
    '''
    def __init__(self, opts, driver=None):
        self.opts = opts
        self.modules = self._modules()
        if driver is None:
            driver = 'msgpack'
        self.driver = driver

    def _modules(self, functions=None, whitelist=None):
        '''
        Lazy load the cache modules
        '''
        codedir = os.path.dirname(os.path.realpath(__file__))
        return LazyLoader(
            [codedir],
            self.opts,
            tag='cache',
            pack={
                '__opts__': self.opts,
                '__cache__': functions
            },
            whitelist=whitelist,
        )

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

        if data is None or update_cache is True:
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
        '''
        fun = '{0}.{1}'.format(self.driver, 'store')
        return self.modules[fun](bank, key, data)

    def fetch(self, bank, key):
        '''
        Fetch data using the specified module
        '''
        fun = '{0}.{1}'.format(self.driver, 'fetch')
        return self.modules[fun](bank, key)

    def updated(self, bank, key):
        '''
        Return the last updated epoch for the specified key
        '''
        fun = '{0}.{1}'.format(self.driver, 'updated')
        return self.modules[fun](bank, key)
