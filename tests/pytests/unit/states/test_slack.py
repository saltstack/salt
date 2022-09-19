"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""

import pytest

import salt.states.slack as slack
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {slack: {}}


def test_post_message_apikey():
    """
    Test to send a message to a Slack channel using an API Key.
    """
    name = "slack-message"
    channel = "#general"
    from_name = "SuperAdmin"
    message = "This state was executed successfully."
    api_key = "xoxp-XXXXXXXXXX-XXXXXXXXXX-XXXXXXXXXX-XXXXXX"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(slack.__opts__, {"test": True}):
        mock = MagicMock(return_value=True)
        with patch.dict(slack.__salt__, {"config.get": mock}):
            comt = "The following message is to be sent to Slack: {}".format(message)
            ret.update({"comment": comt})
            assert (
                slack.post_message(
                    name,
                    channel=channel,
                    from_name=from_name,
                    message=message,
                    api_key=api_key,
                )
                == ret
            )

    with patch.dict(slack.__opts__, {"test": False}):
        mock = MagicMock(return_value=False)
        with patch.dict(slack.__salt__, {"config.get": mock}):
            comt = "Please specify api_key or webhook."
            ret.update({"comment": comt, "result": False})
            assert (
                slack.post_message(
                    name,
                    channel=None,
                    from_name=from_name,
                    message=message,
                    api_key=None,
                )
                == ret
            )

        comt = "Slack channel is missing."
        ret.update({"comment": comt, "result": False})
        assert (
            slack.post_message(
                name,
                channel=None,
                from_name=from_name,
                message=message,
                api_key=api_key,
            )
            == ret
        )

        comt = "Slack from name is missing."
        ret.update({"comment": comt, "result": False})
        assert (
            slack.post_message(
                name,
                channel=channel,
                from_name=None,
                message=message,
                api_key=api_key,
            )
            == ret
        )

        comt = "Slack message is missing."
        ret.update({"comment": comt, "result": False})
        assert (
            slack.post_message(
                name,
                channel=channel,
                from_name=from_name,
                message=None,
                api_key=api_key,
            )
            == ret
        )

        mock = MagicMock(return_value=True)
        with patch.dict(slack.__salt__, {"slack.post_message": mock}):
            comt = "Sent message: slack-message"
            ret.update({"comment": comt, "result": True})
            assert (
                slack.post_message(
                    name,
                    channel=channel,
                    from_name=from_name,
                    message=message,
                    api_key=api_key,
                )
                == ret
            )


def test_post_message_webhook():
    """
    Test to send a message to a Slack channel using an webhook.
    """
    name = "slack-message"
    channel = "#general"
    username = "SuperAdmin"
    message = "This state was executed successfully."
    webhook = "XXXXXXXXX/XXXXXXXXX/XXXXXXXXXXXXXXXXXXXXXXXX"
    api_key = "xoxp-XXXXXXXXXX-XXXXXXXXXX-XXXXXXXXXX-XXXXXX"

    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    with patch.dict(slack.__opts__, {"test": True}):
        mock = MagicMock(return_value=True)
        with patch.dict(slack.__salt__, {"config.get": mock}):
            comt = "The following message is to be sent to Slack: {}".format(message)
            ret.update({"comment": comt})
            assert (
                slack.post_message(
                    name,
                    channel=channel,
                    username=username,
                    message=message,
                    webhook=webhook,
                )
                == ret
            )

    with patch.dict(slack.__opts__, {"test": False}):
        mock = MagicMock(return_value=False)
        with patch.dict(slack.__salt__, {"config.get": mock}):
            comt = "Please specify api_key or webhook."
            ret.update({"comment": comt, "result": False})
            assert (
                slack.post_message(
                    name, channel=channel, username=username, message=None, webhook=None
                )
                == ret
            )

        comt = "Please specify only either api_key or webhook."
        ret.update({"comment": comt, "result": False})
        assert (
            slack.post_message(
                name,
                channel=channel,
                username=username,
                message=message,
                api_key=api_key,
                webhook=webhook,
            )
            == ret
        )

        comt = "Slack message is missing."
        ret.update({"comment": comt, "result": False})
        assert (
            slack.post_message(
                name,
                channel=channel,
                username=username,
                message=None,
                webhook=webhook,
            )
            == ret
        )

        mock = MagicMock(return_value=True)
        with patch.dict(slack.__salt__, {"slack.call_hook": mock}):
            comt = "Sent message: slack-message"
            ret.update({"comment": comt, "result": True})
            assert (
                slack.post_message(
                    name,
                    channel=channel,
                    username=username,
                    message=message,
                    webhook=webhook,
                )
                == ret
            )
