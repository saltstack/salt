import pytest

from tests.support.case import SyndicCase


@pytest.fixture(scope="module", autouse=True)
def salt_syndic(salt_syndic_master_factory, salt_syndic_factory):
    """
    The master of masters and the syndic, which aren't started by default
    """
    with salt_syndic_master_factory.started(), salt_syndic_factory.started():
        yield salt_syndic_factory


@pytest.mark.windows_whitelisted
class TestSyndic(SyndicCase):
    """
    Validate the syndic interface by testing the test module
    """

    @pytest.mark.slow_test
    def test_ping(self):
        """
        test.ping
        """
        self.assertTrue(self.run_function("test.ping"))

    @pytest.mark.slow_test
    def test_fib(self):
        """
        test.fib
        """
        self.assertEqual(
            self.run_function(
                "test.fib",
                ["20"],
            )[0],
            6765,
        )
