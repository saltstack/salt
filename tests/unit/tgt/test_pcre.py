# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.pcre
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
    'extension_modules': ''
}


class PcreTestCase(TestCase):
    '''
    Test cases for salt.tgt.pcre
    '''
    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_pcre(self):
        '''
        Test cases for PCRE
        '''
        ret = salt.tgt.check_minions(fake_opts, '.*ta', 'pcre')
        self.assertEqual(sorted(ret['minions']),
                         sorted(['beta', 'delta', 'zeta', 'eta', 'theta', 'lota']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_pcre_complex(self):
        '''
        Test cases for PCRE with a complex expression
        '''
        ret = salt.tgt.check_minions(fake_opts, 'beta|.*pa|\\w+ma', 'pcre')
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'gamma', 'kappa']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_pcre_malformed(self):
        '''
        Test cases for PCRE with a malformed expression
        '''
        ret = salt.tgt.check_minions(fake_opts, '*', 'pcre')
        self.assertEqual(sorted(ret['minions']), sorted([]))
