# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.compound
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


class CompoundTestCase(TestCase):
    '''
    Test cases for salt.tgt.compound
    '''
    @patch('salt.tgt.check_compound_minions', MagicMock(return_value={'minions': ['alpha', 'beta', 'gamma']}))
    def test_compound(self):
        '''
        Test case for checking being triggered the compound module
        '''
        ret = salt.tgt.check_minions(fake_opts, '', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    def test_compound_glob(self):
        '''
        Test case for glob
        '''
        ret = salt.tgt.check_minions(fake_opts, '*ta', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'abc': 'bar:baz'}}))
    def test_compound_singular_G(self):  # pylint: disable=invalid-name
        '''
        Test case for grains
        '''
        ret = salt.tgt.check_minions(fake_opts, 'G@abc:*:*', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'abc': 'bar#baz'}}))
    def test_compound_singular_G_alt_delimiter(self):  # pylint: disable=invalid-name
        '''
        Test case for grains with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'G#@abc#*#*', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'abc': 'bar:baz'}}))
    def test_compound_singular_P(self):  # pylint: disable=invalid-name
        '''
        Test case for grains PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'P@abc:bar:\\w+', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'abc': 'bar.baz'}}))
    def test_compound_singular_P_alt_delimiter(self):  # pylint: disable=invalid-name
        '''
        Test case for grains PCRE with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'P.@abc.bar.\\w+', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_singular_I(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I@alpha:bar:*', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar!baz'}}))
    def test_compound_singular_I_alt_delimiter(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'I!@alpha!bar!*', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar:baz'}}))
    def test_compound_singular_J(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'J@alpha:.*:baz', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'alpha': 'bar%baz'}}))
    def test_compound_singular_J_alt_delimieter(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar PCRE with another delimiter
        '''
        ret = salt.tgt.check_minions(fake_opts, 'J%@alpha%.*%baz', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_compound_singular_L(self):  # pylint: disable=invalid-name
        '''
        Test case for list
        '''
        ret = salt.tgt.check_minions(fake_opts, 'L@alpha,gamma', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'gamma']))

    def test_compound_singular_N(self):  # pylint: disable=invalid-name
        '''
        Test case for nodegroup, this option should be handled before compound module called
        '''
        ret = salt.tgt.check_minions(fake_opts, 'N@alpha,gamma', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted([]))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv6': '2001:db8::'}}))
    def test_compound_singular_S(self):  # pylint: disable=invalid-name
        '''
        Test case for ipcidr
        '''
        ret = salt.tgt.check_minions(fake_opts, 'S@2001:db8::', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    def test_compound_singular_E(self):  # pylint: disable=invalid-name
        '''
        Test case for PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'E@\\w+t\\w+', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_compound_singular_R(self):  # pylint: disable=invalid-name
        '''
        Test case for all_minions
        '''
        ret = salt.tgt.check_minions(fake_opts, 'R@a', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'gamma']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_compound_singular_malformed(self):  # pylint: disable=invalid-name
        '''
        Test case for malformed expr, compound module will call salt.tgt.glob.check_minions
        '''
        ret = salt.tgt.check_minions(fake_opts, 'H@a', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted([]))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_compound_multiple_E_and_L(self):  # pylint: disable=invalid-name
        '''
        Test case for PCRE and list
        '''
        ret = salt.tgt.check_minions(fake_opts, 'E@a\\w+ and L@alpha,beta', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv4': '192.168.0.1'}}))
    def test_compound_multiple_S_or_glob(self):  # pylint: disable=invalid-name
        '''
        Test case for picidr or glob
        '''
        ret = salt.tgt.check_minions(fake_opts, 'S@192.168.0.0/28 or *ta', tgt_type='compound', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha', 'beta']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'pillar': {'abc': 'bar!baz'}}))
    def test_compound_multiple_J_not_E(self):  # pylint: disable=invalid-name
        '''
        Test case for pillar PCRE not PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, 'J!@abc!bar!\\w+ not E@a\\w+', tgt_type='compound', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['beta']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma', 'iota']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha', 'beta']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'abc': 'bar!baz'}}))
    def test_compound_multiple_open_E_or_L_close_not_G(self):  # pylint: disable=invalid-name
        '''
        Test case for ( PCRE or list ) not grians
        '''
        ret = salt.tgt.check_minions(fake_opts,
                                     '( L@alpha,gamma or E@.*ta ) not G!@abc!bar!*',
                                     tgt_type='compound',
                                     greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['gamma', 'iota']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    @patch('salt.tgt.pki_dir_minions', MagicMock(return_value=['alpha', 'beta', 'gamma']))
    def test_compound_muleiple_malformed(self):  # pylint: disable=invalid-name
        '''
        Test case for malformed expr, compound module will call salt.tgt.glob.check_minions
        '''
        ret = salt.tgt.check_minions(fake_opts, 'R@a and K@b', 'compound')
        self.assertEqual(sorted(ret['minions']), sorted([]))
