# -*- coding: utf-8 -*-
"""
tests.unit.returners.test_splunk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the splunk returner
"""
from __future__ import absolute_import, print_function, unicode_literals

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
        requests_post.assert_called_with(
            "https://the.splunk.domain:8088/services/collector/event",
            data=json.dumps(data),
            headers={"Authorization": "Splunk TheToken"},
            verify=True,
        )

    def test_verify_ssl(self):
        payload = {"some": "payload"}
        verify_ssl_values = [True, False, None]
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
        for verify_ssl in verify_ssl_values:
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
            requests_post.assert_called_with(
                "https://the.splunk.domain:8088/services/collector/event",
                data=json.dumps(data),
                headers={"Authorization": "Splunk TheToken"},
                verify=verify_ssl,
            )
