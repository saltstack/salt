# -*- coding: utf-8 -*-
'''
    tests.unit.utils.cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt cache objects
'''

# Import python libs
from __future__ import absolute_import
import time

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CacheDictTestCase, needs_daemon=False)
