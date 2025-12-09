"""
SSL/TLS certificate fixtures for transport testing.

This module provides pytest fixtures for generating CA, server, and client
certificates for testing Salt transports with SSL/TLS enabled.
"""

import datetime
import os

import pytest

import salt.utils.files

try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def _generate_private_key():
    """Generate an RSA private key."""
    return rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )


def _generate_ca_certificate(private_key, common_name="Test CA"):
    """
    Generate a self-signed CA certificate.

    Args:
        private_key: RSA private key for the CA
        common_name: Common name for the CA certificate

    Returns:
        x509.Certificate: The CA certificate
    """
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Salt Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    return cert


def _generate_certificate(
    private_key, ca_cert, ca_key, common_name, san_dns_names=None
):
    """
    Generate a certificate signed by the CA.

    Args:
        private_key: RSA private key for the certificate
        ca_cert: CA certificate to sign with
        ca_key: CA private key to sign with
        common_name: Common name for the certificate
        san_dns_names: List of DNS names for Subject Alternative Name extension

    Returns:
        x509.Certificate: The signed certificate
    """
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Salt Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
    )

    # Add Subject Alternative Name if DNS names provided
    if san_dns_names:
        san = x509.SubjectAlternativeName(
            [x509.DNSName(name) for name in san_dns_names]
        )
        builder = builder.add_extension(san, critical=False)

    cert = builder.sign(ca_key, hashes.SHA256(), default_backend())

    return cert


def _write_private_key(key, path):
    """Write private key to PEM file."""
    with salt.utils.files.fopen(path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    os.chmod(path, 0o600)


def _write_certificate(cert, path):
    """Write certificate to PEM file."""
    with salt.utils.files.fopen(path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


@pytest.fixture(scope="session")
def ssl_ca_cert_key(tmp_path_factory):
    """
    Generate a self-signed CA certificate and private key.

    Returns:
        tuple: (ca_cert_path, ca_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    # Create directory for certificates
    cert_dir = tmp_path_factory.mktemp("ssl_certs")

    # Generate CA private key
    ca_key = _generate_private_key()
    ca_key_path = cert_dir / "ca.key"
    _write_private_key(ca_key, ca_key_path)

    # Generate CA certificate
    ca_cert = _generate_ca_certificate(ca_key, common_name="Salt Test CA")
    ca_cert_path = cert_dir / "ca.crt"
    _write_certificate(ca_cert, ca_cert_path)

    return str(ca_cert_path), str(ca_key_path)


@pytest.fixture(scope="session")
def ssl_server_cert_key(tmp_path_factory, ssl_ca_cert_key):
    """
    Generate a server certificate and private key signed by the CA.

    Returns:
        tuple: (server_cert_path, server_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    ca_cert_path, ca_key_path = ssl_ca_cert_key
    # Get the directory where CA certs are stored
    import os

    cert_dir = os.path.dirname(ca_cert_path)

    # Load CA certificate and key
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    # Generate server private key
    server_key = _generate_private_key()
    server_key_path = os.path.join(cert_dir, "server.key")
    _write_private_key(server_key, server_key_path)

    # Generate server certificate with SAN
    # Include localhost, 127.0.0.1, and common network names
    san_names = ["localhost", "127.0.0.1", "salt-master", "master"]
    server_cert = _generate_certificate(
        server_key,
        ca_cert,
        ca_key,
        common_name="localhost",
        san_dns_names=san_names,
    )
    server_cert_path = os.path.join(cert_dir, "server.crt")
    _write_certificate(server_cert, server_cert_path)

    return str(server_cert_path), str(server_key_path)


@pytest.fixture(scope="session")
def ssl_client_cert_key(tmp_path_factory, ssl_ca_cert_key):
    """
    Generate a client certificate and private key signed by the CA.

    Returns:
        tuple: (client_cert_path, client_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    ca_cert_path, ca_key_path = ssl_ca_cert_key
    # Get the directory where CA certs are stored
    import os

    cert_dir = os.path.dirname(ca_cert_path)

    # Load CA certificate and key
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    # Generate client private key
    client_key = _generate_private_key()
    client_key_path = os.path.join(cert_dir, "client.key")
    _write_private_key(client_key, client_key_path)

    # Generate client certificate with SAN
    san_names = ["localhost", "127.0.0.1", "salt-minion", "minion"]
    client_cert = _generate_certificate(
        client_key,
        ca_cert,
        ca_key,
        common_name="salt-minion",
        san_dns_names=san_names,
    )
    client_cert_path = os.path.join(cert_dir, "client.crt")
    _write_certificate(client_cert, client_cert_path)

    return str(client_cert_path), str(client_key_path)


@pytest.fixture
def ssl_master_config(ssl_ca_cert_key, ssl_server_cert_key):
    """
    SSL configuration dict for Salt master with CERT_REQUIRED.

    Returns:
        dict: SSL configuration for master
    """
    ca_cert_path, _ = ssl_ca_cert_key
    server_cert_path, server_key_path = ssl_server_cert_key

    return {
        "certfile": server_cert_path,
        "keyfile": server_key_path,
        "ca_certs": ca_cert_path,
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture
def ssl_minion_config(ssl_ca_cert_key, ssl_client_cert_key):
    """
    SSL configuration dict for Salt minion with CERT_REQUIRED.

    Returns:
        dict: SSL configuration for minion
    """
    ca_cert_path, _ = ssl_ca_cert_key
    client_cert_path, client_key_path = ssl_client_cert_key

    return {
        "certfile": client_cert_path,
        "keyfile": client_key_path,
        "ca_certs": ca_cert_path,
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture(scope="session")
def ssl_invalid_ca_cert_key(tmp_path_factory):
    """
    Generate a separate (invalid) CA certificate that won't validate
    certificates signed by the main CA.

    This is used to test scenarios where the client/server don't trust
    each other's certificates.

    Returns:
        tuple: (invalid_ca_cert_path, invalid_ca_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    cert_dir = tmp_path_factory.mktemp("ssl_certs_invalid")

    # Generate CA private key
    ca_key = _generate_private_key()
    ca_key_path = os.path.join(str(cert_dir), "invalid_ca.key")
    _write_private_key(ca_key, ca_key_path)

    # Generate self-signed CA certificate
    ca_cert = _generate_ca_certificate(ca_key, common_name="Invalid Test CA")
    ca_cert_path = os.path.join(str(cert_dir), "invalid_ca.crt")
    _write_certificate(ca_cert, ca_cert_path)

    return str(ca_cert_path), str(ca_key_path)


@pytest.fixture(scope="session")
def ssl_invalid_server_cert_key(tmp_path_factory, ssl_invalid_ca_cert_key):
    """
    Generate a server certificate signed by the invalid CA.

    This certificate won't be trusted by clients using the main CA.

    Returns:
        tuple: (invalid_server_cert_path, invalid_server_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    ca_cert_path, ca_key_path = ssl_invalid_ca_cert_key
    cert_dir = os.path.dirname(ca_cert_path)

    # Load invalid CA certificate and key
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    # Generate server private key
    server_key = _generate_private_key()
    server_key_path = os.path.join(cert_dir, "invalid_server.key")
    _write_private_key(server_key, server_key_path)

    # Generate server certificate with SAN
    san_names = ["localhost", "127.0.0.1", "salt-master", "master"]
    server_cert = _generate_certificate(
        server_key,
        ca_cert,
        ca_key,
        common_name="localhost",
        san_dns_names=san_names,
    )
    server_cert_path = os.path.join(cert_dir, "invalid_server.crt")
    _write_certificate(server_cert, server_cert_path)

    return str(server_cert_path), str(server_key_path)


@pytest.fixture(scope="session")
def ssl_invalid_client_cert_key(tmp_path_factory, ssl_invalid_ca_cert_key):
    """
    Generate a client certificate signed by the invalid CA.

    This certificate won't be trusted by servers using the main CA.

    Returns:
        tuple: (invalid_client_cert_path, invalid_client_key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    ca_cert_path, ca_key_path = ssl_invalid_ca_cert_key
    cert_dir = os.path.dirname(ca_cert_path)

    # Load invalid CA certificate and key
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    # Generate client private key
    client_key = _generate_private_key()
    client_key_path = os.path.join(cert_dir, "invalid_client.key")
    _write_private_key(client_key, client_key_path)

    # Generate client certificate with SAN
    san_names = ["localhost", "127.0.0.1", "salt-minion", "minion"]
    client_cert = _generate_certificate(
        client_key,
        ca_cert,
        ca_key,
        common_name="salt-minion",
        san_dns_names=san_names,
    )
    client_cert_path = os.path.join(cert_dir, "invalid_client.crt")
    _write_certificate(client_cert, client_cert_path)

    return str(client_cert_path), str(client_key_path)


@pytest.fixture
def ssl_master_config_invalid_cert(ssl_ca_cert_key, ssl_invalid_server_cert_key):
    """
    SSL configuration for master with a certificate signed by wrong CA.

    This simulates a misconfigured server where the certificate doesn't
    match the CA that clients trust.

    Returns:
        dict: SSL configuration with invalid server certificate
    """
    ca_cert_path, _ = ssl_ca_cert_key
    server_cert_path, server_key_path = ssl_invalid_server_cert_key

    return {
        "certfile": server_cert_path,
        "keyfile": server_key_path,
        "ca_certs": ca_cert_path,  # Valid CA, but cert is signed by different CA
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture
def ssl_minion_config_invalid_cert(ssl_ca_cert_key, ssl_invalid_client_cert_key):
    """
    SSL configuration for minion with a certificate signed by wrong CA.

    This simulates a misconfigured client where the certificate doesn't
    match the CA that servers trust.

    Returns:
        dict: SSL configuration with invalid client certificate
    """
    ca_cert_path, _ = ssl_ca_cert_key
    client_cert_path, client_key_path = ssl_invalid_client_cert_key

    return {
        "certfile": client_cert_path,
        "keyfile": client_key_path,
        "ca_certs": ca_cert_path,  # Valid CA, but cert is signed by different CA
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture
def ssl_minion_config_no_cert(ssl_ca_cert_key):
    """
    SSL configuration for minion without any client certificate.

    This simulates a client that doesn't present a certificate, which should
    be rejected when server has CERT_REQUIRED.

    Returns:
        dict: SSL configuration without client certificate
    """
    ca_cert_path, _ = ssl_ca_cert_key

    return {
        # No certfile or keyfile
        "ca_certs": ca_cert_path,
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture(scope="session")
def ssl_minion_cert_key_with_id(tmp_path_factory, ssl_ca_cert_key):
    """
    Generate client certificates for specific minion IDs.

    This is a factory fixture that generates certificates with the minion ID
    in both the CN and SAN fields.

    Args:
        minion_id: The minion ID to use in the certificate

    Returns:
        function: A function that takes minion_id and returns (cert_path, key_path)
    """
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    ca_cert_path, ca_key_path = ssl_ca_cert_key
    cert_dir = os.path.dirname(ca_cert_path)

    # Load CA certificate and key
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with salt.utils.files.fopen(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), None, default_backend())

    # Cache for generated certificates
    cert_cache = {}

    def _generate_minion_cert(minion_id):
        """Generate a certificate for a specific minion ID."""
        if minion_id in cert_cache:
            return cert_cache[minion_id]

        # Generate client private key
        client_key = _generate_private_key()
        client_key_path = os.path.join(cert_dir, f"client_{minion_id}.key")
        _write_private_key(client_key, client_key_path)

        # Generate client certificate with minion ID in CN and SAN
        san_names = [minion_id, "localhost", "127.0.0.1"]
        client_cert = _generate_certificate(
            client_key,
            ca_cert,
            ca_key,
            common_name=minion_id,
            san_dns_names=san_names,
        )
        client_cert_path = os.path.join(cert_dir, f"client_{minion_id}.crt")
        _write_certificate(client_cert, client_cert_path)

        result = (str(client_cert_path), str(client_key_path))
        cert_cache[minion_id] = result
        return result

    return _generate_minion_cert


@pytest.fixture
def ssl_minion_a_cert_key(ssl_minion_cert_key_with_id):
    """Certificate for minion with ID 'test-minion-a'."""
    return ssl_minion_cert_key_with_id("test-minion-a")


@pytest.fixture
def ssl_minion_b_cert_key(ssl_minion_cert_key_with_id):
    """Certificate for minion with ID 'test-minion-b'."""
    return ssl_minion_cert_key_with_id("test-minion-b")


@pytest.fixture
def ssl_minion_a_config(ssl_ca_cert_key, ssl_minion_a_cert_key):
    """
    SSL configuration for minion A with certificate CN=test-minion-a.

    Returns:
        dict: SSL configuration for minion A
    """
    ca_cert_path, _ = ssl_ca_cert_key
    client_cert_path, client_key_path = ssl_minion_a_cert_key

    return {
        "certfile": client_cert_path,
        "keyfile": client_key_path,
        "ca_certs": ca_cert_path,
        "cert_reqs": "CERT_REQUIRED",
    }


@pytest.fixture
def ssl_minion_b_config(ssl_ca_cert_key, ssl_minion_b_cert_key):
    """
    SSL configuration for minion B with certificate CN=test-minion-b.

    Returns:
        dict: SSL configuration for minion B
    """
    ca_cert_path, _ = ssl_ca_cert_key
    client_cert_path, client_key_path = ssl_minion_b_cert_key

    return {
        "certfile": client_cert_path,
        "keyfile": client_key_path,
        "ca_certs": ca_cert_path,
        "cert_reqs": "CERT_REQUIRED",
    }
