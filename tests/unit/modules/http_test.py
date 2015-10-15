# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
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

if __name__ == '__main__':
    from integration import run_tests
    run_tests(HttpTestCase, needs_daemon=False)
