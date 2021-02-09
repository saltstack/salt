# Python libs

from collections import namedtuple

# Salt libs
import salt.beacons.swapusage as swapusage
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch

# Salt testing libs
from tests.support.unit import TestCase

STUB_SWAP_USAGE = namedtuple("sswap", "total used free percent sin sout")(
    17179865088, 1674412032, 15505453056, 9.7, 1572110336, 3880046592,
)


class MemUsageBeaconTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test case for salt.beacons.swapusage
    """

    def setup_loader_modules(self):
        return {}

    def test_non_list_config(self):
        config = {}

        ret = swapusage.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for swapusage beacon must be a list.")
        )

    def test_empty_config(self):
        config = [{}]

        ret = swapusage.validate(config)

        self.assertEqual(
            ret, (False, "Configuration for swapusage beacon requires percent.")
        )

    def test_swapusage_match(self):
        with patch("psutil.swap_memory", MagicMock(return_value=STUB_SWAP_USAGE)):

            config = [{"percent": "9%"}, {"interval": 30}]

            ret = swapusage.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = swapusage.beacon(config)
            self.assertEqual(ret, [{"swapusage": 9.7}])

    def test_swapusage_nomatch(self):
        with patch("psutil.swap_memory", MagicMock(return_value=STUB_SWAP_USAGE)):

            config = [{"percent": "10%"}]

            ret = swapusage.validate(config)

            self.assertEqual(ret, (True, "Valid beacon configuration"))

            ret = swapusage.beacon(config)
            self.assertNotEqual(ret, [{"swapusage": 9.7}])
