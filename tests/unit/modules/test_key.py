# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import os.path
from salt.modules import key

# Globals
key.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class KeyTestCase(TestCase):
    '''
    Test cases for salt.modules.key
    '''
    def test_finger(self):
        '''
        Test for finger
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.object(salt.utils,
                              'pem_finger', return_value='A'):
                with patch.dict(key.__opts__,
                        {'pki_dir': MagicMock(return_value='A'), 'hash_type': 'sha256'}):
                    self.assertEqual(key.finger(), 'A')

    def test_finger_master(self):
        '''
        Test for finger
        '''
        with patch.object(os.path, 'join', return_value='A'):
            with patch.object(salt.utils,
                              'pem_finger', return_value='A'):
                with patch.dict(key.__opts__,
                        {'pki_dir': 'A', 'hash_type': 'sha256'}):
                    self.assertEqual(key.finger_master(), 'A')
