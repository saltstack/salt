"""
unit tests for the slack engine
"""
import pytest

import salt.config
import salt.engines.slack as slack
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        slack.HAS_SLACKBOLT is False, reason="The slack_bolt is not installed"
    )
]


class MockSlackBoltSocketMode:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def connect(self, *args, **kwargs):
        return True


class MockSlackBoltApp:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

        self.client = None
        self.logger = None
        self.proxy = None

    def message(self, *args, **kwargs):
        return MagicMock(return_value=True)


@pytest.fixture
def configure_loader_modules():
    return {slack: {}}


@pytest.fixture
def slack_client():
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    app_token = "xapp-x-xxxxxxxxxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    bot_token = "xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"
    trigger = "!"

    with patch.dict(slack.__opts__, mock_opts):
        with patch(
            "slack_bolt.App", MagicMock(autospec=True, return_value=MockSlackBoltApp())
        ):
            with patch(
                "slack_bolt.adapter.socket_mode.SocketModeHandler",
                MagicMock(autospec=True, return_value=MockSlackBoltSocketMode()),
            ):
                slack_client = slack.SlackClient(app_token, bot_token, trigger)
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
