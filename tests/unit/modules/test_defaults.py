# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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

import inspect

# Import Salt Libs
from salt.modules import defaults

# Globals
defaults.__grains__ = {}
defaults.__salt__ = {}
defaults.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DefaultsTestCase(TestCase):
    '''
    Test cases for salt.modules.defaults
    '''
    @patch('salt.modules.defaults.get',
           MagicMock(return_value={'users': {'root': [0]}}))
    def test_get_mock(self):
        '''
        Test if it execute a defaults client run and return a dict
        '''
        with patch.object(inspect, 'stack', MagicMock(return_value=[])):
            self.assertEqual(defaults.get('core:users:root'),
                             {'users': {'root': [0]}})
