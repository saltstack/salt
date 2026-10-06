"""
Unit tests for salt.utils.ostruststore.
"""

import pytest

import salt.utils.ostruststore as ostruststore
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def reset_injected_flag():
    """Reset the module-level _injected flag before and after every test."""
    with patch.object(ostruststore, "_injected", False):
        yield


# ---------------------------------------------------------------------------
# apply_if_enabled
# ---------------------------------------------------------------------------


def test_apply_if_enabled_disabled_by_default():
    """When use_os_truststore is absent, injection is skipped."""
    ostruststore.apply_if_enabled({})
    assert ostruststore.is_injected() is False


def test_apply_if_enabled_explicit_false():
    """When use_os_truststore is False, injection is skipped."""
    ostruststore.apply_if_enabled({"use_os_truststore": False})
    assert ostruststore.is_injected() is False


def test_apply_if_enabled_missing_package(caplog):
    """
    When use_os_truststore is True but truststore is not installed,
    a warning is logged and injection is skipped.
    """
    import logging

    with patch.object(ostruststore, "HAS_TRUSTSTORE", False):
        with caplog.at_level(logging.WARNING, logger="salt.utils.ostruststore"):
            ostruststore.apply_if_enabled({"use_os_truststore": True})

    assert ostruststore.is_injected() is False
    assert "truststore" in caplog.text


def test_apply_if_enabled_success():
    """When the package is available, inject_into_ssl() is called once."""
    mock_truststore = MagicMock()

    with patch.object(ostruststore, "HAS_TRUSTSTORE", True):
        with patch.object(ostruststore, "_truststore", mock_truststore):
            ostruststore.apply_if_enabled({"use_os_truststore": True})

    mock_truststore.inject_into_ssl.assert_called_once()
    assert ostruststore.is_injected() is True


def test_apply_if_enabled_idempotent():
    """Calling apply_if_enabled twice only injects once."""
    mock_truststore = MagicMock()

    with patch.object(ostruststore, "HAS_TRUSTSTORE", True):
        with patch.object(ostruststore, "_truststore", mock_truststore):
            ostruststore.apply_if_enabled({"use_os_truststore": True})
            ostruststore.apply_if_enabled({"use_os_truststore": True})

    mock_truststore.inject_into_ssl.assert_called_once()


# ---------------------------------------------------------------------------
# is_injected
# ---------------------------------------------------------------------------


def test_is_injected_default_false():
    assert ostruststore.is_injected() is False


def test_is_injected_true_after_apply():
    mock_truststore = MagicMock()

    with patch.object(ostruststore, "HAS_TRUSTSTORE", True):
        with patch.object(ostruststore, "_truststore", mock_truststore):
            ostruststore.apply_if_enabled({"use_os_truststore": True})

    assert ostruststore.is_injected() is True


# ---------------------------------------------------------------------------
# active_store_name
# ---------------------------------------------------------------------------


def test_active_store_name_certifi_when_not_injected():
    assert ostruststore.active_store_name({"use_os_truststore": True}) == "certifi"


def test_active_store_name_certifi_when_disabled():
    with patch.object(ostruststore, "_injected", True):
        assert ostruststore.active_store_name({"use_os_truststore": False}) == "certifi"


def test_active_store_name_os_when_injected_and_enabled():
    with patch.object(ostruststore, "_injected", True):
        assert ostruststore.active_store_name({"use_os_truststore": True}) == "os"


def test_active_store_name_certifi_default_opts():
    assert ostruststore.active_store_name({}) == "certifi"
