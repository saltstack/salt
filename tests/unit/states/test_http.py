# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.http as http

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HttpTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the HTTP state
    '''
    def setup_loader_modules(self):
        return {http: {}}

    def test_query(self):
        '''
            Test to perform an HTTP query and statefully return the result
        '''
        ret = [{'changes': {},
                'comment': ' Either match text (match) or a '
                'status code (status) is required.', 'data': {},
                'name': 'salt', 'result': False},
               {'changes': {}, 'comment': ' (TEST MODE)', 'data': True, 'name': 'salt',
                'result': None}]
        self.assertDictEqual(http.query("salt"), ret[0])

        with patch.dict(http.__opts__, {'test': True}):
            mock = MagicMock(return_value=True)
            with patch.dict(http.__salt__, {'http.query': mock}):
                self.assertDictEqual(http.query("salt", "Dude", "stack"),
                                     ret[1])
