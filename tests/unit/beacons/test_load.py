# coding: utf-8

# Python libs
from __future__ import absolute_import

import logging

# Salt libs
import salt.beacons.load as load
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


class LoadBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.load
    """

    def setup_loader_modules(self):
        return {load: {"__context__": {}, "__salt__": {}}}

    def test_non_list_config(self):
        config = {}

        ret = load.validate(config)

        self.assertEqual(ret, (False, "Configuration for load beacon must be a list."))

    def test_empty_config(self):
        config = [{}]

        ret = load.validate(config)

        self.assertEqual(
            ret, (False, "Averages configuration is required for load beacon.")
        )

    @skipIf(salt.utils.platform.is_windows(), "os.getloadavg not available on Windows")
    def test_load_match(self):
        with patch("os.getloadavg", MagicMock(return_value=(1.82, 1.84, 1.56))):
            config = [
                {
                    "averages": {"1m": [0.0, 2.0], "5m": [0.0, 1.5], "15m": [0.0, 1.0]},
                    "emitatstartup": True,
                    "onchangeonly": False,
                }
            ]

            ret = load.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            _expected_return = [{"1m": 1.82, "5m": 1.84, "15m": 1.56}]
            ret = load.beacon(config)
            self.assertEqual(ret, _expected_return)
