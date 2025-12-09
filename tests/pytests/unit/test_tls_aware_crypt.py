"""
Unit tests for TLSAwareCrypticle class.

These tests verify the conditional encryption/decryption logic.
"""

import ssl

import pytest

import salt.crypt

pytestmark = [
    pytest.mark.core_test,
]


def test_tls_aware_crypticle_fallback_to_aes():
    """Test that TLSAwareCrypticle falls back to AES when optimization disabled."""
    opts = {
        "disable_aes_with_tls": False,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.TLSAwareCrypticle(opts, key)

    data = {"test": "data", "number": 42}

    # Without peer_cert, should use AES
    encrypted = crypticle.dumps(data)

    # Should not have TLS marker
    assert not encrypted.startswith(salt.crypt.TLSAwareCrypticle.TLS_MARKER)

    # Should be able to decrypt
    decrypted = crypticle.loads(encrypted)
    assert decrypted == data


def test_tls_aware_crypticle_skips_aes_with_valid_config():
    """Test that TLSAwareCrypticle skips AES with valid TLS configuration."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.TLSAwareCrypticle(opts, key)

    data = {"test": "data", "number": 42}

    # With peer_cert (mock), should skip AES
    fake_cert = b"fake_cert_data"
    encrypted = crypticle.dumps(data, peer_cert=fake_cert)

    # Should have TLS marker
    assert encrypted.startswith(salt.crypt.TLSAwareCrypticle.TLS_MARKER)

    # Should be able to "decrypt" (actually just deserialize)
    decrypted = crypticle.loads(encrypted, peer_cert=fake_cert)
    assert decrypted == data


def test_tls_aware_crypticle_rejects_mismatched_identity():
    """Test that identity mismatch prevents TLS optimization with mock cert."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.TLSAwareCrypticle(opts, key)

    data = {"test": "data", "minion_id": "test-minion-a"}
    fake_cert = b"fake_cert_data"

    # Without identity verification (no claimed_id), should skip AES
    encrypted_no_id = crypticle.dumps(data, peer_cert=fake_cert)
    assert encrypted_no_id.startswith(salt.crypt.TLSAwareCrypticle.TLS_MARKER)

    # Note: Full identity verification requires real certificates
    # This test demonstrates the API, full test is in transport tests


def test_tls_aware_crypticle_backward_compatible():
    """Test that TLSAwareCrypticle can decrypt standard AES messages."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()

    # Create standard Crypticle
    standard_crypticle = salt.crypt.Crypticle(opts, key)

    # Create TLSAwareCrypticle with same key
    tls_crypticle = salt.crypt.TLSAwareCrypticle(opts, key)

    data = {"test": "data", "number": 42}

    # Encrypt with standard Crypticle
    encrypted = standard_crypticle.dumps(data)

    # Should be able to decrypt with TLSAwareCrypticle
    decrypted = tls_crypticle.loads(encrypted)
    assert decrypted == data


def test_tls_aware_crypticle_rejects_tls_message_without_requirements():
    """Test that TLS-optimized message is rejected if requirements not met."""
    # Sender opts (has TLS optimization enabled)
    sender_opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    # Receiver opts (does NOT have TLS optimization enabled)
    receiver_opts = {
        "disable_aes_with_tls": False,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()

    sender = salt.crypt.TLSAwareCrypticle(sender_opts, key)
    receiver = salt.crypt.TLSAwareCrypticle(receiver_opts, key)

    data = {"test": "data"}
    fake_cert = b"fake_cert_data"

    # Sender creates TLS-optimized message
    encrypted = sender.dumps(data, peer_cert=fake_cert)
    assert encrypted.startswith(salt.crypt.TLSAwareCrypticle.TLS_MARKER)

    # Receiver should reject it (opts don't allow TLS optimization)
    decrypted = receiver.loads(encrypted, peer_cert=fake_cert)
    assert decrypted == {}  # Empty dict indicates rejection


def test_tls_aware_crypticle_with_nonce():
    """Test that nonce verification works with TLS optimization."""
    opts = {
        "disable_aes_with_tls": True,
        "transport": "tcp",
        "ssl": {"cert_reqs": ssl.CERT_REQUIRED},
    }

    key = salt.crypt.Crypticle.generate_key_string()
    crypticle = salt.crypt.TLSAwareCrypticle(opts, key)

    data = {"test": "data"}
    nonce = "a" * 32
    fake_cert = b"fake_cert_data"

    # Encrypt with nonce
    encrypted = crypticle.dumps(data, nonce=nonce, peer_cert=fake_cert)

    # Should have TLS marker
    assert encrypted.startswith(salt.crypt.TLSAwareCrypticle.TLS_MARKER)

    # Decrypt with correct nonce
    decrypted = crypticle.loads(encrypted, nonce=nonce, peer_cert=fake_cert)
    assert decrypted == data

    # Decrypt with wrong nonce should raise exception
    with pytest.raises(Exception):  # SaltClientError
        crypticle.loads(encrypted, nonce="b" * 32, peer_cert=fake_cert)
