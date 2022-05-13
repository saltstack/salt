"""
Tests for salt.modules.slack module
"""

import urllib.parse

import pytest
import salt.modules.slack_notify as slack_notify
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {slack_notify: {}}


def test_post_message():
    """
    Tests the post_message function sends data as expected
    """
    slack_query = MagicMock(return_value={"res": True})

    # bare minimum
    with patch("salt.utils.slack.query", slack_query):
        message_params = {
            "channel": "fake_channel",
            "from_name": "salt server",
            "message": "test message",
            "api_key": "xxx-xx-xxx",
        }
        assert slack_notify.post_message(**message_params)
        slack_query.assert_called_with(
            function="message",
            api_key="xxx-xx-xxx",
            method="POST",
            header_dict={"Content-Type": "application/x-www-form-urlencoded"},
            data=urllib.parse.urlencode(
                {
                    "channel": "#fake_channel",
                    "username": "salt server",
                    "text": "test message",
                    "attachments": [],
                    "blocks": [],
                }
            ),
            opts=slack_notify.__opts__,
        )

    # send `blocks` and `attachments` params
    with patch("salt.utils.slack.query", slack_query):
        message_params = {
            "channel": "fake_channel",
            "from_name": "salt server",
            "message": "test message",
            "api_key": "xxx-xx-xxx",
            "attachments": [{"text": "And heres an attachment!"}],
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "New request"},
                }
            ],
        }
        assert slack_notify.post_message(**message_params)
        slack_query.assert_called_with(
            function="message",
            api_key="xxx-xx-xxx",
            method="POST",
            header_dict={"Content-Type": "application/x-www-form-urlencoded"},
            data=urllib.parse.urlencode(
                {
                    "channel": "#fake_channel",
                    "username": "salt server",
                    "text": "test message",
                    "attachments": [{"text": "And heres an attachment!"}],
                    "blocks": [
                        {
                            "type": "header",
                            "text": {"type": "plain_text", "text": "New request"},
                        }
                    ],
                }
            ),
            opts=slack_notify.__opts__,
        )
