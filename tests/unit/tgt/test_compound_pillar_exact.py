# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.compound_pillar_exact
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


class CompoundPillarExactTestCase(TestCase):
    '''
    Test cases for salt.tgt.compound_pillar_exact
    '''
    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_singular_I_exact(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I@alpha:bar:baz', 'compound_pillar_exact', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_singular_J_exact(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I@alpha:bar:*', 'compound_pillar_exact', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted([]))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_multiple_I_exact_or_glob(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact or glob
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I@alpha:bar:baz or *ta', 'compound_pillar_exact', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_multiple_I_exact_not_E(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact not PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'E@.* not I@alpha:bar:baz', 'compound_pillar_exact', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'gamma', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_multiple_J_and_list(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact and list
        '''
        ret = salt.tgt.check_minions(fake_opts,
                                     'I@alpha:bar:baz and L@beta,gamma',
                                     'compound_pillar_exact',
                                     greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted([]))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['beta', 'gamma']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_multiple_J_or_all_minions(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar_exact or all_minions
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I@alpha:bar:baz or R@a', 'compound_pillar_exact', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))
