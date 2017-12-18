# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.pillar
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


class PillarTestCase(TestCase):
    '''
    Test cases for salt.tgt.pillar
    '''
    @patch('salt.tgt.check_cache_minions', MagicMock(return_value={'minions': ['alpha', 'beta', 'gamma']}))
    def tespt_pillar(self):
        '''
        Test case for checking being triggered the pillar module
        '''
        ret = salt.tgt.check_minions(fake_opts, 'a', tgt_type='pillar', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))

    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_pillar_greedy(self):
        '''
        Test case for pillar
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha:*:*', tgt_type='pillar', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar.baz'}}))
    def test_pillar_non_greedy(self):
        '''
        Test case for pillar PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha.bar.*', tgt_type='pillar', delimiter='.', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))
