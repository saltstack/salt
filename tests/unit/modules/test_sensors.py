"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.sensors as sensors
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SensorTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.sensors
    """

    def setup_loader_modules(self):
        return {sensors: {}}

    def test_sense(self):
        """
        Test to gather lm-sensors data from a given chip
        """
        with patch.dict(
            sensors.__salt__, {"cmd.run": MagicMock(return_value="A:a B:b C:c D:d")}
        ):
            self.assertDictEqual(sensors.sense("chip"), {"A": "a B"})
