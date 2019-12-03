# -*- coding: utf-8 -*-
'''
    tests.unit.utils.cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt cache objects
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import time
import tempfile
import shutil

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import salt libs
import salt.config
import salt.loader
import salt.payload
import salt.utils.data
import salt.utils.files
import salt.utils.cache as cache


class CacheDictTestCase(TestCase):

    def test_sanity(self):
        '''
        Make sure you can instantiate etc.
        '''
        cd = cache.CacheDict(5)
        self.assertIsInstance(cd, cache.CacheDict)

        # do some tests to make sure it looks like a dict
        self.assertNotIn('foo', cd)
        cd['foo'] = 'bar'
        self.assertEqual(cd['foo'], 'bar')
        del cd['foo']
        self.assertNotIn('foo', cd)

    def test_ttl(self):
        cd = cache.CacheDict(0.1)
        cd['foo'] = 'bar'
        self.assertIn('foo', cd)
        self.assertEqual(cd['foo'], 'bar')
        time.sleep(0.2)
        self.assertNotIn('foo', cd)

        # make sure that a get would get a regular old key error
        self.assertRaises(KeyError, cd.__getitem__, 'foo')


class CacheContextTestCase(TestCase):

    def setUp(self):
        context_dir = os.path.join(tempfile.gettempdir(), 'context')
        if os.path.exists(context_dir):
            shutil.rmtree(os.path.join(tempfile.gettempdir(), 'context'))

    def test_smoke_context(self):
        '''
        Smoke test the context cache
        '''
        if os.path.exists(os.path.join(tempfile.gettempdir(), 'context')):
            self.skipTest('Context dir already exists')
        else:
            opts = salt.config.DEFAULT_MINION_OPTS.copy()
            opts['cachedir'] = tempfile.gettempdir()
            context_cache = cache.ContextCache(opts, 'cache_test')

            context_cache.cache_context({'a': 'b'})

            ret = context_cache.get_cache_context()

            self.assertDictEqual({'a': 'b'}, ret)

    def test_context_wrapper(self):
        '''
        Test to ensure that a module which decorates itself
        with a context cache can store and retrieve its contextual
        data
        '''
        opts = salt.config.DEFAULT_MINION_OPTS.copy()
        opts['cachedir'] = tempfile.gettempdir()

        ll_ = salt.loader.LazyLoader(
                [os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cache_mods')],
                tag='rawmodule',
                virtual_enable=False,
                opts=opts)

        cache_test_func = ll_['cache_mod.test_context_module']

        self.assertEqual(cache_test_func()['called'], 0)
        self.assertEqual(cache_test_func()['called'], 1)


__context__ = {'a': 'b'}
__opts__ = {'cachedir': '/tmp'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ContextCacheTest(TestCase):
    '''
    Test case for salt.utils.cache.ContextCache
    '''
    def setUp(self):
        '''
        Clear the cache before every test
        '''
        context_dir = os.path.join(__opts__['cachedir'], 'context')
        if os.path.isdir(context_dir):
            shutil.rmtree(context_dir)

    def test_set_cache(self):
        '''
        Tests to ensure the cache is written correctly
        '''
        @cache.context_cache
        def _test_set_cache():
            '''
            This will inherit globals from the test module itself.
            Normally these are injected by the salt loader [salt.loader]
            '''
            pass

        _test_set_cache()

        target_cache_file = os.path.join(__opts__['cachedir'], 'context', '{0}.p'.format(__name__))
        self.assertTrue(os.path.isfile(target_cache_file), 'Context cache did not write cache file')

        # Test manual de-serialize
        with salt.utils.files.fopen(target_cache_file, 'rb') as fp_:
            target_cache_data = salt.utils.data.decode(salt.payload.Serial(__opts__).load(fp_))
        self.assertDictEqual(__context__, target_cache_data)

        # Test cache de-serialize
        cc = cache.ContextCache(__opts__, __name__)
        retrieved_cache = cc.get_cache_context()
        self.assertDictEqual(retrieved_cache, __context__)

    def test_refill_cache(self):
        '''
        Tests to ensure that the context cache can rehydrate a wrapped function
        '''
        # First populate the cache
        @cache.context_cache
        def _test_set_cache():
            pass
        _test_set_cache()

        # Then try to rehydate a func
        @cache.context_cache
        def _test_refill_cache(comparison_context):
            self.assertEqual(__context__, comparison_context)

        global __context__
        __context__ = {}
        _test_refill_cache({'a': 'b'})  # Compare to the context before it was emptied


class CacheDiskTestCase(TestCase):

    def test_everything(self):
        '''
        Make sure you can instantiate, add, update, remove, expire
        '''
        try:
            tmpdir = tempfile.mkdtemp()
            path = os.path.join(tmpdir, 'CacheDisk_test')

            # test instantiation
            cd = cache.CacheDisk(0.1, path)
            self.assertIsInstance(cd, cache.CacheDisk)

            # test to make sure it looks like a dict
            self.assertNotIn('foo', cd)
            cd['foo'] = 'bar'
            self.assertIn('foo', cd)
            self.assertEqual(cd['foo'], 'bar')
            del cd['foo']
            self.assertNotIn('foo', cd)

            # test persistence
            cd['foo'] = 'bar'
            cd2 = cache.CacheDisk(0.1, path)
            self.assertIn('foo', cd2)
            self.assertEqual(cd2['foo'], 'bar')

            # test ttl
            time.sleep(0.2)
            self.assertNotIn('foo', cd)
            self.assertNotIn('foo', cd2)

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
