# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Carlos D. Álvaro <github@cdalvaro.io>`

    tests.unit.returners.test_slack_webhook_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Unit tests for the Slack Webhook Returner.
"""

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.returners.slack_webhook_return as slack_webhook

# Import Salt Testing libs
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
                "pchanges": {},
                "name": "/Users/cdalvaro/",
                "start_time": "10:59:52.252830",
                "result": True,
                "duration": 373.25,
                "__run_num__": 3,
                "__sls__": "config.vim",
                "changes": {},
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

    _EXPECTED_PAYLOAD = {
        u"attachments": [
            {
                u"title": u"Success: False",
                u"color": u"#272727",
                u"text": u"Function: state.apply\nFunction Args: ['config.vim']\nJID: 20181227105933129338\nTotal: 4\nDuration: 27.03 secs",
                u"author_link": u"{}".format(_MINION_NAME),
                u"author_name": u"{}".format(_MINION_NAME),
                u"fallback": u"{} | Failed".format(_MINION_NAME),
                u"author_icon": _AUTHOR_ICON,
            },
            {u"color": u"good", u"title": u"Unchanged: 2"},
            {
                u"color": u"warning",
                u"fields": [
                    {
                        u"short": False,
                        u"value": u"config.vim.sls | salt vim plugin updated",
                    }
                ],
                u"title": u"Changed: 1",
            },
            {
                u"color": u"danger",
                u"fields": [
                    {u"short": False, u"value": u"config.vim.sls | macvim present"}
                ],
                u"title": u"Failed: 1",
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

    def test_generate_payload(self):
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
