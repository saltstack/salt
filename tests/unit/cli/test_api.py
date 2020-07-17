from salt.cli.api import SaltAPI
from tests.support.unit import TestCase
import sys
from tests.support.mock import patch
from tests.support.helpers import slowTest


class SaltAPITestCase(TestCase):
    @slowTest
    def test_start_shutdown(self):
        api = SaltAPI()
        try:
            with patch.object(sys, "argv", [sys.argv[0]]):
                api.start()
        finally:
            self.assertRaises(SystemExit, api.shutdown)
