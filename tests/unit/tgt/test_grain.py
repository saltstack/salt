# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.grain
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.tgt

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
    MagicMock,
)

fake_opts = {
    'transport': 'zeromq',
    'extension_modules': '',
    'minion_data_cache': True
}


class GrainTestCase(TestCase):
    '''
    Test cases for salt.tgt.grain
    '''
    @patch('salt.tgt.check_cache_minions', MagicMock(return_value={'minions': ['alpha', 'beta', 'gamma']}))
    def test_grain(self):
        '''
        Test case for checking being triggered the grain module
        '''
        ret = salt.tgt.check_minions(fake_opts, 'a', tgt_type='grain', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))

    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'alpha': 'bar:baz'}}))
    def test_grain_match(self):
        '''
        Test case for grain with a fnmatch expression
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha:*:*', tgt_type='grain', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'alpha': 'bar.baz'}}))
    def test_grain_match_delimiter(self):
        '''
        Test case for grain with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha.bar.*', tgt_type='grain', delimiter='.', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))
