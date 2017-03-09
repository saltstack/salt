# -*- coding: utf-8 -*-
'''
    tests.unit.utils.cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt cache objects
'''

# Import python libs
from __future__ import absolute_import
import os
import time
import tempfile
import shutil

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
import salt.config
import salt.loader
from salt.utils import cache


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
            opts = salt.config.DEFAULT_MINION_OPTS
            opts['cachedir'] = tempfile.gettempdir()
            context_cache = cache.ContextCache(opts, 'cache_test')

            context_cache.cache_context({'a': 'b'})

            ret = context_cache.get_cache_context()

            self.assertDictEqual({'a': 'b'}, ret)

    def test_context_wrapper(self):
        '''
        Test to ensure that a module which decorates itself
        with a context cache can store and retreive its contextual
        data
        '''
        opts = salt.config.DEFAULT_MINION_OPTS
        opts['cachedir'] = tempfile.gettempdir()

        ll_ = salt.loader.LazyLoader(
                [os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cache_mods')],
                tag='rawmodule',
                virtual_enable=False,
                opts=opts)

        cache_test_func = ll_['cache_mod.test_context_module']

        self.assertEqual(cache_test_func()['called'], 0)
        self.assertEqual(cache_test_func()['called'], 1)
