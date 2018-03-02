# -*- coding: utf-8 -*-
'''
Test cases for salt.tgt.glob
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


class GlobTestCase(TestCase):
    '''
    Test cases for salt.tgt.glob
    '''
    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_glob_postfix(self):
        '''
        Test cases for glob with a fnmatch expression
        '''
        ret = salt.tgt.check_minions(fake_opts, 'a*', 'glob')
        self.assertEqual(sorted(ret['minions']), sorted(['alpha']))

    @patch('salt.tgt.pki_minions', MagicMock(
        return_value=['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta', 'lota', 'kappa']))
    def test_glob_prefix(self):
        '''
        Test cases for glob with a fnmatch expression
        '''
        ret = salt.tgt.check_minions(fake_opts, '*ta', 'glob')
        self.assertEqual(sorted(ret['minions']), sorted(['beta', 'delta', 'zeta', 'eta', 'theta', 'lota']))
