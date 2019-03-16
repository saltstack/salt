# -*- coding: utf-8 -*-
'''
Tests for the Telegram execution module.

:codeauthor: :email:`Roald Nefs (info@roaldnefs.com)`
'''

# Import Python Libs
from __future__ import absolute_import

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
import salt.modules.telegram as telegram


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TelegramModuleTest(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.telegram.
    '''
    def setup_loader_modules(self):
        module_globals = {
            telegram: {
                '__salt__': {
                    'config.get': MagicMock(return_value={
                        'telegram': {
                            'chat_id': '123456789',
                            'token': '000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
                        }
                    })
                }
            }
        }
        if telegram.HAS_REQUESTS is False:
            module_globals['sys.modules'] = {'requests': MagicMock()}
        return module_globals

    def test_post_message(self):
        '''
        Test the post_message function.
        '''
        message = 'Hello World!'

        class MockRequests(object):
            """
            Mock of requests response.
            """
            def json(self):
                return {'ok': True}

        with patch('salt.modules.telegram.requests.post',
                   MagicMock(return_value=MockRequests())):

            self.assertTrue(telegram.post_message(message))
