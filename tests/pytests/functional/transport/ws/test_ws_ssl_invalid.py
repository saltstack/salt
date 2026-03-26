"""
Tests for WebSocket transport SSL/TLS with invalid certificates.

These tests verify that WebSocket transport properly rejects invalid certificates
and enforces CERT_REQUIRED validation.
"""

import asyncio

import pytest

import salt.config
import salt.transport
import salt.utils.files

pytestmark = [
    pytest.mark.core_test,
]


async def test_ws_client_invalid_cert_rejected(
    io_loop,
    minion_opts,
    master_opts,
    process_manager,
    ssl_master_config,
    ssl_minion_config_invalid_cert,
):
    """
    Test that WebSocket server rejects client with certificate signed by wrong CA.

    This verifies:
    1. Server with valid certificate and CERT_REQUIRED
    2. Client with certificate signed by different CA
    3. Connection is rejected during TLS handshake
    """
    # Configure SSL for master with valid cert
    master_opts["transport"] = "ws"
    master_opts["ssl"] = ssl_master_config.copy()
    salt.config._update_ssl_config(master_opts)

    # Configure SSL for minion with invalid cert
    minion_opts["transport"] = "ws"
    minion_opts["ssl"] = ssl_minion_config_invalid_cert.copy()
    salt.config._update_ssl_config(minion_opts)

    # Create publish server with valid SSL
    pub_server = salt.transport.publish_server(master_opts)
    pub_server.pre_fork(process_manager)
    await asyncio.sleep(3)

    try:
        # Create publish client with invalid cert
        pub_client = salt.transport.publish_client(
            minion_opts, io_loop, master_opts["interface"], master_opts["publish_port"]
        )

        # Connection should fail during TLS handshake
        with pytest.raises((asyncio.TimeoutError, Exception)):
            await asyncio.wait_for(pub_client.connect(), timeout=5)

        pub_client.close()
    finally:
        pub_server.close()

    await asyncio.sleep(0.3)


async def test_ws_server_invalid_cert_rejected(
    io_loop,
    minion_opts,
    master_opts,
    process_manager,
    ssl_master_config_invalid_cert,
    ssl_minion_config,
):
    """
    Test that WebSocket client rejects server with certificate signed by wrong CA.

    This verifies:
    1. Server with certificate signed by different CA
    2. Client with valid certificate and CERT_REQUIRED
    3. Connection is rejected during TLS handshake
    """
    # Configure SSL for master with invalid cert
    master_opts["transport"] = "ws"
    master_opts["ssl"] = ssl_master_config_invalid_cert.copy()
    salt.config._update_ssl_config(master_opts)

    # Configure SSL for minion with valid cert
    minion_opts["transport"] = "ws"
    minion_opts["ssl"] = ssl_minion_config.copy()
    salt.config._update_ssl_config(minion_opts)

    # Create publish server with invalid SSL cert
    pub_server = salt.transport.publish_server(master_opts)
    pub_server.pre_fork(process_manager)
    await asyncio.sleep(3)

    try:
        # Create publish client with valid cert
        pub_client = salt.transport.publish_client(
            minion_opts, io_loop, master_opts["interface"], master_opts["publish_port"]
        )

        # Connection should fail during TLS handshake
        with pytest.raises((asyncio.TimeoutError, Exception)):
            await asyncio.wait_for(pub_client.connect(), timeout=5)

        pub_client.close()
    finally:
        pub_server.close()

    await asyncio.sleep(0.3)


async def test_ws_client_no_cert_rejected(
    io_loop,
    minion_opts,
    master_opts,
    process_manager,
    ssl_master_config,
    ssl_minion_config_no_cert,
):
    """
    Test that WebSocket server rejects client without certificate.

    This verifies:
    1. Server with CERT_REQUIRED
    2. Client without any certificate
    3. Connection is rejected during TLS handshake
    """
    # Configure SSL for master with CERT_REQUIRED
    master_opts["transport"] = "ws"
    master_opts["ssl"] = ssl_master_config.copy()
    salt.config._update_ssl_config(master_opts)

    # Configure minion without client cert
    minion_opts["transport"] = "ws"
    minion_opts["ssl"] = ssl_minion_config_no_cert.copy()
    salt.config._update_ssl_config(minion_opts)

    # Create publish server requiring client cert
    pub_server = salt.transport.publish_server(master_opts)
    pub_server.pre_fork(process_manager)
    await asyncio.sleep(3)

    try:
        # Create publish client without cert
        pub_client = salt.transport.publish_client(
            minion_opts, io_loop, master_opts["interface"], master_opts["publish_port"]
        )

        # Connection should fail during TLS handshake
        with pytest.raises((asyncio.TimeoutError, Exception)):
            await asyncio.wait_for(pub_client.connect(), timeout=5)

        pub_client.close()
    finally:
        pub_server.close()

    await asyncio.sleep(0.3)


def test_ws_invalid_cert_chain_detected(ssl_ca_cert_key, ssl_invalid_server_cert_key):
    """
    Test that we can detect when a certificate is not signed by the expected CA.

    This is a unit test that validates certificate chain without starting transports.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    ca_cert_path, _ = ssl_ca_cert_key
    invalid_server_cert_path, _ = ssl_invalid_server_cert_key

    # Load CA certificate
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Load invalid server certificate
    with salt.utils.files.fopen(invalid_server_cert_path, "rb") as f:
        server_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Verify that the certificate's issuer doesn't match the CA's subject
    assert server_cert.issuer != ca_cert.subject


def test_ws_invalid_ca_detected(ssl_ca_cert_key, ssl_invalid_ca_cert_key):
    """
    Test that we can detect when two CAs are different.

    This validates that our test fixtures create truly separate certificate authorities.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        pytest.skip("cryptography library not available")

    ca_cert_path, _ = ssl_ca_cert_key
    invalid_ca_cert_path, _ = ssl_invalid_ca_cert_key

    # Load both CA certificates
    with salt.utils.files.fopen(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    with salt.utils.files.fopen(invalid_ca_cert_path, "rb") as f:
        invalid_ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Verify that the CAs have different subjects
    assert ca_cert.subject != invalid_ca_cert.subject

    # Verify both are CAs
    ca_basic_constraints = ca_cert.extensions.get_extension_for_oid(
        x509.oid.ExtensionOID.BASIC_CONSTRAINTS
    )
    invalid_ca_basic_constraints = invalid_ca_cert.extensions.get_extension_for_oid(
        x509.oid.ExtensionOID.BASIC_CONSTRAINTS
    )

    assert ca_basic_constraints.value.ca is True
    assert invalid_ca_basic_constraints.value.ca is True
