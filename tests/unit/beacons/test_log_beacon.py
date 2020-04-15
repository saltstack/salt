# coding: utf-8

# Python libs
from __future__ import absolute_import

import logging

# Salt libs
import salt.beacons.log_beacon as log_beacon
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import mock_open, patch

# Salt testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


_STUB_LOG_ENTRY = (
    "Jun 29 12:58:51 hostname sshd[6536]: "
    "pam_unix(sshd:session): session opened "
    "for user username by (uid=0)\n"
)


class LogBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.log
    """

    def setup_loader_modules(self):
        return {log_beacon: {"__context__": {"log.loc": 2}, "__salt__": {}}}

    def test_non_list_config(self):
        config = {}

        ret = log_beacon.validate(config)

        self.assertEqual(ret, (False, "Configuration for log beacon must be a list."))

    def test_empty_config(self):
        config = [{}]

        ret = log_beacon.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for log beacon must contain file option.")
        )

    def test_log_match(self):
        with patch("salt.utils.files.fopen", mock_open(read_data=_STUB_LOG_ENTRY)):
            config = [
                {"file": "/var/log/auth.log", "tags": {"sshd": {"regex": ".*sshd.*"}}}
            ]

            ret = log_beacon.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            _expected_return = [
                {
                    "error": "",
                    "match": "yes",
                    "raw": _STUB_LOG_ENTRY.rstrip("\n"),
                    "tag": "sshd",
                }
            ]
            ret = log_beacon.beacon(config)
            self.assertEqual(ret, _expected_return)
