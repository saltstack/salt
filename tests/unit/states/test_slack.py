# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.slack as slack

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SlackTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.slack
    """

    def setup_loader_modules(self):
        return {slack: {}}

    # 'post_message' function tests: 1

    def test_post_message_apikey(self):
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
            comt = "The following message is to be sent to Slack: {0}".format(message)
            ret.update({"comment": comt})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    from_name=from_name,
                    message=message,
                    api_key=api_key,
                ),
                ret,
            )

        with patch.dict(slack.__opts__, {"test": False}):
            comt = "Please specify api_key or webhook."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=None,
                    from_name=from_name,
                    message=message,
                    api_key=None,
                ),
                ret,
            )

            comt = "Slack channel is missing."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=None,
                    from_name=from_name,
                    message=message,
                    api_key=api_key,
                ),
                ret,
            )

            comt = "Slack from name is missing."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    from_name=None,
                    message=message,
                    api_key=api_key,
                ),
                ret,
            )

            comt = "Slack message is missing."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    from_name=from_name,
                    message=None,
                    api_key=api_key,
                ),
                ret,
            )

            mock = MagicMock(return_value=True)
            with patch.dict(slack.__salt__, {"slack.post_message": mock}):
                comt = "Sent message: slack-message"
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    slack.post_message(
                        name,
                        channel=channel,
                        from_name=from_name,
                        message=message,
                        api_key=api_key,
                    ),
                    ret,
                )

    def test_post_message_webhook(self):
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
            comt = "The following message is to be sent to Slack: {0}".format(message)
            ret.update({"comment": comt})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    username=username,
                    message=message,
                    webhook=webhook,
                ),
                ret,
            )

        with patch.dict(slack.__opts__, {"test": False}):
            comt = "Please specify api_key or webhook."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name, channel=channel, username=username, message=None, webhook=None
                ),
                ret,
            )

            comt = "Please specify only either api_key or webhook."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    username=username,
                    message=message,
                    api_key=api_key,
                    webhook=webhook,
                ),
                ret,
            )

            comt = "Slack message is missing."
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(
                slack.post_message(
                    name,
                    channel=channel,
                    username=username,
                    message=None,
                    webhook=webhook,
                ),
                ret,
            )

            mock = MagicMock(return_value=True)
            with patch.dict(slack.__salt__, {"slack.call_hook": mock}):
                comt = "Sent message: slack-message"
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    slack.post_message(
                        name,
                        channel=channel,
                        username=username,
                        message=message,
                        webhook=webhook,
                    ),
                    ret,
                )
