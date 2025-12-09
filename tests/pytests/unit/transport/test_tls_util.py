"""
Unit tests for TLS utility functions.

These tests verify the logic for determining when AES encryption can be
safely skipped in favor of TLS encryption.
"""

import ssl

import pytest

import salt.transport.tls_util
import salt.utils.files

pytestmark = [
    pytest.mark.core_test,
]


def test_can_skip_aes_requires_opt_in():
    """Test that optimization requires explicit opt-in."""
    opts = {
        "transport": "tcp",
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    # Without disable_aes_with_tls, should return False
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False

    # With disable_aes_with_tls=False, should return False
    opts["disable_aes_with_tls"] = False
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False


def test_can_skip_aes_requires_ssl_config():
    """Test that optimization requires SSL configuration."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
    }

    # Without ssl config
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False

    # With ssl=None
    opts["ssl"] = None
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False


def test_can_skip_aes_requires_cert_required():
    """Test that optimization requires CERT_REQUIRED."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {},
    }

    # Without cert_reqs
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False

    # With CERT_NONE
    opts["ssl"]["cert_reqs"] = ssl.CERT_NONE
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False

    # With CERT_OPTIONAL
    opts["ssl"]["cert_reqs"] = ssl.CERT_OPTIONAL
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False


def test_can_skip_aes_requires_tls_transport():
    """Test that optimization only works with TCP or WS transports."""
    base_opts = {
        "disable_aes_with_tls": True,
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    # ZeroMQ should not allow skipping
    opts = base_opts.copy()
    opts["transport"] = "zeromq"
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False

    # Default transport (zeromq) should not allow skipping
    opts = base_opts.copy()
    # No transport specified defaults to zeromq
    assert salt.transport.tls_util.can_skip_aes_encryption(opts) is False


def test_can_skip_aes_requires_peer_cert():
    """Test that optimization requires peer certificate."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    # Without peer_cert
    assert (
        salt.transport.tls_util.can_skip_aes_encryption(opts, peer_cert=None) is False
    )


def test_can_skip_aes_with_valid_config_tcp():
    """Test that optimization works with valid TCP configuration."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    # With valid peer_cert (mock)
    fake_cert = b"fake_cert_data"
    assert (
        salt.transport.tls_util.can_skip_aes_encryption(opts, peer_cert=fake_cert)
        is True
    )


def test_can_skip_aes_with_valid_config_ws():
    """Test that optimization works with valid WebSocket configuration."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "ws",
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    # With valid peer_cert (mock)
    fake_cert = b"fake_cert_data"
    assert (
        salt.transport.tls_util.can_skip_aes_encryption(opts, peer_cert=fake_cert)
        is True
    )


def test_verify_cert_identity_with_matching_cn(ssl_minion_a_cert_key):
    """Test certificate identity verification with matching CN."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate and convert to DER
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    cert_der = cert.public_bytes(encoding=serialization.Encoding.DER)

    # Should match
    assert (
        salt.transport.tls_util.verify_cert_identity(cert_der, "test-minion-a") is True
    )

    # Should not match
    assert (
        salt.transport.tls_util.verify_cert_identity(cert_der, "test-minion-b") is False
    )
    assert salt.transport.tls_util.verify_cert_identity(cert_der, "wrong-id") is False


def test_verify_cert_identity_with_matching_san(ssl_minion_a_cert_key):
    """Test certificate identity verification with matching SAN."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate and convert to DER
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    cert_der = cert.public_bytes(encoding=serialization.Encoding.DER)

    # Should match on SAN (test-minion-a is in SAN)
    assert (
        salt.transport.tls_util.verify_cert_identity(cert_der, "test-minion-a") is True
    )


def test_can_skip_aes_requires_identity_match(ssl_minion_a_cert_key):
    """Test that identity mismatch prevents optimization."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        pytest.skip("cryptography library not available")

    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {
            "cert_reqs": ssl.CERT_REQUIRED,
        },
    }

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate and convert to DER
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    cert_der = cert.public_bytes(encoding=serialization.Encoding.DER)

    # Should allow skipping with matching ID
    assert (
        salt.transport.tls_util.can_skip_aes_encryption(
            opts, peer_cert=cert_der, claimed_id="test-minion-a"
        )
        is True
    )

    # Should NOT allow skipping with mismatched ID
    assert (
        salt.transport.tls_util.can_skip_aes_encryption(
            opts, peer_cert=cert_der, claimed_id="test-minion-b"
        )
        is False
    )


def test_get_cert_identity(ssl_minion_a_cert_key):
    """Test extracting identity from certificate."""
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate and convert to DER
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    cert_der = cert.public_bytes(encoding=serialization.Encoding.DER)

    cn, san_names = salt.transport.tls_util.get_cert_identity(cert_der)

    assert cn == "test-minion-a"
    assert "test-minion-a" in san_names
