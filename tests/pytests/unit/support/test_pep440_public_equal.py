"""Unit tests for ``pep440_public_equal`` in ``tests.support.pkg``."""

from tests.support.pkg import pep440_public_equal


def test_pep440_public_equal_ignores_local():
    assert pep440_public_equal("3008.0rc1", "3008.0rc1+13.gabcdef")
    assert pep440_public_equal("3008.0rc1+13.gabcdef", "3008.0rc1")


def test_pep440_public_equal_distinct_prerelease():
    assert not pep440_public_equal("3008.0rc1", "3008.0")
