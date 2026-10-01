"""
Functional tests for the win_license execution module.

Read-only tests (info, licensed, license_status, get_kms_host, get_kms_port) run
against the OS product key already installed on the test system — no key required.

KMS round-trip tests set a test value, verify it, then restore the original value.
These require no product key and do not affect licensing status.

Tests that install, uninstall, or activate product keys are not included here
as they require a valid product key that cannot be committed to the test suite.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def license(modules):
    return modules.license


@pytest.fixture
def restore_kms_host(license):
    """Save and restore the global KMS host around a test."""
    original = license.get_kms_host()
    yield
    if original:
        license.set_kms_host(original)
    else:
        license.clear_kms_host()


@pytest.fixture
def restore_kms_port(license):
    """Save and restore the global KMS port around a test."""
    original = license.get_kms_port()
    yield
    if original:
        license.set_kms_port(original)
    else:
        license.clear_kms_port()


# ---------------------------------------------------------------------------
# Read-only tests — query existing OS license, no modifications
# ---------------------------------------------------------------------------


def test_info_returns_dict(license):
    """
    info() should return a dict with the expected keys for a licensed Windows machine.
    """
    result = license.info()
    assert isinstance(result, dict)
    assert "name" in result
    assert "description" in result
    assert "partial_key" in result
    assert "licensed" in result
    assert "status" in result
    assert "status_name" in result


def test_info_partial_key_is_five_chars(license):
    """
    The partial_key returned by info() should be exactly 5 characters.
    """
    result = license.info()
    assert result is not None
    assert len(result["partial_key"]) == 5


def test_licensed_returns_bool(license):
    """
    licensed() should return a bool.
    """
    result = license.licensed()
    assert isinstance(result, bool)


def test_license_status_returns_int(license):
    """
    license_status() should return an int in the valid range 0-6.
    """
    result = license.license_status()
    assert isinstance(result, int)
    assert 0 <= result <= 6


def test_license_status_matches_licensed(license):
    """
    licensed() should be True if and only if license_status() == 1.
    """
    assert license.licensed() == (license.license_status() == 1)


def test_get_kms_host_returns_string_or_none(license):
    """
    get_kms_host() should return a non-empty string or None.
    """
    result = license.get_kms_host()
    assert result is None or (isinstance(result, str) and result)


def test_get_kms_port_returns_int_or_none(license):
    """
    get_kms_port() should return a positive int or None.
    """
    result = license.get_kms_port()
    assert result is None or (isinstance(result, int) and result > 0)


# ---------------------------------------------------------------------------
# KMS round-trip tests — set, verify, restore
# ---------------------------------------------------------------------------


@pytest.mark.destructive_test
def test_set_and_clear_kms_host(license, restore_kms_host):
    """
    set_kms_host() should persist and get_kms_host() should return it.
    clear_kms_host() should remove it.
    """
    license.set_kms_host("kms.test.example.com")
    assert license.get_kms_host() == "kms.test.example.com"

    license.clear_kms_host()
    assert license.get_kms_host() is None


@pytest.mark.destructive_test
def test_set_and_clear_kms_port(license, restore_kms_port):
    """
    set_kms_port() should persist and get_kms_port() should return it.
    clear_kms_port() should remove it.
    """
    license.set_kms_port(2500)
    assert license.get_kms_port() == 2500

    license.clear_kms_port()
    assert license.get_kms_port() is None


@pytest.mark.destructive_test
def test_set_kms_host_replaces_existing(license, restore_kms_host):
    """
    Calling set_kms_host() twice should replace the first value.
    """
    license.set_kms_host("kms-first.example.com")
    assert license.get_kms_host() == "kms-first.example.com"

    license.set_kms_host("kms-second.example.com")
    assert license.get_kms_host() == "kms-second.example.com"


@pytest.mark.destructive_test
def test_set_kms_host_and_port_independently(
    license, restore_kms_host, restore_kms_port
):
    """
    KMS host and port are independent — setting one does not clear the other.
    """
    license.set_kms_host("kms.test.example.com")
    license.set_kms_port(2500)

    assert license.get_kms_host() == "kms.test.example.com"
    assert license.get_kms_port() == 2500

    license.clear_kms_host()
    assert license.get_kms_host() is None
    assert license.get_kms_port() == 2500
