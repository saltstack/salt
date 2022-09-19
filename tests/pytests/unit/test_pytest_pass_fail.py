"""
    tests.unit.test_pytest_pass_fail
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Some tests to make sure our pytest usage doesn't break regular pytest behviour
"""

import pytest


@pytest.mark.xfail(
    strict=True,
    reason="This test should always fail. If it passes, we messed up pytest",
)
def test_should_always_fail():
    assert False


def test_should_always_pass():
    assert True
