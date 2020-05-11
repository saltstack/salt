# -*- coding: utf-8 -*-
'''
Tests for the Mandrill execution module.
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.mandrill as mandrill

# Test data
TEST_SEND = {
    'result': True,
    'comment': '',
    'out': [
        {
            'status': 'sent',
            '_id': 'c4353540a3c123eca112bbdd704ab6',
            'email': 'recv@example.com',
            'reject_reason': None
        }
    ]
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MandrillModuleTest(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.mandrill.
    '''
    def setup_loader_modules(self):
        module_globals = {
            mandrill: {
                '__salt__': {
                    'config.merge': MagicMock(return_value={
                        'mandrill': {
                            'key': '2orgk34kgk34g'
                        }
                    })
                }
            }
        }
        if mandrill.HAS_REQUESTS is False:
            module_globals['sys.modules'] = {'requests': MagicMock()}
        return module_globals

    def test_send(self):
        '''
        Test the send function.
        '''
        mock_cmd = MagicMock(return_value=TEST_SEND)
        with patch.object(mandrill, 'send', mock_cmd) as send:
            self.assertEqual(
                send(message={
                        'subject': 'Hi',
                        'from_email': 'test@example.com',
                        'to': [
                            {'email': 'recv@example.com', 'type': 'to'}
                        ]
                    }
                ),
                TEST_SEND
            )
