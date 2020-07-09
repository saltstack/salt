# -*- coding: utf-8 -*-
"""
Tests for the Telegram execution module.

:codeauthor: :email:`Roald Nefs (info@roaldnefs.com)`
"""

# Import Python Libs
from __future__ import absolute_import

import logging

# Import Salt Libs
import salt.modules.telegram as telegram

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, Mock
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class RequestMock(Mock):
    """
    Request Mock
    """

    def get(self, *args, **kwargs):
        return RequestResponseMock()

    def put(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestPutResponseMock()

    def delete(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return RequestResponseMock()


class RequestResponseMock(Mock):
    """
    Request Response Mock
    """

    def json(self):
        return [
            {"url": "http://example.org", "_id": 1234},
        ]


class RequestPutResponseMock(Mock):
    """
    Request Put Response Mock
    """

    ok = True

    def json(self):
        return {"_id": 4321}


class TelegramModuleTest(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.telegram.
    """

    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {
                "config.get": MagicMock(
                    return_value={
                        "telegram": {
                            "chat_id": "123456789",
                            "token": "000000000:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        }
                    }
                ),
                "requests.put": Mock(),
            },
            "requests": RequestMock(),
        }
        return {telegram: module_globals}

    def test_post_message(self):
        """
        Test the post_message function.
        """
        message = "Hello World!"
        self.assertTrue(telegram.post_message(message))
