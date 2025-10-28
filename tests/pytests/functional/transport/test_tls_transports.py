"""
High level TLS handshake regression tests for the master/minion transports.

These scenarios rely on salt-factories to stand up a real master/minion pair so
that we exercise the full publish/request pipeline instead of unit-level stubs.
"""

import os
import pathlib
from contextlib import contextmanager

import pytest
from OpenSSL import crypto
from saltfactories.utils import random_string

from tests.conftest import FIPS_TESTRUN

if os.environ.get("RUN_TLS_FACTORIES_TESTS") != "1":
    pytestmark = pytest.mark.skip(
        reason="Set RUN_TLS_FACTORIES_TESTS=1 to exercise factories-based TLS scenarios"
    )

TRANSPORTS = ("tcp", "tcpv2", "ws")


def _write_pem(path: pathlib.Path, data: bytes, mode: int = 0o600) -> None:
    """
    Persist a PEM blob to disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fp:
        fp.write(data)
    os.chmod(path, mode)


def _generate_ca(cert_dir: pathlib.Path):
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(int.from_bytes(os.urandom(16), "big"))
    subject = cert.get_subject()
    subject.CN = "Salt TLS Test CA"
    subject.O = "SaltStack"
    subject.OU = "Integration Tests"
    subject.L = "Salt Lake City"
    subject.ST = "Utah"
    subject.C = "US"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
    cert.set_issuer(subject)
    cert.set_pubkey(key)
    cert.add_extensions(
        [
            crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE,pathlen:0"),
            crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
            crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        ]
    )
    cert.sign(key, "sha256")
    ca_cert_path = cert_dir / "ca.crt"
    ca_key_path = cert_dir / "ca.key"
    _write_pem(ca_cert_path, crypto.dump_certificate(crypto.FILETYPE_PEM, cert), mode=0o644)
    _write_pem(ca_key_path, crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    return ca_cert_path, ca_key_path, cert, key


def _generate_certificate(
    cert_dir: pathlib.Path, ca_cert, ca_key, common_name: str, *, client: bool
):
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(int.from_bytes(os.urandom(16), "big"))
    subject = cert.get_subject()
    subject.CN = common_name
    subject.O = "SaltStack"
    subject.OU = "Integration Tests"
    subject.L = "Salt Lake City"
    subject.ST = "Utah"
    subject.C = "US"
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365 * 24 * 60 * 60)
    cert.set_issuer(ca_cert.get_subject())
    cert.set_pubkey(key)
    san = f"DNS:{common_name},DNS:localhost,IP:127.0.0.1".encode()
    if client:
        eku = b"clientAuth"
    else:
        eku = b"serverAuth,clientAuth"
    extensions = [
        crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
        crypto.X509Extension(b"subjectAltName", False, san),
        crypto.X509Extension(b"extendedKeyUsage", False, eku),
        crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert),
        crypto.X509Extension(
            b"authorityKeyIdentifier",
            False,
            b"keyid:always,issuer:always",
            issuer=ca_cert,
        ),
    ]
    cert.add_extensions(extensions)
    cert.sign(ca_key, "sha256")
    cert_path = cert_dir / f"{common_name}.crt"
    key_path = cert_dir / f"{common_name}.key"
    _write_pem(cert_path, crypto.dump_certificate(crypto.FILETYPE_PEM, cert), mode=0o644)
    _write_pem(key_path, crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    return cert_path, key_path


@pytest.fixture
def tls_materials(tmp_path):
    """
    Build a CA along with server and client certificates for TLS testing.
    """
    cert_dir = tmp_path / "tls"
    cert_dir.mkdir(parents=True, exist_ok=True)
    ca_cert_path, ca_key_path, ca_cert, ca_key = _generate_ca(cert_dir)
    master_cert, master_key = _generate_certificate(
        cert_dir, ca_cert, ca_key, "127.0.0.1", client=False
    )
    minion_cert, minion_key = _generate_certificate(
        cert_dir, ca_cert, ca_key, "minion.local", client=True
    )
    master_ssl = {
        "certfile": str(master_cert),
        "keyfile": str(master_key),
        "ca_certs": str(ca_cert_path),
        "cert_reqs": "CERT_REQUIRED",
    }
    minion_ssl = {
        "certfile": str(minion_cert),
        "keyfile": str(minion_key),
        "ca_certs": str(ca_cert_path),
        "cert_reqs": "CERT_REQUIRED",
    }
    return {
        "master_ssl": master_ssl,
        "minion_ssl": minion_ssl,
    }


@contextmanager
def _started(factory):
    """
    Context manager helper around ``factory.started()`` that makes sure we always terminate.
    """
    try:
        with factory.started():
            yield factory
    finally:
        factory.terminate()


@pytest.mark.parametrize("transport", TRANSPORTS, ids=lambda item: f"transport({item})")
def test_tls_master_minion_round_trip(
    salt_factories, tls_materials, transport
):
    """
    Assert that each TLS-capable transport can negotiate a secure master/minion session and
    execute a simple command.
    """
    master_id = random_string("tls-master-")
    minion_id = random_string("tls-minion-")

    master_overrides = {
        "auto_accept": True,
        "open_mode": True,
        "transport": transport,
        "ssl": tls_materials["master_ssl"],
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    if transport == "ws":
        # Ensure the websocket server binds deterministically for TLS tests.
        master_overrides.setdefault("websocket_max_message_size", 1048576)

    master = salt_factories.salt_master_daemon(
        master_id,
        overrides=master_overrides,
    )

    minion_overrides = {
        "ssl": tls_materials["minion_ssl"],
        "fips_mode": FIPS_TESTRUN,
    }
    minion = salt_factories.salt_minion_daemon(
        minion_id,
        master=master,
        overrides=minion_overrides,
    )

    with _started(master):
        with _started(minion):
            salt_cli = master.salt_cli()
            result = salt_cli.run(
                "--out=json",
                "test.ping",
                minion_tgt=minion_id,
                _timeout=120,
            )
            assert result.returncode == 0, result
            assert result.data, result.stdout
            assert result.data.get(minion_id) is True, result.data
