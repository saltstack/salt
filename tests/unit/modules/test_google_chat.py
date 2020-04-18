# -*- coding: utf-8 -*-
"""
Test the Google Chat Execution module.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.google_chat as gchat

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


def mocked_http_query(url, method, **kwargs):  # pylint: disable=unused-argument
    """
    Mocked data for test_send_message_success
    """
    return {"status": 200, "dict": None}


def mocked_http_query_failure(url, method, **kwargs):  # pylint: disable=unused-argument
    """
    Mocked data for test_send_message_failure
    """
    return {"status": 522, "dict": None}


class TestModulesCfutils(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.google_chat
    """

    def setup_loader_modules(self):
        return {gchat: {}}

    def test_send_message_success(self):
        """
        Testing a successful message
        """
        with patch.dict(
            gchat.__utils__, {"http.query": mocked_http_query}
        ):  # pylint: disable=no-member
            self.assertTrue(gchat.send_message("https://example.com", "Yupiii"))

    def test_send_message_failure(self):
        """
        Testing a failed message
        """
        with patch.dict(
            gchat.__utils__, {"http.query": mocked_http_query_failure}
        ):  # pylint: disable=no-member
            self.assertFalse(gchat.send_message("https://example.com", "Yupiii"))
