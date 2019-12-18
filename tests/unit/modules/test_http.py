# -*- coding: utf-8 -*-
'''
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    patch,
)

# Import Salt Libs
import salt.modules.http as http
import salt.utils.http


class HttpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.http
    '''
    def setup_loader_modules(self):
        return {http: {}}

    def test_query(self):
        '''
        Test for Query a resource, and decode the return data
        '''
        with patch.object(salt.utils.http, 'query', return_value='A'):
            self.assertEqual(http.query('url'), 'A')
