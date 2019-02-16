# -*- coding: utf-8 -*-
'''
unit tests for salt.cache.imscache
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil
import tempfile

import cachetools

# Import Salt Testing libs
# import integration
from tests.support import mock
from tests.support.unit import TestCase

# Import Salt libs
from salt.cache import imscache
from salt.ext.six.moves import range


class ImsOptionsTest(TestCase):
    def setUp(self):
        imscache.Singleton._instances = {}

    def test_default_policy(self):
        opts = {
            'worker_cache': 'IMSCache',
        }
        self.cache = imscache.cache_from_opts(opts=opts)
        self.assertIsInstance(self.cache, imscache.IMSCache)
        self.assertIsInstance(self.cache._cache, cachetools.Cache)
        self.assertEqual(self.cache._cache.maxsize,
                         imscache.DEFAULT_POLICY['maxsize'])

    def test_policy(self):
        opts = {
            'worker_cache': 'IMSCache',
            'worker_cache_policy': {
                'maxsize': 20
            }
        }
        self.cache = imscache.cache_from_opts(opts=opts)
        self.assertIsInstance(self.cache, imscache.IMSCache)
        self.assertIsInstance(self.cache._cache, cachetools.Cache)
        self.assertEqual(self.cache._cache.maxsize, 20)

    def test_pluggable(self):
        opts = {
            'worker_cache': 'PluggableCache',
            'cache': 'foo'
        }
        self.cache = imscache.cache_from_opts(opts=opts)
        self.assertIsInstance(self.cache, imscache.PluggableCache)
        self.assertEqual(self.cache._cache.driver, 'foo')

    def test_tiered(self):
        opts = {
            'worker_cache': 'TieredIMSCache',
            'worker_cache_tiered': 'redis'
        }
        self.cache = imscache.cache_from_opts(opts=opts)
        self.assertIsInstance(self.cache, imscache.TieredIMSCache)
        self.assertEqual(self.cache._l2._cache.driver, 'redis')


class IMSCacheTestSimple(TestCase):
    def setUp(self):
        imscache.Singleton._instances = {}
        opts = {
            'worker_cache': 'IMSCache',
        }
        self.cache = imscache.cache_from_opts(opts=opts)

    def test_cache_basic_behavior(self):
        self.cache.store("1", "1", imscache.CacheItem.make(data="1/1"))
        self.cache.store("1", "2", imscache.CacheItem.make(data="1/2"))
        self.cache.store("2", "1", imscache.CacheItem.make(data="2/1"))

        self.assertSetEqual(set(self.cache.list("1")), set(["1", "2"]))
        self.assertSetEqual(set(self.cache.list("2")), set(["1"]))

        self.assertEqual(self.cache.fetch("1", "1"), "1/1")

    def test_backwards_compat(self):
        now = 0

        def _mock_time():
            return now

        with mock.patch('time.time', side_effect=_mock_time):
            self.cache.cache("1", "1", fun=lambda **kwargs: "123")
            self.assertEqual(self.cache.fetch("1", "1"), "123")
            now = 86401
            self.cache.cache("1", "1", fun=lambda **kwargs: "1234")
            self.assertEqual(self.cache.fetch("1", "1"), "1234")

    def test_cache(self):
        now = 0
        calls = {'called': 0}

        def _mock_time():
            return now

        def load_cache_fun(item, **kwargs):
            calls['called'] += 1
            data = "called {}".format(now)
            ttl = 10

            return imscache.CacheItem.make(ttl=ttl, data=data)

        with mock.patch('time.time', side_effect=_mock_time):
            for i in range(3):
                data = self.cache.cache("1", "1", fun=load_cache_fun)
                self.assertEqual(data, "called 0")
            self.assertEqual(calls['called'], 1)
            now = 11
            data = self.cache.cache("1", "1", fun=load_cache_fun)
            self.assertEqual(data, "called 11")
            self.assertEqual(calls['called'], 2)

    def test_conditional_cache(self):
        """Always re-validate; only fetch when cache tag changes."""
        now = 0
        tag = "XXX"
        calls = {
            'loads': 0,
            'validates': 0,
        }

        def _mock_time():
            return now

        def load_cache_fun():
            calls['loads'] += 1
            return tag, "called {}".format(now)

        def conditional_load_fun(item, **kwargs):
            calls['validates'] += 1
            cached_tag = item.extra.get('tag', {})

            # i.e. 304 not modified
            if cached_tag == tag:
                return item

            _tag, data = load_cache_fun()
            data = data
            extra = {'tag': _tag}
            ttl = 0

            return imscache.CacheItem.make(ttl=ttl, data=data, extra=extra)

        with mock.patch('time.time', side_effect=_mock_time):
            for i in range(3):
                data = self.cache.cache("1", "1", fun=conditional_load_fun)
                self.assertEqual(data, "called 0")
                now += 1
            self.assertEqual(calls['loads'], 1)
            self.assertEqual(calls['validates'], 3)

            now = 4
            tag = "YYY"
            data = self.cache.cache("1", "1", fun=conditional_load_fun)
            self.assertEqual(data, "called 4")
            self.assertEqual(calls['loads'], 2)
            self.assertEqual(calls['validates'], 4)


class PluggableCacheTestSimple(IMSCacheTestSimple):
    def setUp(self):
        imscache.Singleton._instances = {}
        self.tmp_dir = tempfile.mkdtemp()

        opts = {
            'worker_cache': 'PluggableCache',
            'extension_modules': '.',
            'rootdir': self.tmp_dir,
            'cachedir': os.path.join(self.tmp_dir, 'cache'),
        }
        self.cache = imscache.cache_from_opts(opts=opts)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class TieredIMSCacheTestSimple(IMSCacheTestSimple):
    def setUp(self):
        imscache.Singleton._instances = {}
        self.tmp_dir = tempfile.mkdtemp()

        opts = {
            'worker_cache': 'TieredIMSCache',
            'extension_modules': '.',
            'rootdir': self.tmp_dir,
            'cachedir': os.path.join(self.tmp_dir, 'cache'),

        }
        self.cache = imscache.cache_from_opts(opts=opts)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # Fix to handle max size
    def test_tiered_caching(self):
        now = 0
        calls = {'called': 0}

        def _mock_time():
            return now

        def load_cache_fun(item, **kwargs):
            calls['called'] += 1
            data = "called {}".format(now)
            ttl = 10

            return imscache.CacheItem.make(ttl=ttl, data=data)

        with mock.patch('time.time', side_effect=_mock_time):
            for i in range(10):
                data = self.cache.cache("1", "{}".format(i), fun=load_cache_fun)
                self.assertEqual(data, "called 0")
            self.assertEqual(calls['called'], 10)

            for i in range(10):
                data = self.cache.cache("1", "{}".format(i), fun=load_cache_fun)
                self.assertEqual(data, "called 0")
            self.assertEqual(calls['called'], 10)

            # Trigger in-memory eviction
            data = self.cache.cache("2", "1", fun=load_cache_fun)
            self.assertEqual(data, "called 0")
            self.assertEqual(calls['called'], 11)

            # Trigger load from tiered cache
            for i in range(10):
                data = self.cache.cache("1", "{}".format(i), fun=load_cache_fun)
                self.assertEqual(data, "called 0")
            self.assertEqual(calls['called'], 11)
            self.assertEqual(len(self.cache._l1._cache), 10)
