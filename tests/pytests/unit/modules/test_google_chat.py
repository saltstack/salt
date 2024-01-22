"""
Test the Google Chat Execution module.
"""

import pytest

import salt.modules.google_chat as gchat
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {gchat: {}}


def test_send_message_success():
    """
    Testing a successful message
    """
    with patch(
        "salt.utils.http.query", MagicMock(return_value={"status": 200, "dict": None})
    ):
        assert gchat.send_message("https://example.com", "Yupiii")


def test_send_message_failure():
    """
    Testing a failed message
    """
    with patch(
        "salt.utils.http.query", MagicMock(return_value={"status": 522, "dict": None})
    ):
        assert not gchat.send_message("https://example.com", "Yupiii")
