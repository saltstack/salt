"""
Unit tests for SSL/TLS certificate identity verification.

These tests verify that certificates contain the correct identity information
(CN and SAN) that can be matched against minion IDs.
"""

import pytest

import salt.utils.files

pytestmark = [
    pytest.mark.core_test,
]


def test_minion_cert_has_id_in_cn(ssl_minion_a_cert_key):
    """
    Test that minion certificate has minion ID in Common Name.

    This is critical for the TLS optimization feature which requires
    matching the certificate identity to the minion ID.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Get Common Name from subject
    cn = None
    for attr in cert.subject:
        if attr.oid == x509.oid.NameOID.COMMON_NAME:
            cn = attr.value
            break

    assert cn == "test-minion-a"


def test_minion_cert_has_id_in_san(ssl_minion_a_cert_key):
    """
    Test that minion certificate has minion ID in Subject Alternative Name.

    SAN is the preferred location for hostname/identity verification in modern TLS.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Get SAN extension
    san_ext = cert.extensions.get_extension_for_oid(
        x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
    )

    # Extract DNS names
    dns_names = [name.value for name in san_ext.value]

    # Verify minion ID is in SAN
    assert "test-minion-a" in dns_names


def test_different_minions_have_different_certs(
    ssl_minion_a_cert_key, ssl_minion_b_cert_key
):
    """
    Test that different minion IDs get different certificates with different identities.

    This ensures that minion A cannot use minion B's certificate to impersonate it.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    cert_a_path, _ = ssl_minion_a_cert_key
    cert_b_path, _ = ssl_minion_b_cert_key

    # Load both certificates
    with salt.utils.files.fopen(cert_a_path, "rb") as f:
        cert_a = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(cert_b_path, "rb") as f:
        cert_b = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Verify subjects are different
    assert cert_a.subject != cert_b.subject

    # Get CNs
    cn_a = None
    cn_b = None
    for attr in cert_a.subject:
        if attr.oid == x509.oid.NameOID.COMMON_NAME:
            cn_a = attr.value
    for attr in cert_b.subject:
        if attr.oid == x509.oid.NameOID.COMMON_NAME:
            cn_b = attr.value

    assert cn_a == "test-minion-a"
    assert cn_b == "test-minion-b"
    assert cn_a != cn_b


def test_extract_identity_from_cert(ssl_minion_a_cert_key):
    """
    Test a helper function pattern for extracting identity from certificate.

    This demonstrates how the optimization feature should extract and verify
    the minion ID from a peer certificate.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    def extract_identity_from_cert(cert):
        """
        Extract identity from a certificate.

        Returns the Common Name and all SAN DNS names.
        """
        # Get CN
        cn = None
        for attr in cert.subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                cn = attr.value
                break

        # Get SAN DNS names
        san_names = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            san_names = [name.value for name in san_ext.value]
        except x509.ExtensionNotFound:
            pass

        return cn, san_names

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    cn, san_names = extract_identity_from_cert(cert)

    assert cn == "test-minion-a"
    assert "test-minion-a" in san_names


def test_verify_identity_matches_minion_id(ssl_minion_a_cert_key):
    """
    Test identity verification logic that should be used in the optimization.

    The TLS optimization should only skip AES encryption when:
    1. TLS is active with valid certs
    2. cert_reqs is CERT_REQUIRED
    3. The peer certificate identity matches the expected minion ID
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    def verify_cert_identity(cert, expected_id):
        """
        Verify that certificate identity matches expected minion ID.

        Checks both CN and SAN for a match.
        """
        # Check CN
        for attr in cert.subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                if attr.value == expected_id:
                    return True

        # Check SAN
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            san_names = [name.value for name in san_ext.value]
            if expected_id in san_names:
                return True
        except x509.ExtensionNotFound:
            pass

        return False

    cert_path, _ = ssl_minion_a_cert_key

    # Load certificate
    with salt.utils.files.fopen(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Test matching ID
    assert verify_cert_identity(cert, "test-minion-a") is True

    # Test non-matching ID
    assert verify_cert_identity(cert, "test-minion-b") is False
    assert verify_cert_identity(cert, "test-minion-c") is False
    assert verify_cert_identity(cert, "wrong-id") is False


def test_verify_identity_mismatch_prevents_optimization(
    ssl_minion_a_cert_key, ssl_minion_b_cert_key
):
    """
    Test that identity mismatch should prevent the TLS optimization.

    Even if minion A has a valid certificate, if it claims to be minion B,
    the optimization should NOT be used (and AES should still be applied).
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    def should_skip_aes_with_tls(cert, claimed_minion_id):
        """
        Determine if AES encryption can be skipped.

        Returns True only if certificate identity matches claimed ID.
        """
        # Check CN
        for attr in cert.subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                if attr.value == claimed_minion_id:
                    return True

        # Check SAN
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            san_names = [name.value for name in san_ext.value]
            if claimed_minion_id in san_names:
                return True
        except x509.ExtensionNotFound:
            pass

        return False

    # Load minion A's certificate
    cert_a_path, _ = ssl_minion_a_cert_key
    with salt.utils.files.fopen(cert_a_path, "rb") as f:
        cert_a = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Minion A claiming to be "test-minion-a" - should allow optimization
    assert should_skip_aes_with_tls(cert_a, "test-minion-a") is True

    # Minion A claiming to be "test-minion-b" - should NOT allow optimization
    assert should_skip_aes_with_tls(cert_a, "test-minion-b") is False

    # Minion A claiming to be something else - should NOT allow optimization
    assert should_skip_aes_with_tls(cert_a, "malicious-minion") is False
