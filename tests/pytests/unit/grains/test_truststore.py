"""
Unit tests for salt.grains.truststore.
"""

import pytest

import salt.grains.truststore as truststore_grains
import salt.utils.ostruststore as ostruststore
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def reset_injected_flag():
    with patch.object(ostruststore, "_injected", False):
        yield


def test_grain_certifi_default():
    """ca_truststore grain is 'certifi' when use_os_truststore is False."""
    with patch.object(
        truststore_grains, "__opts__", {"use_os_truststore": False}, create=True
    ):
        result = truststore_grains.ca_truststore()
    assert result == {"ca_truststore": "certifi"}


def test_grain_certifi_when_opts_empty():
    """ca_truststore grain is 'certifi' when opts are empty."""
    with patch.object(truststore_grains, "__opts__", {}, create=True):
        result = truststore_grains.ca_truststore()
    assert result == {"ca_truststore": "certifi"}


def test_grain_os_when_injected_and_enabled():
    """ca_truststore grain is 'os' when injection succeeded and option is True."""
    with patch.object(ostruststore, "_injected", True):
        with patch.object(
            truststore_grains, "__opts__", {"use_os_truststore": True}, create=True
        ):
            result = truststore_grains.ca_truststore()
    assert result == {"ca_truststore": "os"}


def test_grain_certifi_injected_but_option_off():
    """ca_truststore grain is 'certifi' even if injected when option is False."""
    with patch.object(ostruststore, "_injected", True):
        with patch.object(
            truststore_grains, "__opts__", {"use_os_truststore": False}, create=True
        ):
            result = truststore_grains.ca_truststore()
    assert result == {"ca_truststore": "certifi"}


def test_virtual_returns_name():
    assert truststore_grains.__virtual__() == "truststore"
