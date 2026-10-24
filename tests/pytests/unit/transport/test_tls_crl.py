"""
Certificate revocation (``ssl.crlfile``) for the TLS transports: loading on
both sides, rejection of revoked peers over real sockets, hot reload of
refreshed CRLs by ReloadableTLS and reporting of rejected handshakes.
"""

import datetime
import logging
import socket
import ssl
import subprocess
import threading
import time

import pytest

import salt.transport.base
import salt.transport.tls_reload as tls_reload

pytestmark = [
    pytest.mark.core_test,
]

x509 = pytest.importorskip("cryptography.x509")
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402

from tests.pytests.unit.transport.test_tls_reload import (  # noqa: E402
    DAY,
    NOW,
    _ca,
    _key_pem,
    _leaf,
    _pem,
)

HOUR = datetime.timedelta(hours=1)


def _crl(issuer, issuer_key, revoked=(), last_update=None, next_update=None, number=1):
    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer.subject)
        .last_update(last_update or NOW - HOUR)
        .next_update(next_update or NOW + DAY)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            False,
        )
        .add_extension(x509.CRLNumber(number), False)
    )
    for cert in revoked:
        builder = builder.add_revoked_certificate(
            x509.RevokedCertificateBuilder()
            .serial_number(cert.serial_number)
            .revocation_date(NOW - DAY)
            .build()
        )
    return builder.sign(issuer_key, hashes.SHA256()).public_bytes(
        serialization.Encoding.PEM
    )


@pytest.fixture
def pki(tmp_path):
    """Root -> issuing CA -> server, good client and revoked-to-be client."""
    root, root_key = _ca()
    inter, inter_key = _ca("Example Corp Issuing CA", root, root_key, path_length=0)
    server, server_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["localhost"]
    )
    good, good_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    bad, bad_key = _leaf("minion-b.corp.example", inter, inter_key, server=False)
    files = {
        "root": tmp_path / "root.crt",
        "server": tmp_path / "server.chain.crt",
        "server_key": tmp_path / "server.key",
        "good": tmp_path / "good.chain.crt",
        "good_key": tmp_path / "good.key",
        "bad": tmp_path / "bad.chain.crt",
        "bad_key": tmp_path / "bad.key",
        "crl": tmp_path / "issuing.crl.pem",
    }
    files["root"].write_bytes(_pem(root))
    files["server"].write_bytes(_pem(server, inter))
    files["server_key"].write_bytes(_key_pem(server_key))
    files["good"].write_bytes(_pem(good, inter))
    files["good_key"].write_bytes(_key_pem(good_key))
    files["bad"].write_bytes(_pem(bad, inter))
    files["bad_key"].write_bytes(_key_pem(bad_key))
    # Initially nothing is revoked.
    files["crl"].write_bytes(_crl(inter, inter_key))
    return {
        "files": files,
        "root": (root, root_key),
        "inter": (inter, inter_key),
        "server": (server, server_key),
        "good": (good, good_key),
        "bad": (bad, bad_key),
    }


def _revoke(pki, *certs, number=2, **kwargs):
    """Publish CRL ``number`` (issued ``number`` minutes after the first)."""
    kwargs.setdefault(
        "last_update", NOW - HOUR + number * datetime.timedelta(minutes=1)
    )
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(
        _crl(inter, inter_key, revoked=certs, number=number, **kwargs)
    )


def _server_opts(pki, crl=True, **extra):
    f = pki["files"]
    opts = {
        "certfile": str(f["server"]),
        "keyfile": str(f["server_key"]),
        "ca_certs": str(f["root"]),
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    if crl:
        opts["crlfile"] = str(f["crl"])
    opts.update(extra)
    return opts


def _client_opts(pki, who="good", crl=False, **extra):
    f = pki["files"]
    opts = {
        "certfile": str(f[who]),
        "keyfile": str(f[f"{who}_key"]),
        "ca_certs": str(f["root"]),
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    if crl:
        opts["crlfile"] = str(f["crl"])
    opts.update(extra)
    return opts


class _TLSServer:
    """
    A real TLS server on 127.0.0.1: every accepted connection is handshaken
    with ``context`` (looked up per connection, so a ReloadableTLS context
    swapped or updated in place is honoured) and answered with ``b"ok"``.
    """

    def __init__(self, context_getter):
        self._context_getter = context_getter
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self.errors = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                raw, _ = self._sock.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return
            raw.settimeout(5)
            try:
                with self._context_getter().wrap_socket(raw, server_side=True) as tls:
                    tls.sendall(b"ok")
            except (ssl.SSLError, OSError) as exc:
                self.errors.append(exc)
            finally:
                raw.close()

    def close(self):
        self._stop.set()
        self._sock.close()
        self._thread.join(5)


@pytest.fixture
def tls_server():
    servers = []

    def _start(context_getter):
        server = _TLSServer(context_getter)
        servers.append(server)
        return server

    yield _start
    for server in servers:
        server.close()


def _connect(port, client_ctx, server_hostname="localhost"):
    """``b"ok"`` when the server accepted the connection, else the error."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
        try:
            with client_ctx.wrap_socket(raw, server_hostname=server_hostname) as tls:
                data = tls.recv(16)
        except (ssl.SSLError, OSError) as exc:
            return exc
    return data or ConnectionResetError("closed by server")


def _client_ctx(opts):
    return salt.transport.base.ssl_context(opts, server_side=False)


# -- the option ------------------------------------------------------------


def test_option_absent_leaves_crl_checking_off(pki):
    for opts, side in (
        (_server_opts(pki, crl=False), True),
        (_client_opts(pki), False),
    ):
        ctx = salt.transport.base.ssl_context(opts, server_side=side)
        assert not ctx.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF
    assert salt.transport.base._crl_paths({}) == []


@pytest.mark.parametrize("server_side", [True, False])
def test_crlfile_enables_leaf_check_on_both_sides(pki, server_side):
    opts = _server_opts(pki) if server_side else _client_opts(pki, crl=True)
    ctx = salt.transport.base.ssl_context(opts, server_side=server_side)
    assert ctx.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF
    assert (
        not ctx.verify_flags & ssl.VERIFY_CRL_CHECK_CHAIN & ~ssl.VERIFY_CRL_CHECK_LEAF
    )


def test_crlfile_accepts_a_list_and_verify_flags_extend(pki, tmp_path):
    root, root_key = pki["root"]
    root_crl = tmp_path / "root.crl.pem"
    root_crl.write_bytes(_crl(root, root_key))
    opts = _server_opts(
        pki,
        crlfile=[str(pki["files"]["crl"]), str(root_crl)],
        verify_flags=["VERIFY_CRL_CHECK_CHAIN"],
    )
    assert salt.transport.base._crl_paths(opts) == opts["crlfile"]
    ctx = salt.transport.base.ssl_context(opts, server_side=True)
    assert ctx.verify_flags & ssl.VERIFY_CRL_CHECK_CHAIN == ssl.VERIFY_CRL_CHECK_CHAIN


def test_unparseable_crl_fails_context_creation(pki):
    pki["files"]["crl"].write_bytes(b"not a crl")
    with pytest.raises(ValueError, match="other than PEM encoded CRLs"):
        salt.transport.base.ssl_context(_server_opts(pki), server_side=True)


def _rogue(pki):
    """A rogue CA, a client certificate it issued, and the CA's own CRL."""
    rogue, rogue_key = _ca("Rogue CA")
    client, client_key = _leaf("minion-a.corp.example", rogue, rogue_key, server=False)
    return rogue, rogue_key, client, client_key


@pytest.mark.parametrize("server_side", [True, False])
def test_certificate_in_crlfile_is_refused_at_startup(pki, server_side):
    """
    OpenSSL's file loader would make a certificate found in the CRL file a
    trust anchor; the CRL file is written by a refresh job, so it must never
    widen trust: anything but CRLs fails startup loudly.
    """
    rogue, rogue_key, _, _ = _rogue(pki)
    crl = pki["files"]["crl"]
    crl.write_bytes(crl.read_bytes() + _pem(rogue) + _crl(rogue, rogue_key))
    opts = _server_opts(pki) if server_side else _client_opts(pki, crl=True)
    with pytest.raises(ValueError, match="other than PEM encoded CRLs"):
        salt.transport.base.ssl_context(opts, server_side=server_side)
    with pytest.raises(ValueError):
        tls_reload.ReloadableTLS(opts, server_side=server_side)


def test_certificate_hidden_inside_a_crl_block_is_refused(pki):
    data = pki["files"]["crl"].read_bytes()
    rogue, _, _, _ = _rogue(pki)
    head, rest = data.split(b"\n", 1)
    pki["files"]["crl"].write_bytes(head + b"\n" + _pem(rogue) + rest)
    with pytest.raises(ValueError):
        salt.transport.base.ssl_context(_server_opts(pki), server_side=True)


def _inject_rogue_on_refresh(pki, rogue, rogue_key):
    """Refreshed, valid CRL + a rogue CA certificate + the rogue CA's CRL."""
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(
        _crl(inter, inter_key, number=2, last_update=NOW - HOUR / 2)
        + _pem(rogue)
        + _crl(rogue, rogue_key)
    )


def test_certificate_appended_on_reload_is_refused_server(pki, tls_server, caplog):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    server = tls_server(lambda: reloader.context)
    rogue, rogue_key, client, client_key = _rogue(pki)
    _inject_rogue_on_refresh(pki, rogue, rogue_key)
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
    assert any("other than PEM encoded CRLs" in r.getMessage() for r in caplog.records)
    pki["files"]["rogue"] = pki["files"]["good"].with_name("rogue.crt")
    pki["files"]["rogue_key"] = pki["files"]["good"].with_name("rogue.key")
    pki["files"]["rogue"].write_bytes(_pem(client))
    pki["files"]["rogue_key"].write_bytes(_key_pem(client_key))
    assert _connect(server.port, _client_ctx(_client_opts(pki, "rogue"))) != b"ok"
    assert _connect(server.port, _client_ctx(_client_opts(pki, "good"))) == b"ok"


def test_certificate_appended_on_reload_is_refused_client(pki, tls_server, tmp_path):
    owner = type("Owner", (), {})()
    opts = _client_opts(pki, crl=True)
    tls_reload.client_context(owner, opts)
    rogue, rogue_key, _, _ = _rogue(pki)
    rogue_server, rogue_server_key = _leaf(
        "salt-master.corp.example", rogue, rogue_key, san=["localhost"]
    )
    (tmp_path / "rogue-server.crt").write_bytes(_pem(rogue_server))
    (tmp_path / "rogue-server.key").write_bytes(_key_pem(rogue_server_key))
    rogue_ctx = salt.transport.base.ssl_context(
        _server_opts(
            pki,
            crl=False,
            certfile=str(tmp_path / "rogue-server.crt"),
            keyfile=str(tmp_path / "rogue-server.key"),
            cert_reqs=ssl.CERT_NONE,
        ),
        server_side=True,
    )
    server = tls_server(lambda: rogue_ctx)
    _inject_rogue_on_refresh(pki, rogue, rogue_key)
    ctx = tls_reload.client_context(owner, opts)
    result = _connect(server.port, ctx)
    assert isinstance(result, ssl.SSLCertVerificationError)


def test_crl_revoking_own_certificate_is_adopted_with_error(pki, caplog):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    _revoke(pki, pki["server"][0])
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is True
    (record,) = [
        r for r in caplog.records if "own TLS server certificate" in r.getMessage()
    ]
    assert f"{pki['server'][0].serial_number:x}" in record.getMessage()


def test_der_cadata_bundle_provides_crl_issuers(pki):
    root, _ = pki["root"]
    inter, _ = pki["inter"]
    der = b"".join(c.public_bytes(serialization.Encoding.DER) for c in (root, inter))
    subjects = [c.subject for c in tls_reload._der_certificates(der)]
    assert subjects == [root.subject, inter.subject]


# -- real sockets ----------------------------------------------------------


def test_server_rejects_revoked_client_and_accepts_others(pki, tls_server):
    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    server = tls_server(lambda: reloader.context)

    assert _connect(server.port, _client_ctx(_client_opts(pki, "good"))) == b"ok"
    assert _connect(server.port, _client_ctx(_client_opts(pki, "bad"))) != b"ok"
    for _ in range(50):
        if server.errors:
            break
        time.sleep(0.02)
    assert isinstance(server.errors[-1], ssl.SSLCertVerificationError)
    assert server.errors[-1].verify_code == 23  # X509_V_ERR_CERT_REVOKED


def test_without_crlfile_revoked_client_is_accepted(pki, tls_server):
    """Baseline: a CRL only takes effect when ``crlfile`` is configured."""
    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki, crl=False), server_side=True)
    server = tls_server(lambda: reloader.context)
    assert _connect(server.port, _client_ctx(_client_opts(pki, "bad"))) == b"ok"


def test_client_rejects_revoked_server(pki, tls_server):
    server_ctx = salt.transport.base.ssl_context(
        _server_opts(pki, crl=False), server_side=True
    )
    server = tls_server(lambda: server_ctx)
    owner = type("Owner", (), {})()
    opts = _client_opts(pki, crl=True)
    ctx = tls_reload.client_context(owner, opts)
    assert _connect(server.port, ctx) == b"ok"

    _revoke(pki, pki["server"][0])
    ctx = tls_reload.client_context(owner, opts)  # re-checked before connect
    result = _connect(server.port, ctx)
    assert isinstance(result, ssl.SSLCertVerificationError)
    assert result.verify_code == 23


def test_server_picks_up_refreshed_crl_without_restart(pki, tls_server):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    live = reloader.context
    server = tls_server(lambda: reloader.context)
    bad = _client_ctx(_client_opts(pki, "bad"))
    assert _connect(server.port, bad) == b"ok"

    _revoke(pki, pki["bad"][0])
    assert reloader.check() is True
    assert reloader.context is live  # updated in place, socket not rebound
    assert _connect(server.port, bad) != b"ok"
    assert _connect(server.port, _client_ctx(_client_opts(pki, "good"))) == b"ok"

    # A later CRL that no longer lists the certificate (hold released)
    # supersedes the earlier one in the live store.
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(
        _crl(inter, inter_key, number=3, last_update=NOW - HOUR / 2)
    )
    assert reloader.check() is True
    assert _connect(server.port, bad) == b"ok"


@pytest.mark.parametrize(
    "broken",
    ["garbage", "expired", "wrong_signer", "empty"],
)
def test_bad_crl_keeps_last_good_and_logs_once(pki, tls_server, caplog, broken):
    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    server = tls_server(lambda: reloader.context)
    inter, inter_key = pki["inter"]
    if broken == "garbage":
        data = b"-----BEGIN X509 CRL-----\nAAAA\n-----END X509 CRL-----\n"
    elif broken == "expired":
        data = _crl(
            inter, inter_key, number=3, last_update=NOW - 2 * DAY, next_update=NOW - DAY
        )
    elif broken == "wrong_signer":
        _, other_key = _ca("Imposter")
        data = _crl(inter, other_key, number=3)
    else:
        data = b""
    pki["files"]["crl"].write_bytes(data)
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
        assert reloader.check() is False
    errors = [r for r in caplog.records if "rejected" in r.getMessage()]
    assert len(errors) == 1
    assert "CRL" in errors[0].getMessage()
    # Last good CRL still enforced.
    assert _connect(server.port, _client_ctx(_client_opts(pki, "bad"))) != b"ok"
    assert _connect(server.port, _client_ctx(_client_opts(pki, "good"))) == b"ok"


def test_server_rejects_crl_not_newer_than_the_one_in_use(pki, caplog):
    """
    The live server store keeps the CRL with the latest thisUpdate, so a
    changed CRL that is not newer would silently not apply: it is rejected.
    """
    _revoke(pki, pki["bad"][0], number=5)
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    _revoke(pki, number=3)  # older thisUpdate, does not list "bad"
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
    assert any("not newer" in r.getMessage() for r in caplog.records)
    _revoke(pki, number=6)
    assert reloader.check() is True


def test_client_bad_crl_keeps_last_good(pki):
    owner = type("Owner", (), {})()
    opts = _client_opts(pki, crl=True)
    first = tls_reload.client_context(owner, opts)
    pki["files"]["crl"].write_bytes(b"garbage")
    assert tls_reload.client_context(owner, opts) is first


def test_not_yet_valid_crl_is_retried_until_valid(pki, caplog, monkeypatch):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(
        _crl(
            inter, inter_key, revoked=[pki["bad"][0]], number=2, last_update=NOW + HOUR
        )
    )
    monkeypatch.setattr(tls_reload, "_now", lambda: NOW)
    with caplog.at_level(logging.WARNING, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
        assert reloader.check() is False
    pending = [r for r in caplog.records if "not valid yet" in r.getMessage()]
    assert len(pending) == 1
    monkeypatch.setattr(tls_reload, "_now", lambda: NOW + 2 * HOUR)
    assert reloader.check() is True
    assert reloader.check() is False


def test_rotation_to_revoked_own_certificate_is_rejected(pki):
    _revoke(pki, pki["server"][0])
    with pytest.raises(tls_reload.TLSMaterialError, match="revoked"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_rotated_certificate_revoked_by_crl_in_use_is_rejected(pki):
    inter, inter_key = pki["inter"]
    new_server, new_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["localhost"]
    )
    _revoke(pki, new_server)
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    pki["files"]["server"].write_bytes(_pem(new_server, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(new_key))
    assert reloader.check() is False


def test_certificate_rotates_while_crl_refresh_is_broken(pki, tls_server, caplog):
    """A broken CRL refresh keeps the CRL in use but does not block a rotation."""
    _revoke(pki, pki["bad"][0])
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    server = tls_server(lambda: reloader.context)
    inter, inter_key = pki["inter"]
    new_server, new_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["localhost"]
    )
    pki["files"]["server"].write_bytes(_pem(new_server, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(new_key))
    pki["files"]["crl"].write_bytes(
        _crl(
            inter, inter_key, number=3, last_update=NOW - 2 * DAY, next_update=NOW - DAY
        )
    )
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is True
        assert reloader.check() is False
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert "revocation list rejected" in errors[0].getMessage()
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as raw:
        with _client_ctx(_client_opts(pki, "good")).wrap_socket(
            raw, server_hostname="localhost"
        ) as tls:
            served = x509.load_der_x509_certificate(tls.getpeercert(binary_form=True))
            tls.recv(16)
    assert served.serial_number == new_server.serial_number
    # The CRL in use still applies.
    assert _connect(server.port, _client_ctx(_client_opts(pki, "bad"))) != b"ok"


def test_client_certificate_rotates_while_crl_is_not_yet_valid(pki, monkeypatch):
    owner = type("Owner", (), {})()
    opts = _client_opts(pki, crl=True)
    first = tls_reload.client_context(owner, opts)
    inter, inter_key = pki["inter"]
    new_client, new_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    pki["files"]["good"].write_bytes(_pem(new_client, inter))
    pki["files"]["good_key"].write_bytes(_key_pem(new_key))
    pki["files"]["crl"].write_bytes(
        _crl(
            inter,
            inter_key,
            revoked=[pki["server"][0]],
            number=2,
            last_update=NOW + HOUR,
        )
    )
    monkeypatch.setattr(tls_reload, "_now", lambda: NOW)
    second = tls_reload.client_context(owner, opts)
    assert second is not first  # certificate adopted, with the CRL in use
    assert tls_reload.client_context(owner, opts) is second
    monkeypatch.setattr(tls_reload, "_now", lambda: NOW + 2 * HOUR)
    assert owner._tls.check() is True  # pending CRL adopted in place
    assert owner._tls.context is second


def test_crl_refresh_adopted_while_certificate_rotation_is_rejected(
    pki, tls_server, caplog
):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    server = tls_server(lambda: reloader.context)
    _, other_key = _ca("Unrelated")
    pki["files"]["server_key"].write_bytes(_key_pem(other_key))  # mismatched key
    _revoke(pki, pki["bad"][0])
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is True
    assert any(
        "certificate material rejected" in r.getMessage() for r in caplog.records
    )
    assert _connect(server.port, _client_ctx(_client_opts(pki, "bad"))) != b"ok"
    assert _connect(server.port, _client_ctx(_client_opts(pki, "good"))) == b"ok"


def test_client_crl_refresh_is_applied_in_place(pki):
    owner = type("Owner", (), {})()
    opts = _client_opts(pki, crl=True)
    first = tls_reload.client_context(owner, opts)
    _revoke(pki, pki["server"][0])
    assert tls_reload.client_context(owner, opts) is first
    assert len(owner._tls._crls) == 1
    assert owner._tls._crls[0][1].get_revoked_certificate_by_serial_number(
        pki["server"][0].serial_number
    )


def _capath_pki(tmp_path):
    """
    Split PKI: the minion CA is a separate root, trusted by the master only
    through a ``capath`` directory (not ``ca_certs`` / own chain).
    """
    root, root_key = _ca()
    minion_ca, minion_ca_key = _ca("Minion CA")
    server, server_key = _leaf("salt-master", root, root_key, san=["localhost"])
    good, good_key = _leaf("minion-a", minion_ca, minion_ca_key, server=False)
    capath = tmp_path / "capath"
    capath.mkdir()
    (capath / "minion-ca.pem").write_bytes(_pem(minion_ca))  # unhashed copy too
    # OpenSSL looks capath certificates up by subject hash.
    try:
        name_hash = subprocess.run(
            ["openssl", "x509", "-noout", "-subject_hash"],
            input=_pem(minion_ca),
            check=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the openssl binary is needed to hash the capath directory")
    (capath / f"{name_hash.decode()}.0").write_bytes(_pem(minion_ca))
    files = {
        "server": tmp_path / "server.crt",
        "server_key": tmp_path / "server.key",
        "good": tmp_path / "good.crt",
        "good_key": tmp_path / "good.key",
        "root": tmp_path / "root.crt",
        "crl": tmp_path / "minion-ca.crl.pem",
    }
    files["server"].write_bytes(_pem(server))
    files["server_key"].write_bytes(_key_pem(server_key))
    files["good"].write_bytes(_pem(good))
    files["good_key"].write_bytes(_key_pem(good_key))
    files["root"].write_bytes(_pem(root))
    files["crl"].write_bytes(_crl(minion_ca, minion_ca_key))
    server_opts = {
        "certfile": str(files["server"]),
        "keyfile": str(files["server_key"]),
        "verify_locations": [{"capath": str(capath)}],
        "cert_reqs": ssl.CERT_REQUIRED,
        "crlfile": str(files["crl"]),
        "reload_verify_chain": False,
    }
    client_opts = {
        "certfile": str(files["good"]),
        "keyfile": str(files["good_key"]),
        "ca_certs": str(files["root"]),
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    return files, (minion_ca, minion_ca_key), server_opts, client_opts


def test_capath_issuer_verifies_crl_and_impostor_is_rejected(
    tmp_path, tls_server, caplog
):
    files, (minion_ca, minion_ca_key), server_opts, client_opts = _capath_pki(tmp_path)
    reloader = tls_reload.ReloadableTLS(server_opts, server_side=True)
    server = tls_server(lambda: reloader.context)
    assert _connect(server.port, _client_ctx(client_opts)) == b"ok"

    # Correctly signed refresh: the issuer is found in the capath directory.
    files["crl"].write_bytes(
        _crl(minion_ca, minion_ca_key, number=2, last_update=NOW - HOUR / 2)
    )
    assert reloader.check() is True

    # Impostor: right issuer name and AKI, wrong key, newer thisUpdate.
    _, impostor_key = _ca("Impostor")
    forged = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(minion_ca.subject)
        .last_update(NOW - HOUR / 4)
        .next_update(NOW + DAY)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                minion_ca_key.public_key()
            ),
            False,
        )
        .add_extension(x509.CRLNumber(3), False)
        .sign(impostor_key, hashes.SHA256())
        .public_bytes(serialization.Encoding.PEM)
    )
    files["crl"].write_bytes(forged)
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
    assert any("not signed by its issuer" in r.getMessage() for r in caplog.records)
    assert _connect(server.port, _client_ctx(client_opts)) == b"ok"


def test_crl_with_unknown_issuer_is_rejected(pki, caplog):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    stranger, stranger_key = _ca("Stranger CA")
    pki["files"]["crl"].write_bytes(_crl(stranger, stranger_key, number=2))
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        assert reloader.check() is False
    assert any("cannot verify the signature" in r.getMessage() for r in caplog.records)


def test_crl_issuer_found_in_multi_certificate_bundle(pki, tmp_path):
    root, _ = pki["root"]
    inter, inter_key = pki["inter"]
    bundle = tmp_path / "bundle.crt"
    bundle.write_bytes(pki["files"]["crl"].read_bytes() + _pem(root, inter))
    leaf_only = tmp_path / "server-leaf.crt"
    leaf_only.write_bytes(_pem(pki["server"][0]))
    opts = _server_opts(
        pki, ca_certs=str(bundle), certfile=str(leaf_only), reload_verify_chain=False
    )
    certs = tls_reload._issuer_candidates(opts, True)
    assert inter.subject in [c.subject for c in certs]
    tls_reload.validate_crls(opts, True)


def test_older_crl_accepted_when_crl_in_use_expired(pki):
    """An expired CRL in use loses to any current one in OpenSSL: no 'not newer'."""
    inter, inter_key = pki["inter"]
    expired = x509.load_pem_x509_crl(
        _crl(
            inter,
            inter_key,
            number=9,
            last_update=NOW - HOUR / 2,
            next_update=NOW - HOUR / 4,
        )
    )
    current = x509.load_pem_x509_crl(
        _crl(inter, inter_key, number=2, last_update=NOW - HOUR)
    )
    tls_reload._check_crls_supersede([("new", current)], [("old", expired)], NOW)
    with pytest.raises(tls_reload.TLSMaterialError, match="not newer"):
        tls_reload._check_crls_supersede(
            [("new", current)],
            [
                (
                    "old",
                    x509.load_pem_x509_crl(
                        _crl(inter, inter_key, number=9, last_update=NOW - HOUR / 2)
                    ),
                )
            ],
            NOW,
        )


@pytest.mark.parametrize("server_side", [True, False])
def test_probe_ignores_crls_that_do_not_cover_own_issuer(pki, tmp_path, server_side):
    """
    The CRLs are for peers.  One that does not cover the CA of the daemon's
    own certificate (and the probe's throwaway identity, which has no CRL at
    all) must not fail validation with "unable to get certificate CRL".
    """
    root, root_key = pki["root"]
    root_crl = tmp_path / "root-only.crl.pem"
    root_crl.write_bytes(_crl(root, root_key))
    if server_side:
        opts = _server_opts(pki, crlfile=str(root_crl))
    else:
        opts = _client_opts(pki, crlfile=str(root_crl))
    for flags in ([], ["VERIFY_CRL_CHECK_CHAIN"]):
        opts["verify_flags"] = flags
        tls_reload.validate_material(opts, server_side=server_side)


def test_crl_files_are_watched_and_snapshotted(pki, tmp_path):
    opts = _server_opts(pki)
    assert str(pki["files"]["crl"]) in tls_reload._watched_paths(opts, True)
    before = tls_reload.fingerprint(opts, True)
    _revoke(pki, pki["bad"][0])
    assert tls_reload.fingerprint(opts, True) != before
    with tls_reload._Snapshot(opts, True) as snap:
        (copy,) = snap.options["crlfile"]
        assert copy != str(pki["files"]["crl"])
        assert copy.startswith(snap.tmpdir)


def test_startup_with_expired_crl_logs_error(pki, caplog):
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(
        _crl(inter, inter_key, last_update=NOW - 2 * DAY, next_update=NOW - DAY)
    )
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    assert any("failed validation" in r.getMessage() for r in caplog.records)


def test_startup_with_not_yet_valid_crl_warns(pki, caplog):
    inter, inter_key = pki["inter"]
    pki["files"]["crl"].write_bytes(_crl(inter, inter_key, last_update=NOW + HOUR))
    with caplog.at_level(logging.WARNING, logger="salt.transport.tls_reload"):
        tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    (record,) = [r for r in caplog.records if "not valid yet" in r.getMessage()]
    assert record.levelno == logging.WARNING
    assert "becomes valid at" in record.getMessage()


def test_loaded_crl_expiry_is_logged_once(pki, caplog):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    assert len(reloader._crls) == 1
    # The CRL in use passes its nextUpdate without a replacement.
    inter, inter_key = pki["inter"]
    reloader._crls = [
        (
            "issuing.crl.pem",
            x509.load_pem_x509_crl(
                _crl(inter, inter_key, last_update=NOW - DAY, next_update=NOW - HOUR)
            ),
        )
    ]
    with caplog.at_level(logging.ERROR, logger="salt.transport.tls_reload"):
        reloader.check()
        reloader.check()
    expired = [r for r in caplog.records if "expired at" in r.getMessage()]
    assert len(expired) == 1
