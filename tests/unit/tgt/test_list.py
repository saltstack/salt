# -*- coding: utf-8 -*-
'''
Test case for salt.tgt.list
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


class ListTestCase(TestCase):
    '''
    Test case for salt.tgt.list
    '''
    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_list(self):
        '''
        Test case for list
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha,beta', 'list')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_list_with_malformed_item(self):
        '''
        Test case for list with a fnmatch expression
        '''
        ret = salt.tgt.check_minions(fake_opts, 'efef,beta,epsilon,a*', 'list')
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'epsilon']))
        self.assertEqual(sorted(ret['missing']), sorted(['a*', 'efef']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_list_with_whitespaces(self):
        '''
        Test case for list with whitespaces
        '''
        ret = salt.tgt.check_minions(fake_opts, 'alpha, beta', 'list')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha', 'beta']))
