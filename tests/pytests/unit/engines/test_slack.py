"""
unit tests for the slack engine
"""

import pytest

import salt.engines.slack as slack
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        slack.HAS_SLACKCLIENT is False, reason="The SlackClient is not installed"
    )
]


@pytest.fixture
def configure_loader_modules():
    return {slack: {}}


@pytest.fixture
def slack_client(minion_opts):
    token = "xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"

    with patch.dict(slack.__opts__, minion_opts):
        with patch("slackclient.SlackClient.rtm_connect", MagicMock(return_value=True)):
            slack_client = slack.SlackClient(token)
            yield slack_client


def test_control_message_target(slack_client):
    """
    Test slack engine: control_message_target
    """
    trigger_string = "!"

    loaded_groups = {
        "default": {
            "targets": {},
            "commands": {"cmd.run", "test.ping"},
            "default_target": {"tgt_type": "glob", "target": "*"},
            "users": {"gareth"},
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
    target_commandline = slack_client.control_message_target(
        slack_user_name, text, loaded_groups, trigger_string
    )

    assert target_commandline == _expected

    # Check aliases result in correct cmdline
    text = "!whoami"
    target_commandline = slack_client.control_message_target(
        slack_user_name, text, loaded_groups, trigger_string
    )

    assert target_commandline == _expected

    # Check pillar is overridden
    _expected = (
        True,
        {"tgt_type": "glob", "target": "*"},
        ["pillar.items", 'pillar={"hello": "world"}'],
    )
    text = r"""!list_pillar pillar='{"hello": "world"}'"""
    target_commandline = slack_client.control_message_target(
        slack_user_name, text, loaded_groups, trigger_string
    )

    assert target_commandline == _expected

    # Check target is overridden
    _expected = (
        True,
        {"tgt_type": "glob", "target": "localhost"},
        ["cmd.run", "whoami"],
    )
    text = "!cmd.run whoami target='localhost'"
    target_commandline = slack_client.control_message_target(
        slack_user_name, text, loaded_groups, trigger_string
    )

    assert target_commandline == _expected
