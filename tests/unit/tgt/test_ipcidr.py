# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.ipcidr
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


class IpcidrTestCase(TestCase):
    '''
    Test cases for salt.tgt.ipcidr
    '''
    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv4': '192.168.0.1'}}))
    def test_ipcidr_v4(self):
        '''
        Test cases fo ipcidr with ipv4
        '''
        ret = salt.tgt.check_minions(fake_opts, u'192.168.0.1', tgt_type='ipcidr', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv6': '2001:db8::'}}))
    def test_ipcidr_v6(self):
        '''
        Test cases fo ipcidr with ipv6
        '''
        ret = salt.tgt.check_minions(fake_opts, u'2001:db8::', tgt_type='ipcidr', greedy=True)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv4': '192.168.1.1'}}))
    def test_ipcidr_subnet(self):
        '''
        Test cases fo ipcidr with a subnet expression
        '''
        ret = salt.tgt.check_minions(fake_opts, u'192.168.1.0/28', tgt_type='ipcidr', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.cache.Cache.list', MagicMock(return_value=['alpha']))
    @patch('salt.cache.Cache.fetch', MagicMock(return_value={'grains': {'ipv4': '192.168.1.1'}}))
    def test_ipcidr_malformed(self):
        '''
        Test cases fo ipcidr with a malformed expression
        '''
        ret = salt.tgt.check_minions(fake_opts, u'a', tgt_type='ipcidr', greedy=False)
        self.assertEqual(sorted(ret['minions']), sorted([]))
