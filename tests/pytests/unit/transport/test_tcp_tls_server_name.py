"""
Tests for checking the master's TLS certificate against the configured master
name instead of the address the minion connects to.

https://github.com/saltstack/salt/issues/70982
"""

import asyncio
import ssl

import pytest

import salt.transport.base
import salt.transport.tcp
import salt.utils.files
from tests.support.pytest.transport_ssl import (
    HAS_CRYPTOGRAPHY,
    _generate_ca_certificate,
    _generate_certificate,
    _generate_private_key,
    _write_certificate,
    _write_private_key,
)

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography is required"),
]

MASTER_NAME = "master.example.internal"


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    """
    A CA plus two server certificates:

    ``by_name``: SAN is the master's DNS name only.
    ``by_ip``: SAN is another DNS name and 127.0.0.1.
    """
    cert_dir = tmp_path_factory.mktemp("tls_server_name")
    ca_key = _generate_private_key()
    ca_cert = _generate_ca_certificate(ca_key)
    ca_path = cert_dir / "ca.crt"
    _write_certificate(ca_cert, ca_path)

    paths = {"ca": str(ca_path)}
    for label, sans in (
        ("by_name", [MASTER_NAME]),
        ("by_ip", ["other.example.internal", "127.0.0.1"]),
    ):
        key = _generate_private_key()
        cert = _generate_certificate(key, ca_cert, ca_key, sans[0], san_dns_names=sans)
        cert_path = cert_dir / f"{label}.crt"
        key_path = cert_dir / f"{label}.key"
        _write_certificate(cert, cert_path)
        _write_private_key(key, key_path)
        paths[label] = (str(cert_path), str(key_path))
    return paths


async def _tls_server(cert_key):
    """
    Start a TLS listener on 127.0.0.1 that records the SNI each client sends.
    """
    seen = []
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(*cert_key)

    def sni_callback(sslobj, server_name, context):
        seen.append(server_name)

    ctx.sni_callback = sni_callback

    async def handle(reader, writer):
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=ctx)
    port = server.sockets[0].getsockname()[1]
    return server, port, seen


def _client_ctx(certs):
    return salt.transport.base.ssl_context(
        {"ca_certs": certs["ca"], "cert_reqs": ssl.CERT_REQUIRED}, server_side=False
    )


async def _connect(opts, port, ctx):
    client = salt.transport.tcp.TCPClientKeepAlive(opts)
    try:
        stream = await asyncio.wait_for(
            client.connect("127.0.0.1", port, ssl_options=ctx), 10
        )
        stream.close()
    finally:
        client.close()


async def test_certificate_checked_against_master_name(minion_opts, certs):
    """
    A certificate that names only the master's DNS name is accepted when the
    minion connects to the master's IP address, and the name is sent as SNI.
    """
    minion_opts["master"] = MASTER_NAME
    server, port, seen = await _tls_server(certs["by_name"])
    try:
        await _connect(minion_opts, port, _client_ctx(certs))
    finally:
        server.close()
        await server.wait_closed()
    assert seen == [MASTER_NAME]


async def test_certificate_for_other_name_with_ip_refused(minion_opts, certs):
    """
    A certificate that lists the master's IP address but not its name is
    refused when ``master`` is a host name.
    """
    minion_opts["master"] = MASTER_NAME
    server, port, _ = await _tls_server(certs["by_ip"])
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            await _connect(minion_opts, port, _client_ctx(certs))
    finally:
        server.close()
        await server.wait_closed()


async def test_master_ip_address_keeps_address_check(minion_opts, certs):
    """
    When ``master`` is an IP address, the certificate is still checked against
    that address.
    """
    minion_opts["master"] = "127.0.0.1"
    server, port, _ = await _tls_server(certs["by_ip"])
    try:
        await _connect(minion_opts, port, _client_ctx(certs))
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize(
    "role,master,expected",
    [
        ("minion", MASTER_NAME, MASTER_NAME),
        ("minion", "salt", "salt"),
        ("minion", "10.0.0.1", None),
        ("minion", "::1", None),
        ("minion", "[2001:db8::1]", None),
        ("minion", "", None),
        ("minion", None, None),
        ("minion", ["m1.example.internal", "m2.example.internal"], None),
        ("master", MASTER_NAME, None),
        ("syndic", MASTER_NAME, None),
    ],
)
def test_tls_server_name(role, master, expected):
    opts = {"__role": role, "master": master}
    assert salt.transport.tcp._tls_server_name(opts) == expected
