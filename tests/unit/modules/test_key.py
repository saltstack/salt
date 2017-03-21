# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os.path

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils
import salt.modules.key as key


@skipIf(NO_MOCK, NO_MOCK_REASON)
class KeyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.key
    '''
    loader_module = key

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
