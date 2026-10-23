"""
Unit tests for salt.transport.tls_reload: certificate rotation without a
restart, gated on validation of the new material.
"""

import asyncio
import datetime
import logging
import pathlib
import ssl

import pytest

import salt.transport.tls_reload as tls_reload
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]

x509 = pytest.importorskip("cryptography.x509")
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: E402

NOW = datetime.datetime.now(datetime.timezone.utc)
DAY = datetime.timedelta(days=1)


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _ca(cn="Example Corp Root CA", issuer=None, issuer_key=None, path_length=1):
    key = _key()
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(issuer.subject if issuer is not None else _name(cn))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - DAY)
        .not_valid_after(NOW + 30 * DAY)
        .add_extension(x509.BasicConstraints(ca=True, path_length=path_length), True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False
        )
    )
    if issuer is not None:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            False,
        )
    cert = builder.sign(issuer_key or key, hashes.SHA256())
    return cert, key


def _leaf(
    cn,
    issuer,
    issuer_key,
    *,
    server=True,
    san=None,
    not_before=None,
    not_after=None,
    self_signed=False,
):
    key = _key()
    eku = [
        ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH
    ]
    issuer_name = _name(cn) if self_signed else issuer.subject
    sign_key = key if self_signed else issuer_key
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(cn))
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before or NOW - DAY)
        .not_valid_after(not_after or NOW + 10 * DAY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            True,
        )
        .add_extension(x509.ExtendedKeyUsage(eku), False)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False
        )
        # OpenSSL >= 3.6 refuses to build a chain for a leaf without an
        # Authority Key Identifier ("Missing Authority Key Identifier").
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(sign_key.public_key()),
            False,
        )
    )
    if san:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(n) for n in san]), False
        )
    return builder.sign(sign_key, hashes.SHA256()), key


def _pem(*certs):
    return b"".join(c.public_bytes(serialization.Encoding.PEM) for c in certs)


def _key_pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


@pytest.fixture
def pki(tmp_path):
    """Root -> intermediate -> server + client leaves, written as files."""
    root, root_key = _ca()
    inter, inter_key = _ca("Example Corp Issuing CA", root, root_key, path_length=0)
    server, server_key = _leaf(
        "salt-master.corp.example",
        inter,
        inter_key,
        san=["salt-master.corp.example", "localhost"],
    )
    client, client_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    files = {
        "root": tmp_path / "root.crt",
        "inter": tmp_path / "inter.crt",
        "server": tmp_path / "server.chain.crt",
        "server_key": tmp_path / "server.key",
        "client": tmp_path / "client.chain.crt",
        "client_key": tmp_path / "client.key",
    }
    files["root"].write_bytes(_pem(root))
    files["inter"].write_bytes(_pem(inter))
    files["server"].write_bytes(_pem(server, inter))
    files["server_key"].write_bytes(_key_pem(server_key))
    files["client"].write_bytes(_pem(client, inter))
    files["client_key"].write_bytes(_key_pem(client_key))
    return {
        "files": files,
        "root": (root, root_key),
        "inter": (inter, inter_key),
        "server": (server, server_key),
        "client": (client, client_key),
    }


def _server_opts(pki, **extra):
    f = pki["files"]
    opts = {
        "certfile": str(f["server"]),
        "keyfile": str(f["server_key"]),
        "ca_certs": str(f["root"]),
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    opts.update(extra)
    return opts


def _client_opts(pki, **extra):
    f = pki["files"]
    opts = {
        "certfile": str(f["client"]),
        "keyfile": str(f["client_key"]),
        "ca_certs": str(f["root"]),
        "cert_reqs": ssl.CERT_REQUIRED,
    }
    opts.update(extra)
    return opts


def _served_serial(server_ctx, client_ctx, server_hostname="salt-master.corp.example"):
    """Run an in-memory handshake and return the serial the server presented."""
    s_in, s_out = ssl.MemoryBIO(), ssl.MemoryBIO()
    server = server_ctx.wrap_bio(s_in, s_out, server_side=True)
    client = client_ctx.wrap_bio(s_out, s_in, server_hostname=server_hostname)
    for _ in range(20):
        for side in (client, server):
            try:
                side.do_handshake()
            except ssl.SSLWantReadError:
                pass
        try:
            client.do_handshake()
            server.do_handshake()
            break
        except ssl.SSLWantReadError:
            continue
    der = client.getpeercert(binary_form=True)
    return x509.load_der_x509_certificate(der).serial_number


# -- validate_material -------------------------------------------------------


def test_validate_material_accepts_valid_chain_server(pki):
    ctx = tls_reload.validate_material(_server_opts(pki), server_side=True)
    assert isinstance(ctx, ssl.SSLContext)


def test_validate_material_accepts_valid_chain_client(pki):
    ctx = tls_reload.validate_material(_client_opts(pki), server_side=False)
    assert isinstance(ctx, ssl.SSLContext)


def test_validate_material_rejects_mismatched_key(pki):
    opts = _server_opts(pki, keyfile=str(pki["files"]["client_key"]))
    with pytest.raises(tls_reload.TLSMaterialError, match="does not load"):
        tls_reload.validate_material(opts, server_side=True)


def test_validate_material_rejects_expired(pki):
    inter, inter_key = pki["inter"]
    expired, key = _leaf(
        "salt-master.corp.example",
        inter,
        inter_key,
        san=["salt-master.corp.example"],
        not_before=NOW - 10 * DAY,
        not_after=NOW - DAY,
    )
    pki["files"]["server"].write_bytes(_pem(expired, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="expired"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_validate_material_rejects_not_yet_valid(pki):
    inter, inter_key = pki["inter"]
    future, key = _leaf(
        "salt-master.corp.example",
        inter,
        inter_key,
        san=["salt-master.corp.example"],
        not_before=NOW + DAY,
        not_after=NOW + 10 * DAY,
    )
    pki["files"]["server"].write_bytes(_pem(future, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="not valid before"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_validate_material_rejects_untrusted_issuer_when_verifying(pki):
    """A cert from a *different* PKI must not be adopted while verification is on."""
    rogue, rogue_key = _ca("Rogue CA")
    leaf, key = _leaf(
        "salt-master.corp.example", rogue, rogue_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server"].write_bytes(_pem(leaf, rogue))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_validate_material_rejects_missing_intermediate(pki):
    """Leaf without its intermediate cannot chain to the root-only anchor."""
    server, _ = pki["server"]
    pki["files"]["server"].write_bytes(_pem(server))
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_validate_material_rejects_wrong_eku_for_role(pki):
    """A serverAuth-only certificate is not acceptable as a client certificate."""
    opts = _client_opts(
        pki,
        certfile=str(pki["files"]["server"]),
        keyfile=str(pki["files"]["server_key"]),
    )
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(opts, server_side=False)


def test_validate_material_server_uses_pinned_server_hostname(pki):
    opts = _server_opts(pki, server_hostname="localhost")
    tls_reload.validate_material(opts, server_side=True)
    opts = _server_opts(pki, server_hostname="other.corp.example")
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(opts, server_side=True)


def test_validate_material_self_signed_accepted_without_verification(pki):
    """Verification off: a time-valid self-signed certificate is fine."""
    leaf, key = _leaf("salt-master", None, None, san=["salt-master"], self_signed=True)
    pki["files"]["server"].write_bytes(_pem(leaf))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    opts = {
        "certfile": str(pki["files"]["server"]),
        "keyfile": str(pki["files"]["server_key"]),
        "cert_reqs": ssl.CERT_NONE,
    }
    tls_reload.validate_material(opts, server_side=True)
    tls_reload.validate_material(opts, server_side=False)


def test_validate_material_self_signed_rejected_with_verification(pki):
    leaf, key = _leaf("salt-master", None, None, san=["salt-master"], self_signed=True)
    pki["files"]["server"].write_bytes(_pem(leaf))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(_server_opts(pki), server_side=True)


def test_validate_material_expired_self_signed_rejected_without_verification(pki):
    """Verification off still requires time validity."""
    leaf, key = _leaf(
        "salt-master",
        None,
        None,
        san=["salt-master"],
        self_signed=True,
        not_before=NOW - 10 * DAY,
        not_after=NOW - DAY,
    )
    pki["files"]["server"].write_bytes(_pem(leaf))
    pki["files"]["server_key"].write_bytes(_key_pem(key))
    opts = {
        "certfile": str(pki["files"]["server"]),
        "keyfile": str(pki["files"]["server_key"]),
        "cert_reqs": ssl.CERT_NONE,
    }
    with pytest.raises(tls_reload.TLSMaterialError, match="expired"):
        tls_reload.validate_material(opts, server_side=True)


def test_validate_material_client_certfile_is_what_gets_checked(pki):
    opts = _server_opts(
        pki,
        client_certfile=str(pki["files"]["client"]),
        client_keyfile=str(pki["files"]["client_key"]),
    )
    # Server role: the serverAuth certfile is validated.
    tls_reload.validate_material(opts, server_side=True)
    # Client role: the clientAuth client_certfile is validated.
    tls_reload.validate_material(opts, server_side=False)


# -- ReloadableTLS -----------------------------------------------------------


def test_reloadable_tls_no_change_no_reload(pki):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    assert reloader.check() is False


def test_reloadable_tls_server_rotation_served_in_place(pki):
    """
    After rotating certfile/keyfile the *same* context object (held by the
    listening server) presents the new certificate.
    """
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    live_ctx = reloader.context
    client_ctx = tls_reload.validate_material(_client_opts(pki), server_side=False)
    old_serial = pki["server"][0].serial_number
    assert _served_serial(live_ctx, client_ctx) == old_serial

    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server"].write_bytes(_pem(new_leaf, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(new_key))

    assert reloader.check() is True
    assert reloader.context is live_ctx
    assert _served_serial(live_ctx, client_ctx) == new_leaf.serial_number
    assert reloader.check() is False


def test_reloadable_tls_rejected_rotation_keeps_old_and_logs_once(pki, caplog):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    live_ctx = reloader.context
    client_ctx = tls_reload.validate_material(_client_opts(pki), server_side=False)
    old_serial = pki["server"][0].serial_number

    rogue, rogue_key = _ca("Rogue CA")
    leaf, key = _leaf(
        "salt-master.corp.example", rogue, rogue_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server"].write_bytes(_pem(leaf, rogue))
    pki["files"]["server_key"].write_bytes(_key_pem(key))

    with caplog.at_level("ERROR", logger="salt.transport.tls_reload"):
        assert reloader.check() is False
        assert reloader.check() is False
    errors = [r for r in caplog.records if "rejected" in r.getMessage()]
    assert len(errors) == 1
    # The operator sees the configured path, not the snapshot copy.
    assert str(pki["files"]["server"]) in errors[0].getMessage()
    assert "salt-tls-" not in errors[0].getMessage()
    assert _served_serial(live_ctx, client_ctx) == old_serial

    # Fixing the files afterwards is picked up.
    inter, inter_key = pki["inter"]
    good, good_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server"].write_bytes(_pem(good, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(good_key))
    assert reloader.check() is True
    assert _served_serial(live_ctx, client_ctx) == good.serial_number


def test_reloadable_tls_half_written_rotation_is_rejected_then_recovers(pki):
    """Key rotated first, cert not yet: pair mismatch is rejected, not adopted."""
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server_key"].write_bytes(_key_pem(new_key))
    assert reloader.check() is False
    pki["files"]["server"].write_bytes(_pem(new_leaf, inter))
    assert reloader.check() is True


def test_reloadable_tls_client_rotation_builds_new_context(pki):
    reloader = tls_reload.ReloadableTLS(_client_opts(pki), server_side=False)
    first = reloader.context
    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    pki["files"]["client"].write_bytes(_pem(new_leaf, inter))
    pki["files"]["client_key"].write_bytes(_key_pem(new_key))
    assert reloader.check() is True
    assert reloader.context is not first


def test_reloadable_tls_ca_rotation_client_drops_old_anchor(pki):
    reloader = tls_reload.ReloadableTLS(_client_opts(pki), server_side=False)
    assert len(reloader.context.get_ca_certs()) == 1
    other, _ = _ca("Other Root CA")
    pki["files"]["root"].write_bytes(_pem(pki["root"][0], other))
    assert reloader.check() is True
    assert len(reloader.context.get_ca_certs()) == 2


def test_reloadable_tls_enabled_requires_interval_and_files(pki):
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    assert reloader.enabled is True
    reloader.interval = 0
    assert reloader.enabled is False
    # ``ssl: True`` -> {} : nothing to watch, nothing to poll
    empty = tls_reload.ReloadableTLS({"cert_reqs": ssl.CERT_NONE}, server_side=False)
    assert empty.enabled is False
    assert empty.check() is False


def test_reloadable_tls_start_schedules_on_asyncio_loop(pki):
    reloader = tls_reload.ReloadableTLS(
        _server_opts(pki, reload_interval=7), server_side=True
    )
    loop = asyncio.new_event_loop()
    try:
        reloader.start(loop)
        handle = reloader._handle
        assert handle is not None
        reloader.start(loop)  # idempotent
        assert reloader._handle is handle
        reloader._tick()  # a tick re-arms the timer
        assert reloader._handle is not None and reloader._handle is not handle
        reloader.stop()
        assert reloader._handle is None
    finally:
        loop.close()


def test_reloadable_tls_start_disabled_does_nothing(pki):
    reloader = tls_reload.ReloadableTLS(
        _server_opts(pki, reload_interval=0), server_side=True
    )
    loop = asyncio.new_event_loop()
    try:
        reloader.start(loop)
        assert reloader._handle is None
    finally:
        loop.close()


def test_client_context_helper_reuses_and_rechecks(pki):
    owner = MagicMock(spec=[])
    opts = _client_opts(pki)
    ctx1 = tls_reload.client_context(owner, opts)
    ctx2 = tls_reload.client_context(owner, opts)
    assert ctx1 is ctx2
    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    pki["files"]["client"].write_bytes(_pem(new_leaf, inter))
    pki["files"]["client_key"].write_bytes(_key_pem(new_key))
    ctx3 = tls_reload.client_context(owner, opts)
    assert ctx3 is not ctx1


def test_reloadable_tls_client_ca_rotation_drops_removed_anchor(pki):
    """Client contexts are rebuilt, so an anchor removed from ca_certs is gone."""
    other, _ = _ca("Other Root CA")
    pki["files"]["root"].write_bytes(_pem(pki["root"][0], other))
    reloader = tls_reload.ReloadableTLS(_client_opts(pki), server_side=False)
    assert len(reloader.context.get_ca_certs()) == 2
    pki["files"]["root"].write_bytes(_pem(pki["root"][0]))
    assert reloader.check() is True
    assert len(reloader.context.get_ca_certs()) == 1


def test_reloadable_tls_server_adopt_loads_anchors_before_certificate(pki, caplog):
    """If the new anchors cannot be loaded the live certificate is untouched."""
    reloader = tls_reload.ReloadableTLS(_server_opts(pki), server_side=True)
    live_ctx = reloader.context
    calls = []
    real_load_verify_locations = ssl.SSLContext.load_verify_locations
    real_load_cert_chain = ssl.SSLContext.load_cert_chain

    def load_verify_locations(self, *args, **kwargs):
        if self is live_ctx:
            calls.append("anchors")
            raise ssl.SSLError("bad anchor file")
        return real_load_verify_locations(self, *args, **kwargs)

    def load_cert_chain(self, *args, **kwargs):
        if self is live_ctx:
            calls.append("cert")
        return real_load_cert_chain(self, *args, **kwargs)

    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf(
        "salt-master.corp.example", inter, inter_key, san=["salt-master.corp.example"]
    )
    pki["files"]["server"].write_bytes(_pem(new_leaf, inter))
    pki["files"]["server_key"].write_bytes(_key_pem(new_key))
    with patch.object(
        ssl.SSLContext, "load_verify_locations", load_verify_locations
    ), patch.object(
        ssl.SSLContext, "load_cert_chain", load_cert_chain
    ), caplog.at_level(
        "ERROR", logger="salt.transport.tls_reload"
    ):
        assert reloader.check() is False
    # Anchors were attempted first and the certificate was never touched.
    assert calls == ["anchors"]
    applied = [r for r in caplog.records if "could not be applied" in r.getMessage()]
    assert len(applied) == 1
    assert "salt-tls-" not in applied[0].getMessage()
    client_ctx = tls_reload.validate_material(_client_opts(pki), server_side=False)
    assert _served_serial(live_ctx, client_ctx) == pki["server"][0].serial_number
    # Same (bad) files again: already reported, no second attempt.
    assert reloader.check() is False
    assert calls == ["anchors"]


def test_snapshot_missing_file_is_fingerprinted_once(pki):
    opts = _server_opts(pki)
    pki["files"]["root"].unlink()
    live = tls_reload.fingerprint(opts, server_side=True)
    with tls_reload._Snapshot(opts, server_side=True) as snap:
        assert snap.fingerprint == live
        # the missing file keeps its original path for validation to report
        assert snap.options["ca_certs"] == opts["ca_certs"]
    with pytest.raises(tls_reload.TLSMaterialError, match="does not load"):
        tls_reload.validate_material(snap.options, server_side=True)


def test_reloadable_tls_reload_verify_chain_opt_out(pki):
    """Split PKI: with reload_verify_chain False only pair + time are checked."""
    rogue, rogue_key = _ca("Client Issuing CA")
    leaf, key = _leaf("minion-a.corp.example", rogue, rogue_key, server=False)
    pki["files"]["client"].write_bytes(_pem(leaf, rogue))
    pki["files"]["client_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="does not verify"):
        tls_reload.validate_material(_client_opts(pki), server_side=False)
    tls_reload.validate_material(
        _client_opts(pki, reload_verify_chain=False), server_side=False
    )
    expired, key = _leaf(
        "minion-a.corp.example",
        rogue,
        rogue_key,
        server=False,
        not_before=NOW - 10 * DAY,
        not_after=NOW - DAY,
    )
    pki["files"]["client"].write_bytes(_pem(expired, rogue))
    pki["files"]["client_key"].write_bytes(_key_pem(key))
    with pytest.raises(tls_reload.TLSMaterialError, match="expired"):
        tls_reload.validate_material(
            _client_opts(pki, reload_verify_chain=False), server_side=False
        )


def test_validate_material_rsa_leaf_probe(pki):
    """The probe identity follows the leaf's key algorithm (RSA here)."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    inter, inter_key = pki["inter"]
    key = rsa.generate_private_key(65537, 2048)
    leaf = (
        x509.CertificateBuilder()
        .subject_name(_name("minion-rsa.corp.example"))
        .issuer_name(inter.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOW - DAY)
        .not_valid_after(NOW + DAY)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(inter_key.public_key()),
            False,
        )
        .sign(inter_key, hashes.SHA256())
    )
    pki["files"]["client"].write_bytes(_pem(leaf, inter))
    pki["files"]["client_key"].write_bytes(_key_pem(key))
    tls_reload.validate_material(_client_opts(pki), server_side=False)


def test_snapshot_rewrites_paths_and_fingerprints_copies(pki, tmp_path):
    capath = tmp_path / "capath"
    capath.mkdir()
    (capath / "extra.crt").write_bytes(_pem(_ca("Extra CA")[0]))
    opts = _server_opts(pki, verify_locations=[{"capath": str(capath)}])
    with tls_reload._Snapshot(opts, server_side=True) as snap:
        assert snap.options["certfile"] != opts["certfile"]
        assert snap.options["certfile"].startswith(snap.tmpdir)
        assert snap.options["ca_certs"].startswith(snap.tmpdir)
        # directories are watched (listing + mtimes) but not copied
        assert snap.options["verify_locations"] == [{"capath": str(capath)}]
        assert (
            pathlib.Path(snap.options["certfile"]).read_bytes()
            == pki["files"]["server"].read_bytes()
        )
        assert snap.fingerprint == tls_reload.fingerprint(opts, server_side=True)
        tmpdir = snap.tmpdir
    assert not pathlib.Path(tmpdir).exists()
    # a change inside the CA directory changes the fingerprint
    (capath / "extra2.crt").write_bytes(_pem(_ca("Extra CA 2")[0]))
    assert tls_reload.fingerprint(opts, server_side=True) != snap.fingerprint


def test_client_context_polls_and_stop_polling_cancels(pki):
    owner = MagicMock(spec=[])
    opts = _client_opts(pki, reload_interval=30)
    loop = asyncio.new_event_loop()
    try:
        tls_reload.client_context(owner, opts, loop)
        assert owner._tls._handle is not None
        tls_reload.stop_polling(owner)
        assert owner._tls._handle is None
        tls_reload.stop_polling(MagicMock(spec=[]))  # no reloader: no-op
    finally:
        loop.close()


def test_client_context_checks_on_connect_even_when_polling_disabled(pki):
    owner = MagicMock(spec=[])
    opts = _client_opts(pki, reload_interval=0)
    first = tls_reload.client_context(owner, opts)
    inter, inter_key = pki["inter"]
    new_leaf, new_key = _leaf("minion-a.corp.example", inter, inter_key, server=False)
    pki["files"]["client"].write_bytes(_pem(new_leaf, inter))
    pki["files"]["client_key"].write_bytes(_key_pem(new_key))
    assert tls_reload.client_context(owner, opts) is not first


def test_server_name_is_the_pin_or_nothing(caplog):
    """
    A rotated server certificate's identity is checked against a pinned
    ``ssl.server_hostname`` only; a name taken from the certificate itself
    would match trivially.
    """
    assert (
        tls_reload._server_name({"server_hostname": "salt-master.corp.example"})
        == "salt-master.corp.example"
    )
    with caplog.at_level(logging.DEBUG, logger="salt.transport.tls_reload"):
        assert tls_reload._server_name({}) is None
    assert "identity not checked" in caplog.text


def test_adopt_warns_when_server_trust_anchors_change(tmp_path, caplog):
    old = tmp_path / "ca-old.crt"
    old.write_bytes(b"OLD ANCHORS")
    same = tmp_path / "ca-copy.crt"
    same.write_bytes(b"OLD ANCHORS")  # a snapshot copy: same bytes, other path
    new = tmp_path / "ca-new.crt"
    new.write_bytes(b"NEW ANCHORS")

    reloader = tls_reload.ReloadableTLS.__new__(tls_reload.ReloadableTLS)
    reloader.server_side = True
    reloader.context = MagicMock()
    reloader._anchors = tls_reload._anchor_digest({"ca_certs": str(old)})

    with caplog.at_level(logging.WARNING, logger="salt.transport.tls_reload"):
        reloader._adopt(MagicMock(), {"ca_certs": str(same)})
        assert "trust anchors changed" not in caplog.text
        reloader._adopt(MagicMock(), {"ca_certs": str(new)})
    assert "trust anchors changed" in caplog.text
    assert "stay trusted until this process restarts" in caplog.text
    assert reloader.context.load_verify_locations.call_count == 2
    assert reloader._anchors == tls_reload._anchor_digest({"ca_certs": str(new)})


def test_client_context_stops_a_replaced_poller():
    class Owner:
        pass

    owner = Owner()
    previous = MagicMock()
    previous.ssl_options = {"certfile": "/old"}
    owner._tls = previous
    with patch.object(tls_reload, "ReloadableTLS") as reloadable:
        reloadable.return_value.context = "new-context"
        assert tls_reload.client_context(owner, {"certfile": "/new"}) == "new-context"
    previous.stop.assert_called_once_with()
    assert owner._tls is reloadable.return_value
