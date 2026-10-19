"""
Server-side reporting of TLS handshakes rejected by certificate verification:
once per peer address and reason, with an actionable hint, instead of once
per connection attempt.
"""

import asyncio
import logging
import socket
import ssl

import pytest

import salt.transport.tls_reload as tls_reload

pytestmark = [
    pytest.mark.core_test,
]

pytest.importorskip("cryptography.x509")

from tests.pytests.unit.transport.test_tls_crl import (  # noqa: E402,F401
    _client_ctx,
    _client_opts,
    _revoke,
    _server_opts,
    pki,
)


@pytest.fixture
def fresh_reports(monkeypatch):
    monkeypatch.setattr(tls_reload, "_reported", type(tls_reload._reported)())


async def test_tornado_server_reports_revoked_peer_once(
    pki, caplog, fresh_reports, io_loop
):
    """
    The tcp transport serves through tornado: a revoked minion reconnecting
    in a loop is logged once with an actionable hint, not once per attempt
    (tornado's own per-attempt "SSL Error" warning is suppressed for it).
    """
    import tornado.tcpserver

    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)

    class Server(tornado.tcpserver.TCPServer):
        async def handle_stream(self, stream, address):
            try:
                await stream.write(b"ok")
            finally:
                stream.close()

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(8)
    sock.setblocking(False)
    port = sock.getsockname()[1]
    server = Server(ssl_options=reloader.context)
    server.add_socket(sock)

    async def attempt(who):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    "127.0.0.1",
                    port,
                    ssl=_client_ctx(_client_opts(pki, who)),
                    server_hostname="localhost",
                ),
                5,
            )
        except (ssl.SSLError, OSError) as exc:
            return exc
        try:
            return await asyncio.wait_for(reader.read(16), 5)
        except (ssl.SSLError, OSError) as exc:
            return exc
        finally:
            writer.close()

    try:
        with caplog.at_level(logging.DEBUG):
            assert await attempt("good") == b"ok"
            for _ in range(3):
                assert await attempt("bad") != b"ok"
            await asyncio.sleep(0.2)
    finally:
        server.stop()

    reports = [
        r
        for r in caplog.records
        if r.name == "salt.transport.tls_reload"
        and r.getMessage().startswith("Rejected TLS connection from 127.0.0.1")
    ]
    assert [r.levelno for r in reports if r.levelno >= logging.WARNING] == [
        logging.WARNING
    ]
    assert "certificate revoked" in reports[0].getMessage()
    assert "ssl.crlfile" in reports[0].getMessage()
    assert len(reports) == 3  # the repeats at debug level
    assert not [
        r
        for r in caplog.records
        if r.name == "tornado.general" and "SSL Error" in r.getMessage()
    ]


def test_report_levels_and_rate_limit(fresh_reports, caplog):
    def err(code, message):
        exc = ssl.SSLCertVerificationError(1, message)
        exc.verify_code = code
        exc.verify_message = message
        return exc

    with caplog.at_level(logging.DEBUG, logger="salt.transport.tls_reload"):
        tls_reload.report_handshake_failure(
            err(23, "certificate revoked"), ("10.0.0.5", 1)
        )
        tls_reload.report_handshake_failure(
            err(23, "certificate revoked"), ("10.0.0.5", 2)
        )
        tls_reload.report_handshake_failure(
            err(23, "certificate revoked"), ("10.0.0.6", 3)
        )
        tls_reload.report_handshake_failure(
            err(3, "unable to get certificate CRL"), ("10.0.0.5", 4)
        )
    levels = [(r.levelno, r.getMessage().split(":")[0]) for r in caplog.records]
    assert levels == [
        (logging.WARNING, "Rejected TLS connection from 10.0.0.5"),
        (logging.DEBUG, "Rejected TLS connection from 10.0.0.5 again"),
        (logging.WARNING, "Rejected TLS connection from 10.0.0.6"),
        (logging.ERROR, "Rejected TLS connection from 10.0.0.5"),
    ]


def test_asyncio_server_context_reports_rejections(pki, fresh_reports, caplog):
    """ws (aiohttp/asyncio) wraps BIOs: the SSLObject hook reports too."""
    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    client = _client_ctx(_client_opts(pki, "bad"))
    c2s, s2c = ssl.MemoryBIO(), ssl.MemoryBIO()
    srv = reloader.context.wrap_bio(c2s, s2c, server_side=True)
    cli = client.wrap_bio(s2c, c2s, server_hostname="localhost")
    with caplog.at_level(logging.WARNING, logger="salt.transport.tls_reload"):
        with pytest.raises(ssl.SSLCertVerificationError):
            for _ in range(10):
                for side in (cli, srv):
                    try:
                        side.do_handshake()
                    except ssl.SSLWantReadError:
                        pass
    assert any("unknown peer" in r.getMessage() for r in caplog.records)
