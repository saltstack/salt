"""
Unit tests for SSL/TLS transport configuration.

These tests verify that TCP and WebSocket transports can be properly
configured with SSL certificates.
"""

import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend

import salt.config
import salt.utils.files

pytestmark = [
    pytest.mark.core_test,
]


def test_ssl_config_has_required_fields(ssl_master_config, ssl_minion_config):
    """
    Test that SSL config dictionaries have all required fields.
    """
    # Master config
    assert "certfile" in ssl_master_config
    assert "keyfile" in ssl_master_config
    assert "ca_certs" in ssl_master_config
    assert "cert_reqs" in ssl_master_config

    # Minion config
    assert "certfile" in ssl_minion_config
    assert "keyfile" in ssl_minion_config
    assert "ca_certs" in ssl_minion_config
    assert "cert_reqs" in ssl_minion_config


def test_ssl_certificates_are_valid(
    ssl_ca_cert_key, ssl_server_cert_key, ssl_client_cert_key
):
    """
    Test that generated certificates are valid PEM format.
    """

    ca_cert_path, _ = ssl_ca_cert_key
    server_cert_path, _ = ssl_server_cert_key
    client_cert_path, _ = ssl_client_cert_key

    # Load and validate CA certificate
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    assert ca_cert.subject

    # Verify CA has CA basic constraint
    basic_constraints = ca_cert.extensions.get_extension_for_oid(
        x509.oid.ExtensionOID.BASIC_CONSTRAINTS
    )
    assert basic_constraints.value.ca is True

    # Load and validate server certificate
    with salt.utils.files.fopen(server_cert_path, "rb") as f:
        server_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    assert server_cert.subject

    # Verify server cert is signed by CA
    assert server_cert.issuer == ca_cert.subject

    # Load and validate client certificate
    with salt.utils.files.fopen(client_cert_path, "rb") as f:
        client_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    assert client_cert.subject

    # Verify client cert is signed by CA
    assert client_cert.issuer == ca_cert.subject


def test_server_cert_has_san(ssl_server_cert_key):
    """
    Test that server certificate has Subject Alternative Name extension.
    """

    server_cert_path, _ = ssl_server_cert_key

    with salt.utils.files.fopen(server_cert_path, "rb") as f:
        server_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Get SAN extension
    san_ext = server_cert.extensions.get_extension_for_oid(
        x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
    )

    # Verify localhost and 127.0.0.1 are in SAN
    # Note: IP addresses are stored as IPAddress objects, not DNS names

    san_values = []
    for name in san_ext.value:
        if isinstance(name, x509.DNSName):
            san_values.append(name.value)
        elif isinstance(name, x509.IPAddress):
            san_values.append(str(name.value))

    assert "localhost" in san_values
    assert "127.0.0.1" in san_values


def test_cert_reqs_string_to_constant():
    """
    Test that cert_reqs string is properly converted to SSL constant.
    """

    opts = {"ssl": {"cert_reqs": "CERT_REQUIRED"}}
    salt.config._update_ssl_config(opts)

    # Should be converted to constant
    assert opts["ssl"]["cert_reqs"] == ssl.CERT_REQUIRED


def test_ssl_config_with_none():
    """
    Test that ssl=None is handled correctly.
    """

    opts = {"ssl": None}
    salt.config._update_ssl_config(opts)

    assert opts["ssl"] is None


def test_ssl_config_with_false():
    """
    Test that ssl=False is handled correctly.
    """

    opts = {"ssl": False}
    salt.config._update_ssl_config(opts)

    assert opts["ssl"] is None


def test_ssl_config_with_true():
    """
    Test that ssl=True creates empty dict.
    """

    opts = {"ssl": True}
    salt.config._update_ssl_config(opts)

    # Should be converted to empty dict
    assert opts["ssl"] == {}
