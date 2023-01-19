"""
Test the Google Chat Execution module.
"""

import pytest

import salt.modules.google_chat as gchat
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {gchat: {}}


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


def test_send_message_success():
    """
    Testing a successful message
    """
    with patch.dict(
        gchat.__utils__, {"http.query": mocked_http_query}
    ):  # pylint: disable=no-member
        assert gchat.send_message("https://example.com", "Yupiii")


def test_send_message_failure():
    """
    Testing a failed message
    """
    with patch.dict(
        gchat.__utils__, {"http.query": mocked_http_query_failure}
    ):  # pylint: disable=no-member
        assert not gchat.send_message("https://example.com", "Yupiii")
