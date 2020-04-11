# -*- coding: utf-8 -*-
"""
unit tests for the slack engine
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.config

# Import Salt Libs
import salt.engines.slack as slack

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(slack.HAS_SLACKCLIENT is False, "The SlackClient is not installed")
class EngineSlackTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.engine.slack
    """

    def setup_loader_modules(self):
        return {slack: {}}

    def setUp(self):
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        token = "xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"

        with patch.dict(slack.__opts__, mock_opts):
            with patch(
                "slackclient.SlackClient.rtm_connect", MagicMock(return_value=True)
            ):
                self.client = slack.SlackClient(token)

    def test_control_message_target(self):
        """
        Test slack engine: control_message_target
        """
        trigger_string = "!"

        loaded_groups = {
            "default": {
                "targets": {},
                "commands": set(["cmd.run", "test.ping"]),
                "default_target": {"tgt_type": "glob", "target": "*"},
                "users": set(["gareth"]),
                "aliases": {
                    "whoami": {"cmd": "cmd.run whoami"},
                    "list_pillar": {"cmd": "pillar.items"},
                },
            }
        }

        slack_user_name = "gareth"

        # Check for correct cmdline
        _expected = (True, {"tgt_type": "glob", "target": "*"}, ["cmd.run", "whoami"])
        text = "!cmd.run whoami"
        target_commandline = self.client.control_message_target(
            slack_user_name, text, loaded_groups, trigger_string
        )

        self.assertEqual(target_commandline, _expected)

        # Check aliases result in correct cmdline
        text = "!whoami"
        target_commandline = self.client.control_message_target(
            slack_user_name, text, loaded_groups, trigger_string
        )

        self.assertEqual(target_commandline, _expected)

        # Check pillar is overrided
        _expected = (
            True,
            {"tgt_type": "glob", "target": "*"},
            ["pillar.items", 'pillar={"hello": "world"}'],
        )
        text = r"""!list_pillar pillar='{"hello": "world"}'"""
        target_commandline = self.client.control_message_target(
            slack_user_name, text, loaded_groups, trigger_string
        )

        self.assertEqual(target_commandline, _expected)

        # Check target is overrided
        _expected = (
            True,
            {"tgt_type": "glob", "target": "localhost"},
            ["cmd.run", "whoami"],
        )
        text = "!cmd.run whoami target='localhost'"
        target_commandline = self.client.control_message_target(
            slack_user_name, text, loaded_groups, trigger_string
        )

        self.assertEqual(target_commandline, _expected)
