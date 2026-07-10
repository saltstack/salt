"""
Tests for salt.modules.slack module
"""

import logging
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

    # bare minimum - from_name is now optional and, when omitted, the
    # deprecated `username` field must not be sent (Slack rejects it with
    # legacy_custom_bots_deprecated, see issue #67948).
    with patch("salt.utils.slack.query", slack_query):
        message_params = {
            "channel": "fake_channel",
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


def test_post_message_legacy_from_name_preserved_with_warning(caplog):
    """
    Regression test for #67948.

    When a caller explicitly passes ``from_name``/``icon`` (the legacy
    Slack custom-bot fields), the values must still be forwarded to Slack
    for backward compatibility, but a deprecation warning must be logged.
    """
    slack_query = MagicMock(return_value={"res": True})

    with patch("salt.utils.slack.query", slack_query), caplog.at_level(
        logging.WARNING, logger="salt.modules.slack_notify"
    ):
        message_params = {
            "channel": "fake_channel",
            "message": "test message",
            "from_name": "salt server",
            "icon": "https://example.com/icon.png",
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
                    "text": "test message",
                    "attachments": [],
                    "blocks": [],
                    "username": "salt server",
                    "icon_url": "https://example.com/icon.png",
                }
            ),
            opts=slack_notify.__opts__,
        )
    assert any(
        "from_name" in rec.getMessage() and "deprecated" in rec.getMessage()
        for rec in caplog.records
    )
    assert any(
        "icon" in rec.getMessage() and "deprecated" in rec.getMessage()
        for rec in caplog.records
    )


def test_post_message_omits_username_when_from_name_absent():
    """
    Regression test for #67948.

    Ensure the deprecated ``username`` field is not present in the
    request body when the caller does not provide ``from_name``. Slack
    rejects calls that include ``username`` from classic/custom-bot
    apps with ``legacy_custom_bots_deprecated`` since 2025-03-31.
    """
    slack_query = MagicMock(return_value={"res": True})
    with patch("salt.utils.slack.query", slack_query):
        assert slack_notify.post_message(
            channel="fake_channel",
            message="hi",
            api_key="xxx-xx-xxx",
        )
    call_kwargs = slack_query.call_args.kwargs
    body = call_kwargs["data"]
    assert "username=" not in body
    assert "icon_url=" not in body
