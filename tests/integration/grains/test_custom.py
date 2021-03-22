"""
Test the core grains
"""


import pytest
from tests.support.case import ModuleCase


@pytest.mark.windows_whitelisted
class TestGrainsCore(ModuleCase):
    """
    Test the core grains grains
    """

    @pytest.mark.slow_test
    def test_grains_passed_to_custom_grain(self):
        """
        test if current grains are passed to grains module functions that have a grains argument
        """
        self.assertEqual(
            self.run_function("grains.get", ["custom_grain_test"]), "itworked"
        )
