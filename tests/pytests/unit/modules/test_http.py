"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.http
"""


import pytest

import salt.modules.http as http
import salt.utils.http
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {http: {}}


def test_query():
    """
    Test for Query a resource, and decode the return data
    """
    with patch.object(salt.utils.http, "query", return_value="A"):
        assert http.query("url") == "A"


def test_wait_for_with_interval():
    """
    Test for wait_for_successful_query waits for request_interval
    """

    query_mock = MagicMock(side_effect=[{"error": "error"}, {}])

    with patch.object(salt.utils.http, "query", query_mock):
        with patch("time.sleep", MagicMock()) as sleep_mock:
            assert http.wait_for_successful_query("url", request_interval=1) == {}
            sleep_mock.assert_called_once_with(1)


def test_wait_for_without_interval():
    """
    Test for wait_for_successful_query waits for request_interval
    """

    query_mock = MagicMock(side_effect=[{"error": "error"}, {}])

    with patch.object(salt.utils.http, "query", query_mock):
        with patch("time.sleep", MagicMock()) as sleep_mock:
            assert http.wait_for_successful_query("url") == {}
            sleep_mock.assert_not_called()
