# -*- coding: utf-8 -*-
'''
unit tests for the cache runner
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.runners import cache
import salt.utils

cache.__opts__ = {}
cache.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CacheTest(TestCase):
    '''
    Validate the cache runner
    '''
    def test_grains(self):
        '''
        test cache.grains runner
        '''
        mock_minion = ['Larry']
        mock_ret = {}
        self.assertEqual(cache.grains(minion=mock_minion), mock_ret)

        mock_data = 'grain stuff'

        class MockMaster(object):
            def __init__(self, *args, **kwargs):
                pass

            def get_minion_grains(self):
                return mock_data

        with patch.object(salt.utils.master, 'MasterPillarUtil', MockMaster):
            self.assertEqual(cache.grains(), mock_data)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CacheTest, needs_daemon=False)
