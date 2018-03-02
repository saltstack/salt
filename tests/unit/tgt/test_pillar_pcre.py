# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.pillar_pcre
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


class PillarPcreTestCase(TestCase):
    '''
    Test cases for salt.tgt.pillar_pcre
    '''
    @patch('salt.tgt.check_cache_minions', MagicMock(return_value={'minions': ['alpha', 'beta', 'gamma']}))
    def test_pillar_pcre(self):
        '''
        Test case for checking being triggered the pillar_pcre module
        '''
        ret = salt.tgt.check_minions(fake_opts, 'a', tgt_type='pillar_pcre', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_pillar_pcre_match(self):
        '''
        Test case for pillar PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha:.*', tgt_type='pillar_pcre', delimiter=':', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_pillar_pcre_non_match(self):
        '''
        Test case for pillar PCRE with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha.bar.e.*', tgt_type='pillar_pcre', delimiter='.', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted([]))
