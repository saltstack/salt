# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import inspect

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
import salt.modules.defaults as defaults


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DefaultsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.defaults
    '''
    def setup_loader_modules(self):
        return {defaults: {}}

    def test_get_mock(self):
        '''
        Test if it execute a defaults client run and return a dict
        '''
        with patch.object(inspect, 'stack', MagicMock(return_value=[])), \
                patch('salt.modules.defaults.get',
                      MagicMock(return_value={'users': {'root': [0]}})):
            self.assertEqual(defaults.get('core:users:root'),
                             {'users': {'root': [0]}})
