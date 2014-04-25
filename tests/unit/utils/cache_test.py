# -*- coding: utf-8 -*-
'''
    tests.unit.utils.cache_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt cache objects
'''

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import cache

import time


class CacheDictTestCase(TestCase):

    def test_sanity(self):
        '''
        Make sure you can instantiate etc.
        '''
        cd = cache.CacheDict(5)
        assert isinstance(cd, cache.CacheDict)

        # do some tests to make sure it looks like a dict
        assert 'foo' not in cd
        cd['foo'] = 'bar'
        assert cd['foo'] == 'bar'
        del cd['foo']
        assert 'foo' not in cd

    def test_ttl(self):
        cd = cache.CacheDict(0.1)
        cd['foo'] = 'bar'
        assert 'foo' in cd
        assert cd['foo'] == 'bar'
        time.sleep(0.1)
        assert 'foo' not in cd
        # make sure that a get would get a regular old key error
        self.assertRaises(KeyError, cd.__getitem__, 'foo')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CacheDictTestCase, needs_daemon=False)
