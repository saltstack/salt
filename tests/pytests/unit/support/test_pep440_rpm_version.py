"""
Unit tests for :py:func:`tests.support.pkg.pep440_version_to_rpm_nevra_version`.
"""

import pytest

from tests.support.pkg import pep440_version_to_rpm_nevra_version


@pytest.mark.parametrize(
    ("pep440", "expected"),
    [
        ("3008.0rc1", "3008.0~rc1"),
        ("3007.13", "3007.13"),
        ("3008.0rc1+9.g1490eb2716", "3008.0~rc1+9.g1490eb2716"),
        ("3008.0~rc1", "3008.0~rc1"),
        ("3008.0~rc1+9.g1490eb2716", "3008.0~rc1+9.g1490eb2716"),
        ("3008.0.dev3", "3008.0~dev3"),
        ("1.0a1", "1.0~a1"),
        ("3008.0rc1.post1", "3008.0~rc1.post1"),
    ],
)
def test_pep440_version_to_rpm_nevra_version(pep440, expected):
    assert pep440_version_to_rpm_nevra_version(pep440) == expected
