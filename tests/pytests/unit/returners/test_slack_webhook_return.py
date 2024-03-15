"""
    :codeauthor: :email:`Carlos D. Álvaro <github@cdalvaro.io>`

    Unit tests for the Slack Webhook Returner.
"""

import pytest

import salt.returners.slack_webhook_return as slack_webhook
from tests.support.mock import patch


@pytest.fixture
def webhook():
    return "T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"


@pytest.fixture
def author_icon():
    return "https://platform.slack-edge.com/img/default_application_icon.png"


@pytest.fixture
def show_tasks():
    return True


@pytest.fixture
def minion_name():
    return "MacPro"


@pytest.fixture
def ret(minion_name):
    return {
        "fun_args": ["config.vim"],
        "jid": "20181227105933129338",
        "return": {
            "file_|-vim files present_|-/Users/cdalvaro/_|-recurse": {
                "comment": "The directory /Users/cdalvaro/ is in the correct state",
                "changes": {},
                "name": "/Users/cdalvaro/",
                "start_time": "10:59:52.252830",
                "result": True,
                "duration": 373.25,
                "__run_num__": 3,
                "__sls__": "config.vim",
                "__id__": "vim files present",
            },
            "pkg_|-vim present_|-vim_|-installed": {
                "comment": "All specified packages are already installed",
                "name": "vim",
                "start_time": "10:59:36.830591",
                "result": True,
                "duration": 1280.127,
                "__run_num__": 0,
                "__sls__": "config.vim",
                "changes": {},
                "__id__": "vim present",
            },
            "git_|-salt vim plugin updated_|-https://github.com/saltstack/salt-vim.git_|-latest": {
                "comment": (
                    "https://github.com/saltstack/salt-vim.git cloned to"
                    " /Users/cdalvaro/.vim/pack/git-plugins/start/salt"
                ),
                "name": "https://github.com/saltstack/salt-vim.git",
                "start_time": "11:00:01.892757",
                "result": True,
                "duration": 11243.445,
                "__run_num__": 6,
                "__sls__": "config.vim",
                "changes": {
                    "new": (
                        "https://github.com/saltstack/salt-vim.git =>"
                        " /Users/cdalvaro/.vim/pack/git-plugins/start/salt"
                    ),
                    "revision": {
                        "new": "6ca9e3500cc39dd417b411435d58a1b720b331cc",
                        "old": None,
                    },
                },
                "__id__": "salt vim plugin updated",
            },
            "pkg_|-macvim present_|-caskroom/cask/macvim_|-installed": {
                "comment": (
                    "The following packages failed to install/update:"
                    " caskroom/cask/macvim"
                ),
                "name": "caskroom/cask/macvim",
                "start_time": "10:59:38.111119",
                "result": False,
                "duration": 14135.45,
                "__run_num__": 1,
                "__sls__": "config.vim",
                "changes": {},
                "__id__": "macvim present",
            },
        },
        "retcode": 2,
        "success": True,
        "fun": "state.apply",
        "id": minion_name,
        "out": "highstate",
    }


@pytest.fixture
def evnt_ret(minion_name):
    return [
        {
            "data": {
                "fun_args": ["config.vim"],
                "jid": "20181227105933129338",
                "return": {
                    "file_|-vim files present_|-/Users/cdalvaro/_|-recurse": {
                        "comment": "The directory /Users/cdalvaro/ is in the correct state",
                        "changes": {},
                        "name": "/Users/cdalvaro/",
                        "start_time": "10:59:52.252830",
                        "result": True,
                        "duration": 373.25,
                        "__run_num__": 3,
                        "__sls__": "config.vim",
                        "__id__": "vim files present",
                    },
                    "pkg_|-vim present_|-v ju im_|-installed": {
                        "comment": "All specified packages are already installed",
                        "name": "vim",
                        "start_time": "10:59:36.830591",
                        "result": True,
                        "duration": 1280.127,
                        "__run_num__": 0,
                        "__sls__": "config.vim",
                        "changes": {},
                        "__id__": "vim present",
                    },
                    "git_|-salt vim plugin updated_|-https://github.com/saltstack/salt-vim.git_|-latest": {
                        "comment": "https://github.com/saltstack/salt-vim.git cloned to /Users/cdalvaro/.vim/pack/git-plugins/start/salt",
                        "name": "https://github.com/saltstack/salt-vim.git",
                        "start_time": "11:00:01.892757",
                        "result": True,
                        "duration": 11243.445,
                        "__run_num__": 6,
                        "__sls__": "config.vim",
                        "changes": {
                            "new": "https://github.com/saltstack/salt-vim.git => /Users/cdalvaro/.vim/pack/git-plugins/start/salt",
                            "revision": {
                                "new": "6ca9e3500cc39dd417b411435d58a1b720b331cc",
                                "old": None,
                            },
                        },
                        "__id__": "salt vim plugin updated",
                    },
                    "pkg_|-macvim present_|-caskroom/cask/macvim_|-installed": {
                        "comment": "The following packages failed to install/update: caskroom/cask/macvim",
                        "name": "caskroom/cask/macvim",
                        "start_time": "10:59:38.111119",
                        "result": False,
                        "duration": 14135.45,
                        "__run_num__": 1,
                        "__sls__": "config.vim",
                        "changes": {},
                        "__id__": "macvim present",
                    },
                },
                "retcode": 2,
                "success": True,
                "fun": "state.apply",
                "id": minion_name,
                "out": "highstate",
            }
        }
    ]


@pytest.fixture
def expected_payload(minion_name, author_icon):
    return {
        "attachments": [
            {
                "title": "Success: False",
                "color": "#272727",
                "text": (
                    "Function: state.apply\nFunction Args: ['config.vim']\nJID:"
                    " 20181227105933129338\nTotal: 4\nDuration: 27.03 secs"
                ),
                "author_link": f"{minion_name}",
                "author_name": f"{minion_name}",
                "fallback": f"{minion_name} | Failed",
                "author_icon": author_icon,
            },
            {"color": "good", "title": "Unchanged: 2"},
            {
                "color": "warning",
                "fields": [
                    {
                        "short": False,
                        "value": "config.vim.sls | salt vim plugin updated",
                    }
                ],
                "title": "Changed: 1",
            },
            {
                "color": "danger",
                "fields": [
                    {"short": False, "value": "config.vim.sls | macvim present"}
                ],
                "title": "Failed: 1",
            },
        ]
    }


@pytest.fixture
def configure_loader_modules(webhook, author_icon, show_tasks):
    return {
        slack_webhook: {
            "__opts__": {
                "slack_webhook.webhook": webhook,
                "slack_webhook.author_icon": author_icon,
                "slack_webhook.success_title": "{id} | Succeeded",
                "slack_webhook.failure_title": "{id} | Failed",
                "slack_webhook.show_tasks": show_tasks,
            }
        }
    }


def test_no_webhook(ret):
    """
    Test returner stops if no webhook is defined
    """
    with patch.dict(slack_webhook.__opts__, {"slack_webhook.webhook": ""}):
        assert slack_webhook.returner(ret) is None


def test_returner(ret):
    """
    Test to see if the Slack Webhook returner sends a message
    """
    query_ret = {"body": "ok", "status": 200}
    with patch("salt.utils.http.query", return_value=query_ret):
        assert slack_webhook.returner(ret)


def test_event_return(evnt_ret):
    """
    Test to see if the Slack Webhook event_return sends a message
    """
    query_ret = {"body": "ok", "status": 200}
    with patch("salt.utils.http.query", return_value=query_ret):
        assert slack_webhook.event_return(evnt_ret)


def test_generate_payload_for_state_apply(
    ret, minion_name, show_tasks, expected_payload, author_icon
):
    """
    Test _generate_payload private method
    """
    test_title = f"{minion_name} | Failed"
    test_report = slack_webhook._generate_report(ret, show_tasks)

    custom_grains = slack_webhook.__grains__
    custom_grains["id"] = minion_name
    custom_grains["localhost"] = minion_name

    with patch.dict(slack_webhook.__grains__, custom_grains):
        test_payload = slack_webhook._generate_payload(
            author_icon, test_title, test_report
        )

    assert test_payload == expected_payload


def test_generate_payload_for_test_ping(minion_name, author_icon, show_tasks):
    """
    Test _generate_payload private method
    """

    test_ping_ret = {
        "jid": "20200124204109195206",
        "return": True,
        "retcode": 0,
        "id": minion_name,
        "fun": "test.ping",
        "fun_args": [],
        "success": True,
    }
    expected_payload = {
        "attachments": [
            {
                "fallback": f"{minion_name} | Succeeded",
                "color": "#272727",
                "author_name": minion_name,
                "author_link": minion_name,
                "author_icon": author_icon,
                "title": "Success: True",
                "text": "Function: test.ping\nJID: 20200124204109195206\n",
            },
            {"color": "good", "title": "Return: True"},
        ]
    }

    test_title = f"{minion_name} | Succeeded"
    test_report = slack_webhook._generate_report(test_ping_ret, show_tasks)

    custom_grains = slack_webhook.__grains__
    custom_grains["id"] = minion_name
    custom_grains["localhost"] = minion_name

    with patch.dict(slack_webhook.__grains__, custom_grains):
        test_payload = slack_webhook._generate_payload(
            author_icon, test_title, test_report
        )

    assert test_payload == expected_payload
