"""
unit tests for the slack engine
"""
import pytest

import salt.engines.slack_bolt_engine as slack_bolt_engine
from tests.support.mock import MagicMock, call, patch

pytestmark = [
    pytest.mark.skipif(
        slack_bolt_engine.HAS_SLACKBOLT is False,
        reason="The slack_bolt is not installed",
    )
]


class MockRunnerClient:
    """
    Mock RunnerClient class
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def asynchronous(self, *args, **kwargs):
        """
        Mock asynchronous method
        """
        return True


class MockLocalClient:
    """
    Mock RunnerClient class
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def cmd_async(self, *args, **kwargs):
        """
        Mock cmd_async method
        """
        return True


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

        self.client = MockSlackBoltAppClient()
        self.logger = None
        self.proxy = None

    def message(self, *args, **kwargs):
        return MagicMock(return_value=True)


class MockSlackBoltAppClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def chat_postMessage(self, *args, **kwargs):
        return MagicMock(return_value=True)

    def files_upload(self, *args, **kwargs):
        return MagicMock(return_value=True)


@pytest.fixture
def configure_loader_modules():
    return {slack_bolt_engine: {}}


@pytest.fixture
def slack_client(minion_opts):
    app_token = "xapp-x-xxxxxxxxxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    bot_token = "xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"
    trigger = "!"

    with patch.dict(slack_bolt_engine.__opts__, minion_opts):
        with patch(
            "slack_bolt.App", MagicMock(autospec=True, return_value=MockSlackBoltApp())
        ):
            with patch(
                "slack_bolt.adapter.socket_mode.SocketModeHandler",
                MagicMock(autospec=True, return_value=MockSlackBoltSocketMode()),
            ):
                slack_client = slack_bolt_engine.SlackClient(
                    app_token, bot_token, trigger
                )
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


def test_run_commands_from_slack_async(slack_client):
    """
    Test slack engine: test_run_commands_from_slack_async
    """

    mock_job_status = {
        "20221027001127600438": {
            "data": {"minion": {"return": True, "retcode": 0, "success": True}},
            "function": "test.ping",
        }
    }

    message_generator = [
        {
            "message_data": {
                "client_msg_id": "c1d0c13d-5e78-431e-9921-4786a7d27543",
                "type": "message",
                "text": '!test.ping target="minion"',
                "user": "U02QY11UJ",
                "ts": "1666829486.542159",
                "blocks": [
                    {
                        "type": "rich_text",
                        "block_id": "2vdy",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": '!test.ping target="minion"',
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "team": "T02QY11UG",
                "channel": "C02QY11UQ",
                "event_ts": "1666829486.542159",
                "channel_type": "channel",
            },
            "channel": "C02QY11UQ",
            "user": "U02QY11UJ",
            "user_name": "garethgreenaway",
            "cmdline": ["test.ping"],
            "target": {"target": "minion", "tgt_type": "glob"},
        }
    ]

    mock_files_upload_resp = {
        "ok": True,
        "file": {
            "id": "F047YTDGJF9",
            "created": 1666883749,
            "timestamp": 1666883749,
            "name": "salt-results-20221027081549173603.yaml",
            "title": "salt-results-20221027081549173603",
            "mimetype": "text/plain",
            "filetype": "yaml",
            "pretty_type": "YAML",
            "user": "U0485K894PN",
            "user_team": "T02QY11UG",
            "editable": True,
            "size": 18,
            "mode": "snippet",
            "is_external": False,
            "external_type": "",
            "is_public": True,
            "public_url_shared": False,
            "display_as_bot": False,
            "username": "",
            "url_private": "",
            "url_private_download": "",
            "permalink": "",
            "permalink_public": "",
            "edit_link": "",
            "preview": "minion:\n    True",
            "preview_highlight": "",
            "lines": 2,
            "lines_more": 0,
            "preview_is_truncated": False,
            "comments_count": 0,
            "is_starred": False,
            "shares": {
                "public": {
                    "C02QY11UQ": [
                        {
                            "reply_users": [],
                            "reply_users_count": 0,
                            "reply_count": 0,
                            "ts": "1666883749.485979",
                            "channel_name": "general",
                            "team_id": "T02QY11UG",
                            "share_user_id": "U0485K894PN",
                        }
                    ]
                }
            },
            "channels": ["C02QY11UQ"],
            "groups": [],
            "ims": [],
            "has_rich_preview": False,
            "file_access": "visible",
        },
    }

    patch_app_client_files_upload = patch.object(
        MockSlackBoltAppClient,
        "files_upload",
        MagicMock(autospec=True, return_value=mock_files_upload_resp),
    )
    patch_app_client_chat_postMessage = patch.object(
        MockSlackBoltAppClient,
        "chat_postMessage",
        MagicMock(autospec=True, return_value=True),
    )
    patch_slack_client_run_until = patch.object(
        slack_client, "_run_until", MagicMock(autospec=True, side_effect=[True, False])
    )
    patch_slack_client_run_command_async = patch.object(
        slack_client,
        "run_command_async",
        MagicMock(autospec=True, return_value="20221027001127600438"),
    )
    patch_slack_client_get_jobs_from_runner = patch.object(
        slack_client,
        "get_jobs_from_runner",
        MagicMock(autospec=True, return_value=mock_job_status),
    )

    upload_calls = call(
        channels="C02QY11UQ",
        content="minion:\n    True",
        filename="salt-results-20221027090136014442.yaml",
    )

    chat_postMessage_calls = [
        call(
            channel="C02QY11UQ",
            text="@garethgreenaway's job is submitted as salt jid 20221027001127600438",
        ),
        call(
            channel="C02QY11UQ",
            text="@garethgreenaway's job `['test.ping']` (id: 20221027001127600438) (target: {'target': 'minion', 'tgt_type': 'glob'}) returned",
        ),
    ]

    #
    # test with control as True and fire_all as False
    #
    with patch_slack_client_run_until, patch_slack_client_run_command_async, patch_slack_client_get_jobs_from_runner, patch_app_client_files_upload as app_client_files_upload, patch_app_client_chat_postMessage as app_client_chat_postMessage:
        slack_client.run_commands_from_slack_async(
            message_generator=message_generator,
            fire_all=False,
            tag="salt/engines/slack",
            control=True,
        )
        app_client_files_upload.asser_has_calls(upload_calls)
        app_client_chat_postMessage.asser_has_calls(chat_postMessage_calls)

    #
    # test with control and fire_all as True
    #
    patch_slack_client_run_until = patch.object(
        slack_client, "_run_until", MagicMock(autospec=True, side_effect=[True, False])
    )

    mock_event_send = MagicMock(return_value=True)
    patch_event_send = patch.dict(
        slack_bolt_engine.__salt__, {"event.send": mock_event_send}
    )

    event_send_calls = [
        call(
            "salt/engines/slack/message",
            {
                "message_data": {
                    "client_msg_id": "c1d0c13d-5e78-431e-9921-4786a7d27543",
                    "type": "message",
                    "text": '!test.ping target="minion"',
                    "user": "U02QY11UJ",
                    "ts": "1666829486.542159",
                    "blocks": [
                        {
                            "type": "rich_text",
                            "block_id": "2vdy",
                            "elements": [
                                {
                                    "type": "rich_text_section",
                                    "elements": [
                                        {
                                            "type": "text",
                                            "text": '!test.ping target="minion"',
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "team": "T02QY11UG",
                    "channel": "C02QY11UQ",
                    "event_ts": "1666829486.542159",
                    "channel_type": "channel",
                },
                "channel": "C02QY11UQ",
                "user": "U02QY11UJ",
                "user_name": "garethgreenaway",
                "cmdline": ["test.ping"],
                "target": {"target": "minion", "tgt_type": "glob"},
            },
        )
    ]
    with patch_slack_client_run_until, patch_slack_client_run_command_async, patch_slack_client_get_jobs_from_runner, patch_event_send, patch_app_client_files_upload as app_client_files_upload, patch_app_client_chat_postMessage as app_client_chat_postMessage:
        slack_client.run_commands_from_slack_async(
            message_generator=message_generator,
            fire_all=True,
            tag="salt/engines/slack",
            control=True,
        )
        app_client_files_upload.asser_has_calls(upload_calls)
        app_client_chat_postMessage.asser_has_calls(chat_postMessage_calls)
        mock_event_send.asser_has_calls(event_send_calls)


def test_run_command_async(slack_client):
    """
    Test slack engine: test_run_command_async
    """

    msg = {
        "message_data": {
            "client_msg_id": "6c71d7f9-a44d-402f-8f9f-d1bb5b650853",
            "type": "message",
            "text": '!test.ping target="minion"',
            "user": "U02QY11UJ",
            "ts": "1667427929.764169",
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": "AjL",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {"type": "text", "text": '!test.ping target="minion"'}
                            ],
                        }
                    ],
                }
            ],
            "team": "T02QY11UG",
            "channel": "C02QY11UQ",
            "event_ts": "1667427929.764169",
            "channel_type": "channel",
        },
        "channel": "C02QY11UQ",
        "user": "U02QY11UJ",
        "user_name": "garethgreenaway",
        "cmdline": ["test.ping"],
        "target": {"target": "minion", "tgt_type": "glob"},
    }

    local_client_mock = MagicMock(autospec=True, return_value=MockLocalClient())
    patch_local_client = patch("salt.client.LocalClient", local_client_mock)

    local_client_cmd_async_mock = MagicMock(
        autospec=True, return_value={"jid": "20221027001127600438"}
    )
    patch_local_client_cmd_async = patch.object(
        MockLocalClient, "cmd_async", local_client_cmd_async_mock
    )

    expected_calls = [call("minion", "test.ping", arg=[], kwarg={}, tgt_type="glob")]
    with patch_local_client, patch_local_client_cmd_async as local_client_cmd_async:
        ret = slack_client.run_command_async(msg)
        local_client_cmd_async.assert_has_calls(expected_calls)

    msg = {
        "message_data": {
            "client_msg_id": "35f4783f-8913-4687-8f04-21182bcacd5a",
            "type": "message",
            "text": "!test.arg arg1 arg2 arg3 key1=value1 key2=value2",
            "user": "U02QY11UJ",
            "ts": "1667429460.576889",
            "blocks": [
                {
                    "type": "rich_text",
                    "block_id": "EAzTy",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {
                                    "type": "text",
                                    "text": "!test.arg arg1 arg2 arg3 key1=value1 key2=value2",
                                }
                            ],
                        }
                    ],
                }
            ],
            "team": "T02QY11UG",
            "channel": "C02QY11UQ",
            "event_ts": "1667429460.576889",
            "channel_type": "channel",
        },
        "channel": "C02QY11UQ",
        "user": "U02QY11UJ",
        "user_name": "garethgreenaway",
        "cmdline": ["test.arg", "arg1", "arg2", "arg3", "key1=value1", "key2=value2"],
        "target": {"target": "*", "tgt_type": "glob"},
    }

    runner_client_mock = MagicMock(autospec=True, return_value=MockRunnerClient())
    patch_runner_client = patch("salt.runner.RunnerClient", runner_client_mock)

    runner_client_asynchronous_mock = MagicMock(
        autospec=True, return_value={"jid": "20221027001127600438"}
    )
    patch_runner_client_asynchronous = patch.object(
        MockRunnerClient, "asynchronous", runner_client_asynchronous_mock
    )

    expected_calls = [
        call(
            "test.arg",
            {
                "arg": ["arg1", "arg2", "arg3"],
                "kwarg": {"key1": "value1", "key2": "value2"},
            },
        )
    ]
    with patch_runner_client, patch_runner_client_asynchronous as runner_client_asynchronous:
        ret = slack_client.run_command_async(msg)
        runner_client_asynchronous.assert_has_calls(expected_calls)
