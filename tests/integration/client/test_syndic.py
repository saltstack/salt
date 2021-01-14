import pytest
from tests.support.case import SyndicCase
from tests.support.helpers import slowTest
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
@skipIf(True, "The Syndic Tests are currently broken. See #58975")
class TestSyndic(SyndicCase):
    """
    Validate the syndic interface by testing the test module
    """

    @slowTest
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @slowTest
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(self.run_function("test.fib", ["20"],)[0], 6765)
