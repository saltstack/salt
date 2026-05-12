"""
Test the custom grains
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.slow_test,
]


def test_grains_passed_to_custom_grain(salt_call_cli):
    """
    test if current grains are passed to grains module functions that have a grains argument
    """
    ret = salt_call_cli.run("grains.item", "custom_grain_test")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["custom_grain_test"] == "itworked"
