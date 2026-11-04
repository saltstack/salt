"""Tests for loading the supported X.509 state module."""

import pytest

import salt.states.x509_v2 as x509
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {x509: {"__opts__": {}}}


@pytest.mark.parametrize("features", [{}, {"x509_v2": True}, {"x509_v2": False}])
def test_virtual_ignores_removed_implementation_selector(features):
    """The legacy feature flag cannot disable the only X.509 implementation."""
    with patch.dict(x509.__opts__, {"features": features}), patch.object(
        x509, "HAS_CRYPTOGRAPHY", True
    ):
        assert x509.__virtual__() == "x509"


def test_virtual_requires_cryptography():
    """The remaining implementation still requires cryptography."""
    with patch.object(x509, "HAS_CRYPTOGRAPHY", False):
        assert x509.__virtual__() == (False, "Could not load cryptography")
