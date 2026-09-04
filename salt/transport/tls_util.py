"""
Utilities for TLS encryption optimization.

This module provides functions for detecting when TLS is active with validated
certificates and when AES encryption can be safely skipped.
"""

import logging
import ssl

log = logging.getLogger(__name__)

# Try to import cryptography for certificate parsing
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def can_skip_aes_encryption(opts, peer_cert=None, claimed_id=None):
    """
    Determine if AES encryption can be skipped for this connection.

    This function implements the security checks required for the TLS
    encryption optimization. AES can only be skipped when ALL conditions are met:

    1. disable_aes_with_tls is enabled in configuration
    2. SSL is configured
    3. cert_reqs is CERT_REQUIRED (mutual TLS)
    4. Transport is TCP or WS (not ZeroMQ)
    5. Peer certificate is present
    6. Peer certificate identity matches claimed minion ID (if applicable)

    Args:
        opts: Configuration dictionary
        peer_cert: Peer's SSL certificate (DER format bytes or None)
        claimed_id: The minion ID claimed in the message (optional)

    Returns:
        bool: True if AES encryption can be skipped, False otherwise
    """
    # Check if optimization is enabled
    if not opts.get("disable_aes_with_tls", False):
        return False

    # Check if SSL is configured
    ssl_config = opts.get("ssl")
    if not ssl_config or ssl_config is None:
        log.debug("Cannot skip AES: SSL not configured")
        return False

    # Check if cert_reqs is CERT_REQUIRED
    cert_reqs = ssl_config.get("cert_reqs")
    if cert_reqs != ssl.CERT_REQUIRED:
        log.debug("Cannot skip AES: cert_reqs is %s, must be CERT_REQUIRED", cert_reqs)
        return False

    # Check transport type
    transport = opts.get("transport", "zeromq")
    if transport not in ("tcp", "ws"):
        log.debug("Cannot skip AES: transport %s does not support TLS", transport)
        return False

    # Check if peer certificate is present
    if peer_cert is None:
        log.debug("Cannot skip AES: no peer certificate")
        return False

    # If a claimed ID is provided, verify it matches the certificate
    if claimed_id is not None:
        if not verify_cert_identity(peer_cert, claimed_id):
            log.warning(
                "Cannot skip AES: certificate identity does not match claimed ID '%s'",
                claimed_id,
            )
            return False

    return True


def verify_cert_identity(peer_cert, expected_id):
    """
    Verify that the peer certificate identity matches the expected minion ID.

    This is a critical security check that prevents minion impersonation.
    Without this check, a minion with a valid certificate could claim to be
    any other minion.

    Args:
        peer_cert: Peer's SSL certificate (DER format bytes)
        expected_id: The expected minion ID to match

    Returns:
        bool: True if certificate identity matches expected_id, False otherwise
    """
    if not HAS_CRYPTOGRAPHY:
        log.warning(
            "Cannot verify certificate identity: cryptography library not available"
        )
        return False

    try:
        # Load certificate
        cert = x509.load_der_x509_certificate(peer_cert, default_backend())

        # Check Common Name
        for attr in cert.subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                if attr.value == expected_id:
                    log.debug(
                        "Certificate identity verified: CN='%s' matches expected ID '%s'",
                        attr.value,
                        expected_id,
                    )
                    return True

        # Check Subject Alternative Name
        try:
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            san_names = [name.value for name in san_ext.value]
            if expected_id in san_names:
                log.debug(
                    "Certificate identity verified: SAN contains '%s'", expected_id
                )
                return True
        except x509.ExtensionNotFound:
            pass

        log.debug(
            "Certificate identity mismatch: expected '%s', cert does not contain this identity",
            expected_id,
        )
        return False

    except (ValueError, TypeError, AttributeError) as e:
        # ValueError: Invalid certificate format
        # TypeError: Invalid argument types
        # AttributeError: Missing certificate attributes
        log.error("Error verifying certificate identity: %s", e)
        return False


def get_cert_identity(peer_cert):
    """
    Extract identity information from a peer certificate.

    Args:
        peer_cert: Peer's SSL certificate (DER format bytes)

    Returns:
        tuple: (common_name, san_dns_names) or (None, []) on error
    """
    if not HAS_CRYPTOGRAPHY:
        return None, []

    try:
        cert = x509.load_der_x509_certificate(peer_cert, default_backend())

        # Get Common Name
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

    except (ValueError, TypeError, AttributeError) as e:
        # ValueError: Invalid certificate format
        # TypeError: Invalid argument types
        # AttributeError: Missing certificate attributes
        log.error("Error extracting certificate identity: %s", e)
        return None, []
