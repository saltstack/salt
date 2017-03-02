# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import http
import salt.utils.http

http.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HttpTestCase(TestCase):
    '''
    Test cases for salt.modules.http
    '''
    def test_query(self):
        '''
        Test for Query a resource, and decode the return data
        '''
        with patch.object(salt.utils.http, 'query', return_value='A'):
            self.assertEqual(http.query('url'), 'A')
