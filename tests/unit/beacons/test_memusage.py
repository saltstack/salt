# coding: utf-8

# Python libs
from __future__ import absolute_import

from collections import namedtuple

# Salt libs
import salt.beacons.memusage as memusage
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

STUB_MEMORY_USAGE = namedtuple(
    "vmem", "total available percent used free active inactive buffers cached shared"
)(
    15722012672,
    9329594368,
    40.7,
    5137018880,
    4678086656,
    6991405056,
    2078953472,
    1156378624,
    4750528512,
    898908160,
)


class MemUsageBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.memusage
    """

    def setup_loader_modules(self):
        return {}

    def test_non_list_config(self):
        config = {}

        ret = memusage.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for memusage beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = memusage.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for memusage beacon requires percent.")
        )

    def test_memusage_match(self):
        with patch("psutil.virtual_memory", MagicMock(return_value=STUB_MEMORY_USAGE)):

            config = [{"percent": "40%"}, {"interval": 30}]

            ret = memusage.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = memusage.beacon(config)
            self.assertEqual(ret, [{"memusage": 40.7}])

    def test_memusage_nomatch(self):
        with patch("psutil.virtual_memory", MagicMock(return_value=STUB_MEMORY_USAGE)):

            config = [{"percent": "70%"}]

            ret = memusage.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = memusage.beacon(config)
            self.assertNotEqual(ret, [{"memusage": 50}])
