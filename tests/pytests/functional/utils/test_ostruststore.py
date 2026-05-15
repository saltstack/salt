"""
Functional tests for salt.utils.ostruststore.

These tests verify that, when truststore is actually available in the test
environment, the injection genuinely patches ssl.SSLContext.  They are
skipped when the package is not installed.
"""

import ssl

import pytest

import salt.utils.ostruststore as ostruststore
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skipif(
        not ostruststore.HAS_TRUSTSTORE,
        reason="truststore is not installed; skipping OS truststore functional tests",
    ),
]


@pytest.fixture(autouse=True)
def reset_injected_flag():
    """Reset injection state and ssl.SSLContext after each test."""
    original_ssl_context = ssl.SSLContext
    with patch.object(ostruststore, "_injected", False):
        yield
    ssl.SSLContext = original_ssl_context


def test_injection_patches_ssl_context():
    """
    After apply_if_enabled with use_os_truststore=True, ssl.create_default_context()
    should return a truststore-aware context.  inject_into_ssl() replaces
    ssl.SSLContext in-place, so we must capture the original class reference
    before injection to have something to compare against.
    """
    original_class = ssl.SSLContext  # capture before injection replaces it
    ostruststore.apply_if_enabled({"use_os_truststore": True})
    assert ostruststore.is_injected() is True
    ctx = ssl.create_default_context()
    assert (
        type(ctx) is not original_class
    ), "Expected a truststore-patched context, got plain ssl.SSLContext"


def test_injection_is_idempotent():
    """Calling apply_if_enabled twice does not raise and only patches once."""
    ostruststore.apply_if_enabled({"use_os_truststore": True})
    context_class_after_first = type(ssl.create_default_context())
    ostruststore.apply_if_enabled({"use_os_truststore": True})
    context_class_after_second = type(ssl.create_default_context())
    assert context_class_after_first is context_class_after_second


def test_no_injection_when_disabled():
    """When use_os_truststore is False, ssl.SSLContext is not patched."""
    original = ssl.SSLContext
    ostruststore.apply_if_enabled({"use_os_truststore": False})
    assert ssl.SSLContext is original
    assert ostruststore.is_injected() is False


def test_active_store_name_os_after_injection():
    """active_store_name returns 'os' after a successful injection."""
    ostruststore.apply_if_enabled({"use_os_truststore": True})
    assert ostruststore.active_store_name({"use_os_truststore": True}) == "os"


def test_active_store_name_certifi_when_disabled():
    """active_store_name returns 'certifi' when injection was not requested."""
    ostruststore.apply_if_enabled({"use_os_truststore": False})
    assert ostruststore.active_store_name({"use_os_truststore": False}) == "certifi"
