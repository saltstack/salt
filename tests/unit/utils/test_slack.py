"""
Test case for the slack utils module
"""


import logging

import salt.utils.slack as slack
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class TestSlackUtils(LoaderModuleMockMixin, TestCase):
    """
    Test case for the slack utils module
    """

    def setup_loader_modules(self):
        return {
            slack: {
                "__opts__": {
                    "vault": {
                        "url": "http://127.0.0.1",
                        "auth": {
                            "token": "test",
                            "method": "token",
                            "uses": 15,
                            "ttl": 500,
                        },
                    },
                },
            }
        }

    def test_query(self):
        """
        Test case for the query function in the slack utils module
        """

        function = "message"
        api_key = "xoxp-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxxxx"
        args = None
        method = "POST"
        header_dict = {"Content-Type": "application/x-www-form-urlen coded"}
        data = "channel=%23general&username=Slack+User&as_user=Slack+User&text=%60%60%60id%3A+minion%0D%0Afunction%3A+test.ping%0D%0Afunction+args%3A+%5B%5D%0D%0Ajid%3A+20201017004822956482%0D%0Areturn%3A+true%0A%0D%0A%60%60%60"
        opts = None

        mock_result = {
            "body": '{"ok": false, "error": "token_revoked"}',
            "status": 200,
            "dict": {"ok": False, "error": "token_revoked"},
        }
        mock = MagicMock(return_value=mock_result)
        with patch("salt.utils.http.query", mock):
            expected = {"message": "token_revoked", "res": False}
            ret = slack.query(function, api_key, args, method, header_dict, data, opts)
            self.assertEqual(ret, expected)

        mock_result = {
            "status": 0,
            "error": "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1076)",
        }
        mock = MagicMock(return_value=mock_result)
        with patch("salt.utils.http.query", mock):
            expected = {"message": "invalid_auth", "res": False}
            ret = slack.query(function, api_key, args, method, header_dict, data, opts)
            self.assertEqual(ret, expected)

        mock_result = {"status": 0, "dict": {}}
        mock = MagicMock(return_value=mock_result)
        with patch("salt.utils.http.query", mock):
            expected = {"message": "Unknown response", "res": False}
            ret = slack.query(function, api_key, args, method, header_dict, data, opts)
            self.assertEqual(ret, expected)
