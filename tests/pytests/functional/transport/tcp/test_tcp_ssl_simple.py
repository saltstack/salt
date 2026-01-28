"""
Simple functional tests for TCP transport with SSL/TLS.

These tests verify basic SSL configuration and transport creation.
"""

import pytest

import salt.config
import salt.transport

pytestmark = [
    pytest.mark.core_test,
]


def test_tcp_transport_accepts_ssl_config(master_opts, ssl_master_config):
    """
    Test that TCP transport accepts SSL configuration without errors.

    This verifies:
    1. SSL config can be added to master_opts
    2. Transport can be created with SSL config
    3. No exceptions are raised during initialization
    """
    # Configure transport with SSL
    master_opts["transport"] = "tcp"
    master_opts["ssl"] = ssl_master_config.copy()

    # Convert cert_reqs string to constant
    salt.config._update_ssl_config(master_opts)

    # Verify conversion happened
    import ssl

    assert master_opts["ssl"]["cert_reqs"] == ssl.CERT_REQUIRED

    # Create transport - should not raise exception
    try:
        pub_server = salt.transport.publish_server(master_opts)
        # If we get here, SSL config was accepted
        assert pub_server is not None
        pub_server.close()
    except (ValueError, TypeError, OSError) as e:
        # ValueError: Invalid SSL configuration
        # TypeError: Invalid parameter types
        # OSError: File/network errors
        pytest.fail(f"Failed to create transport with SSL: {e}")


def test_tcp_client_accepts_ssl_config(minion_opts, io_loop, ssl_minion_config):
    """
    Test that TCP client accepts SSL configuration without errors.

    This verifies:
    1. SSL config can be added to minion_opts
    2. Client can be created with SSL config
    3. No exceptions are raised during initialization
    """
    # Configure transport with SSL
    minion_opts["transport"] = "tcp"
    minion_opts["ssl"] = ssl_minion_config.copy()

    # Convert cert_reqs string to constant
    salt.config._update_ssl_config(minion_opts)

    # Verify conversion happened
    import ssl

    assert minion_opts["ssl"]["cert_reqs"] == ssl.CERT_REQUIRED

    # Create client - should not raise exception
    try:
        pub_client = salt.transport.publish_client(
            minion_opts, io_loop, "127.0.0.1", 4505
        )
        # If we get here, SSL config was accepted
        assert pub_client is not None
        pub_client.close()
    except (ValueError, TypeError, OSError) as e:
        # ValueError: Invalid SSL configuration
        # TypeError: Invalid parameter types
        # OSError: File/network errors
        pytest.fail(f"Failed to create client with SSL: {e}")


def test_ssl_config_has_certificate_files(ssl_master_config, ssl_minion_config):
    """
    Test that SSL config includes valid certificate file paths.
    """
    import os

    # Check master config
    assert os.path.exists(ssl_master_config["certfile"])
    assert os.path.exists(ssl_master_config["keyfile"])
    assert os.path.exists(ssl_master_config["ca_certs"])

    # Check minion config
    assert os.path.exists(ssl_minion_config["certfile"])
    assert os.path.exists(ssl_minion_config["keyfile"])
    assert os.path.exists(ssl_minion_config["ca_certs"])


def test_ssl_config_cert_reqs_is_required(ssl_master_config):
    """
    Test that cert_reqs is set to CERT_REQUIRED.

    This is critical for the TLS optimization feature.
    """
    assert ssl_master_config["cert_reqs"] == "CERT_REQUIRED"
