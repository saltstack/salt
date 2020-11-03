# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.haproxy as haproxy
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase


class HAProxyBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.haproxy
    """

    def setup_loader_modules(self):
        return {haproxy: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        config = {}

        ret = haproxy.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for haproxy beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = haproxy.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for haproxy beacon requires backends.")
        )

    def test_no_servers(self):
        config = [{"backends": {"www-backend": {"threshold": 45}}}]
        ret = haproxy.validate(config)

        self.assertEqual(ret, (False, "Backends for haproxy beacon require servers."))

    def test_threshold_reached(self):
        config = [{"backends": {"www-backend": {"threshold": 45, "servers": ["web1"]}}}]
        ret = haproxy.validate(config)

        self.assertEqual(ret, (True, "Valid beacon configuration"))

        mock = MagicMock(return_value=46)
        with patch.dict(haproxy.__salt__, {"haproxy.get_sessions": mock}):
            ret = haproxy.beacon(config)
            self.assertEqual(ret, [{"threshold": 45, "scur": 46, "server": "web1"}])

    def test_threshold_not_reached(self):
        config = [
            {"backends": {"www-backend": {"threshold": 100, "servers": ["web1"]}}}
        ]
        ret = haproxy.validate(config)

        self.assertEqual(ret, (True, "Valid beacon configuration"))

        mock = MagicMock(return_value=50)
        with patch.dict(haproxy.__salt__, {"haproxy.get_sessions": mock}):
            ret = haproxy.beacon(config)
            self.assertEqual(ret, [])
