# coding: utf-8

# Python libs
from __future__ import absolute_import

from collections import namedtuple

# Salt libs
import salt.beacons.service as service_beacon
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

PATCH_OPTS = dict(autospec=True, spec_set=True)

FakeProcess = namedtuple("Process", "cmdline pid")


class ServiceBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.service
    """

    def setup_loader_modules(self):
        return {service_beacon: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        config = {}

        ret = service_beacon.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for service beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = service_beacon.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for service beacon requires services.")
        )

    def test_service_running(self):
        with patch.dict(
            service_beacon.__salt__, {"service.status": MagicMock(return_value=True)}
        ):
            config = [{"services": {"salt-master": {}}}]

            ret = service_beacon.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = service_beacon.beacon(config)
            self.assertEqual(
                ret,
                [
                    {
                        "service_name": "salt-master",
                        "tag": "salt-master",
                        "salt-master": {"running": True},
                    }
                ],
            )

    def test_service_not_running(self):
        with patch.dict(
            service_beacon.__salt__, {"service.status": MagicMock(return_value=False)}
        ):
            config = [{"services": {"salt-master": {}}}]

            ret = service_beacon.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = service_beacon.beacon(config)
            self.assertEqual(
                ret,
                [
                    {
                        "service_name": "salt-master",
                        "tag": "salt-master",
                        "salt-master": {"running": False},
                    }
                ],
            )
