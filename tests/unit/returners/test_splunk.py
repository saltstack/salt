"""
tests.unit.returners.test_splunk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the splunk returner
"""

import json
import logging

import salt.modules.config as config
import salt.returners.splunk as splunk
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class SplunkReturnerTest(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        opts = {
            "splunk_http_forwarder": {
                "token": "TheToken",
                "indexer": "the.splunk.domain",
                "index": "TheIndex",
                "sourcetype": "TheSourceType",
            }
        }
        return {
            splunk: {"__opts__": opts, "__salt__": {"config.get": config.get}},
            config: {"__opts__": opts},
        }

    def test_verify_ssl_defaults_to_true(self):
        payload = {"some": "payload"}
        requests_post = MagicMock()
        ts = 1234565789
        host = "TheHostName"
        data = {
            "time": str(ts),
            "index": "TheIndex",
            "sourcetype": "TheSourceType",
            "event": payload,
            "host": host,
        }
        with patch(
            "salt.returners.splunk.time.time", MagicMock(return_value=ts)
        ), patch(
            "salt.returners.splunk.socket.gethostname", MagicMock(return_value=host)
        ), patch(
            "requests.post", requests_post
        ):
            splunk.returner(payload.copy())
        assert json.loads(requests_post.call_args_list[0][1]["data"]) == data
        assert requests_post.call_args_list[0][1]["verify"]
        assert requests_post.call_args_list[0][1]["headers"] == {
            "Authorization": "Splunk TheToken"
        }
        assert (
            requests_post.call_args_list[0][0][0]
            == "https://the.splunk.domain:8088/services/collector/event"
        )

    def test_verify_ssl(self):
        payload = {"some": "payload"}
        verify_ssl_values = [True, False, None]
        payload = {"some": "payload"}
        ts = 1234565789
        host = "TheHostName"
        data = {
            "time": str(ts),
            "index": "TheIndex",
            "sourcetype": "TheSourceType",
            "event": payload,
            "host": host,
        }
        for verify_ssl in verify_ssl_values:
            requests_post = MagicMock()
            with patch(
                "salt.returners.splunk.time.time", MagicMock(return_value=ts)
            ), patch(
                "salt.returners.splunk.socket.gethostname", MagicMock(return_value=host)
            ), patch(
                "requests.post", requests_post
            ), patch.dict(
                splunk.__opts__["splunk_http_forwarder"], verify_ssl=verify_ssl
            ):
                splunk.returner(payload.copy())
                assert json.loads(requests_post.call_args_list[0][1]["data"]) == data
                assert requests_post.call_args_list[0][1]["verify"] == verify_ssl
                assert requests_post.call_args_list[0][1]["headers"] == {
                    "Authorization": "Splunk TheToken"
                }
                assert (
                    requests_post.call_args_list[0][0][0]
                    == "https://the.splunk.domain:8088/services/collector/event"
                )
