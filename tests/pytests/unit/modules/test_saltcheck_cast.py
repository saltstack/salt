"""
Unit tests for the casting of the expected value in the saltcheck module
"""

import pytest

import salt.modules.saltcheck as saltcheck


@pytest.mark.parametrize(
    "expected,returned,result",
    [
        ("False", False, False),  # the text "False" would be True as a bool
        ("False", True, False),
        ("True", True, True),
        ("", False, False),
        (5, "x", "5"),
        ("3", 1, 3),
        ("abc", 1, "abc"),  # cannot be cast: stays as it is
        ("False", "text", "False"),  # only a bool gets the special case
        ("False", 0, "False"),  # an int is not a bool: int("False") fails, so it stays
        ("expected", None, "expected"),  # nothing returned: not cast
    ],
)
def test_cast_expected_to_returned_type(expected, returned, result):
    ret = saltcheck.SaltCheck._cast_expected_to_returned_type(expected, returned)
    assert ret == result
    assert type(ret) is type(result)
