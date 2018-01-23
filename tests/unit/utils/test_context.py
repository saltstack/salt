# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libraries
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

# Import Salt testing libraries
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt libraries
import salt.payload
import salt.utils.cache
import salt.utils.data
import salt.utils.files

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
        @salt.utils.cache.context_cache
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
        cc = salt.utils.cache.ContextCache(__opts__, __name__)
        retrieved_cache = cc.get_cache_context()
        self.assertDictEqual(retrieved_cache, __context__)

    def test_refill_cache(self):
        '''
        Tests to ensure that the context cache can rehydrate a wrapped function
        '''
        # First populate the cache
        @salt.utils.cache.context_cache
        def _test_set_cache():
            pass
        _test_set_cache()

        # Then try to rehydate a func
        @salt.utils.cache.context_cache
        def _test_refill_cache(comparison_context):
            self.assertEqual(__context__, comparison_context)

        global __context__
        __context__ = {}
        _test_refill_cache({'a': 'b'})  # Compare to the context before it was emptied
