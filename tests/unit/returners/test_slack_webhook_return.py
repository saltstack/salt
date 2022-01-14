"""
    :codeauthor: :email:`Carlos D. Álvaro <github@cdalvaro.io>`

    tests.unit.returners.test_slack_webhook_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Unit tests for the Slack Webhook Returner.
"""


import salt.returners.slack_webhook_return as slack_webhook
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class SlackWebhookReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test slack_webhook returner
    """

    _WEBHOOK = "T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
    _AUTHOR_ICON = "https://platform.slack-edge.com/img/default_application_icon.png"
    _SHOW_TASKS = True
    _MINION_NAME = "MacPro"

    _RET = {
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
        "id": _MINION_NAME,
        "out": "highstate",
    }

    _EVNT_RET = [
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
                "id": _MINION_NAME,
                "out": "highstate",
            }
        }
    ]

    _EXPECTED_PAYLOAD = {
        "attachments": [
            {
                "title": "Success: False",
                "color": "#272727",
                "text": (
                    "Function: state.apply\nFunction Args: ['config.vim']\nJID:"
                    " 20181227105933129338\nTotal: 4\nDuration: 27.03 secs"
                ),
                "author_link": "{}".format(_MINION_NAME),
                "author_name": "{}".format(_MINION_NAME),
                "fallback": "{} | Failed".format(_MINION_NAME),
                "author_icon": _AUTHOR_ICON,
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

    def setup_loader_modules(self):
        return {
            slack_webhook: {
                "__opts__": {
                    "slack_webhook.webhook": self._WEBHOOK,
                    "slack_webhook.author_icon": self._AUTHOR_ICON,
                    "slack_webhook.success_title": "{id} | Succeeded",
                    "slack_webhook.failure_title": "{id} | Failed",
                    "slack_webhook.show_tasks": self._SHOW_TASKS,
                }
            }
        }

    def test_no_webhook(self):
        """
        Test returner stops if no webhook is defined
        """
        with patch.dict(slack_webhook.__opts__, {"slack_webhook.webhook": ""}):
            self.assertEqual(slack_webhook.returner(self._RET), None)

    def test_returner(self):
        """
        Test to see if the Slack Webhook returner sends a message
        """
        query_ret = {"body": "ok", "status": 200}
        with patch("salt.utils.http.query", return_value=query_ret):
            self.assertTrue(slack_webhook.returner(self._RET))

    def test_event_return(self):
        """
        Test to see if the Slack Webhook event_return sends a message
        """
        query_ret = {"body": "ok", "status": 200}
        with patch("salt.utils.http.query", return_value=query_ret):
            self.assertTrue(slack_webhook.event_return(self._EVNT_RET))

    def test_generate_payload_for_state_apply(self):
        """
        Test _generate_payload private method
        """
        test_title = "{} | Failed".format(self._MINION_NAME)
        test_report = slack_webhook._generate_report(self._RET, self._SHOW_TASKS)

        custom_grains = slack_webhook.__grains__
        custom_grains["id"] = self._MINION_NAME
        custom_grains["localhost"] = self._MINION_NAME

        with patch.dict(slack_webhook.__grains__, custom_grains):
            test_payload = slack_webhook._generate_payload(
                self._AUTHOR_ICON, test_title, test_report
            )

        self.assertDictEqual(test_payload, self._EXPECTED_PAYLOAD)

    def test_generate_payload_for_test_ping(self):
        """
        Test _generate_payload private method
        """

        test_ping_ret = {
            "jid": "20200124204109195206",
            "return": True,
            "retcode": 0,
            "id": self._MINION_NAME,
            "fun": "test.ping",
            "fun_args": [],
            "success": True,
        }
        expected_payload = {
            "attachments": [
                {
                    "fallback": "{} | Succeeded".format(self._MINION_NAME),
                    "color": "#272727",
                    "author_name": self._MINION_NAME,
                    "author_link": self._MINION_NAME,
                    "author_icon": self._AUTHOR_ICON,
                    "title": "Success: True",
                    "text": "Function: test.ping\nJID: 20200124204109195206\n",
                },
                {"color": "good", "title": "Return: True"},
            ]
        }

        test_title = "{} | Succeeded".format(self._MINION_NAME)
        test_report = slack_webhook._generate_report(test_ping_ret, self._SHOW_TASKS)

        custom_grains = slack_webhook.__grains__
        custom_grains["id"] = self._MINION_NAME
        custom_grains["localhost"] = self._MINION_NAME

        with patch.dict(slack_webhook.__grains__, custom_grains):
            test_payload = slack_webhook._generate_payload(
                self._AUTHOR_ICON, test_title, test_report
            )

        self.assertDictEqual(test_payload, expected_payload)
