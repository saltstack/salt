# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.http as http
import salt.utils.http

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class HttpTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.http
    """

    def setup_loader_modules(self):
        return {http: {}}

    def test_query(self):
        """
        Test for Query a resource, and decode the return data
        """
        with patch.object(salt.utils.http, "query", return_value="A"):
            self.assertEqual(http.query("url"), "A")

    def test_wait_for_with_interval(self):
        """
        Test for wait_for_successful_query waits for request_interval
        """

        query_mock = MagicMock(side_effect=[{"error": "error"}, {}])

        with patch.object(salt.utils.http, "query", query_mock):
            with patch("time.sleep", MagicMock()) as sleep_mock:
                self.assertEqual(
                    http.wait_for_successful_query("url", request_interval=1), {}
                )
                sleep_mock.assert_called_once_with(1)

    def test_wait_for_without_interval(self):
        """
        Test for wait_for_successful_query waits for request_interval
        """

        query_mock = MagicMock(side_effect=[{"error": "error"}, {}])

        with patch.object(salt.utils.http, "query", query_mock):
            with patch("time.sleep", MagicMock()) as sleep_mock:
                self.assertEqual(http.wait_for_successful_query("url"), {})
                sleep_mock.assert_not_called()
