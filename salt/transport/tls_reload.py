"""
Hot reload of TLS certificates for the ``tcp`` and ``ws`` transports.

Certificates rotate far more often than Salt daemons restart.  :class:`ReloadableTLS`
owns an :class:`ssl.SSLContext` for one role (server or client), watches the
files named in the ``ssl`` configuration and, when they change, *validates*
the new material before it is adopted:

* the certificate and key must load and belong together
* the leaf certificate must be valid for the current time
* when verification is enabled (``cert_reqs`` other than ``CERT_NONE``) the
  leaf must verify -- with OpenSSL, exactly as its peers will verify it --
  against the configured trust anchors (``ca_certs`` / ``verify_locations``),
  or against the default trust store when none is pinned.  With verification
  disabled a self-signed certificate is accepted as long as it is time-valid.
  Deployments whose own certificate is issued by a *different* CA than the
  one in ``ca_certs`` (split server/client PKIs) set
  ``reload_verify_chain: False`` to keep only the first two checks.
* certificate revocation lists named by ``crlfile`` must parse, be current
  (``thisUpdate`` <= now <= ``nextUpdate``), be newer than the CRL in use
  and be signed by their issuer, whose certificate must be among the trust
  anchors or in the daemon's own chain.  A CRL that is not valid *yet*
  (clock skew between the CA and this host) is retried on every poll
  instead of being rejected for good.  CRLs and the other material are
  validated and adopted independently, and a rotated certificate must not
  be revoked by the CRLs in use.

The files are snapshotted into a private directory first; the snapshot is
what gets fingerprinted, validated and loaded, so the bytes that passed
validation are the bytes that go live.  Material that fails validation is
logged once and ignored; the previously loaded context stays in use so a
botched rotation never takes the transport down.  For CRLs this means "keep
the last good CRL": OpenSSL still rejects every peer once that CRL itself
passes its ``nextUpdate``, which is logged at ERROR level.
"""

import datetime
import hashlib
import logging
import os
import re
import shutil
import ssl
import tempfile

import salt.transport.base
import salt.utils.asynchronous

log = logging.getLogger(__name__)

DEFAULT_RELOAD_INTERVAL = 60
_FILE_KEYS = ("certfile", "keyfile", "client_certfile", "client_keyfile", "ca_certs")
_PROBE_NAME = "salt-tls-reload-probe"
_CRL_FLAGS = ("VERIFY_CRL_CHECK_LEAF", "VERIFY_CRL_CHECK_CHAIN")
_CERT_PEM = re.compile(
    rb"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.DOTALL
)


class TLSMaterialError(Exception):
    """Rotated certificate material failed validation."""


class TLSMaterialNotYetValid(TLSMaterialError):
    """
    The material is not valid *yet* (a freshly issued CRL whose ``thisUpdate``
    is ahead of this host's clock).  Re-checked on the next poll instead of
    being rejected until the files change again.
    """


def _watched_paths(ssl_options, server_side):
    """Return the files (and CA directories) whose change triggers a reload."""
    paths = []
    for key in _FILE_KEYS:
        if key.startswith("client_") and server_side:
            continue
        if ssl_options.get(key):
            paths.append(ssl_options[key])
    for location in salt.transport.base._explicit_trust_locations(ssl_options):
        if "cafile" in location:
            if location["cafile"] not in paths:
                paths.append(location["cafile"])
        elif "capath" in location:
            paths.append(location["capath"])
    for path in salt.transport.base._crl_paths(ssl_options):
        if path not in paths:
            paths.append(path)
    return paths


def _hash_path(digest, path, content_path=None):
    """
    Feed ``digest`` with the configured ``path`` and the content found at
    ``content_path`` (defaults to ``path``; a snapshot passes its copy so the
    digest describes the copied bytes under the original name).
    """
    if content_path is None:
        content_path = path
    digest.update(path.encode("utf-8", "surrogateescape"))
    digest.update(b"\0")
    try:
        if os.path.isdir(content_path):
            for name in sorted(os.listdir(content_path)):
                st = os.stat(os.path.join(content_path, name))
                digest.update(f"{name}:{st.st_mtime_ns}:{st.st_size}".encode())
        else:
            with open(content_path, "rb") as fh:  # pylint: disable=resource-leakage
                digest.update(fh.read())
    except OSError as exc:
        digest.update(f"<missing:{exc.errno}>".encode())
    digest.update(b"\0")


def _anchor_digest(ssl_options):
    """
    Hash the *content* of the configured trust anchors (independent of the
    path they are read from, so a snapshot copy hashes like the original).
    """
    digest = hashlib.sha256()
    for location in salt.transport.base._explicit_trust_locations(ssl_options):
        path = location.get("cafile") or location.get("capath")
        if path:
            _hash_path(digest, "", path)
    return digest.hexdigest()


def fingerprint(ssl_options, server_side):
    """
    Hash the content of every watched file (and the listing + mtimes of every
    CA directory).  Missing files hash to a marker so a half-written rotation
    is noticed and re-checked once the file is back.
    """
    digest = hashlib.sha256()
    for path in _watched_paths(ssl_options, server_side):
        _hash_path(digest, path)
    return digest.hexdigest()


def _crl_only_paths(ssl_options):
    """``crlfile`` entries that are not also certificate/key/CA files."""
    return set(salt.transport.base._crl_paths(ssl_options)) - {
        ssl_options.get(key) for key in _FILE_KEYS
    }


def _part_fingerprints(ssl_options, server_side):
    """
    ``(material, crl)`` fingerprints: like :func:`fingerprint` but split into
    the CRLs and everything else (matches ``_Snapshot``'s split).
    """
    crl_only = _crl_only_paths(ssl_options)
    parts = {True: hashlib.sha256(), False: hashlib.sha256()}
    for path in _watched_paths(ssl_options, server_side):
        _hash_path(parts[path in crl_only], path)
    return parts[False].hexdigest(), parts[True].hexdigest()


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class _Snapshot:
    """
    Private copies of the watched files.

    ``options`` is ``ssl_options`` with every file path rewritten to its copy
    (CA *directories* and ``cadata`` are left as they are).  ``fingerprint``
    is computed from the copies, so it describes exactly the bytes that are
    validated and loaded -- a rotation tool rewriting the originals halfway
    through cannot slip unvalidated material past the check.

    ``crl_fingerprint`` covers only the ``crlfile`` CRLs and
    ``material_fingerprint`` everything else, so a CRL refresh and a
    certificate rotation can be validated and adopted independently.
    """

    def __init__(self, ssl_options, server_side):
        self.tmpdir = tempfile.mkdtemp(prefix="salt-tls-")  # created 0700
        self.options = dict(ssl_options)
        self._copies = {}
        crl_only = _crl_only_paths(ssl_options)
        digest = hashlib.sha256()
        parts = {True: hashlib.sha256(), False: hashlib.sha256()}
        try:
            for path in _watched_paths(ssl_options, server_side):
                part = parts[path in crl_only]
                if os.path.isdir(path):
                    _hash_path(digest, path)
                    _hash_path(part, path)
                    continue
                copy, error = self._copy(path)
                for dig in (digest, part):
                    if copy is None:
                        dig.update(path.encode("utf-8", "surrogateescape"))
                        dig.update(b"\0")
                        dig.update(f"<missing:{error.errno}>".encode())
                        dig.update(b"\0")
                    else:
                        _hash_path(dig, path, content_path=copy)
            for key in _FILE_KEYS:
                if self.options.get(key) in self._copies:
                    self.options[key] = self._copies[self.options[key]]
            if self.options.get("verify_locations"):
                rewritten = []
                for entry in self.options["verify_locations"]:
                    if isinstance(entry, dict):
                        entry = {
                            k: (self._copies.get(v, v) if k.lower() == "cafile" else v)
                            for k, v in entry.items()
                        }
                    else:
                        entry = self._copies.get(entry, entry)
                    rewritten.append(entry)
                self.options["verify_locations"] = rewritten
            if self.options.get("crlfile"):
                self.options["crlfile"] = [
                    self._copies.get(path, path)
                    for path in salt.transport.base._crl_paths(ssl_options)
                ]
        except Exception:
            self.cleanup()
            raise
        self.fingerprint = digest.hexdigest()
        self.crl_fingerprint = parts[True].hexdigest()
        self.material_fingerprint = parts[False].hexdigest()

    def with_crls(self, crl_pems):
        """
        ``options`` with ``crlfile`` pointing at copies of ``crl_pems`` (the
        CRL bytes still in use) instead of the CRLs found on disk.
        """
        options = dict(self.options)
        if not salt.transport.base._crl_paths(options):
            return options
        if not crl_pems:
            # No good CRL to fall back to: stay fail closed (peers are
            # refused with "unable to get certificate CRL").
            options["crlfile"] = []
            options["verify_flags"] = list(options.get("verify_flags") or ()) + [
                "VERIFY_CRL_CHECK_LEAF"
            ]
            return options
        paths = []
        for index, data in enumerate(crl_pems):
            path = os.path.join(self.tmpdir, f"in-use-{index}.crl.pem")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            paths.append(path)
        options["crlfile"] = paths
        return options

    def _copy(self, path):
        """Copy ``path`` into the snapshot; returns ``(copy, None)`` or ``(None, error)``."""
        try:
            with open(path, "rb") as fh:  # pylint: disable=resource-leakage
                data = fh.read()
        except OSError as exc:
            # Missing file: leave the original path so validation reports
            # the real error; the caller records the gap in the fingerprint.
            return None, exc
        copy = os.path.join(
            self.tmpdir, f"{len(self._copies)}-{os.path.basename(path)}"
        )
        fd = os.open(copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        self._copies[path] = copy
        return copy, None

    def describe(self, message):
        """Replace copy paths in ``message`` with the configured originals."""
        for original, copy in self._copies.items():
            message = message.replace(copy, original)
        return message

    def cleanup(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cleanup()


def _read_pem_chain(path):
    from cryptography import x509

    with open(path, "rb") as fh:  # pylint: disable=resource-leakage
        data = fh.read()
    certs = x509.load_pem_x509_certificates(data)
    return certs[0], certs[1:]


def _server_name(ssl_options):
    """
    Name a rotated *server* certificate has to be valid for: the pinned
    ``ssl.server_hostname``, else ``None``.

    Nothing else is authoritative here: the daemon does not know which name
    its peers verify, and a name taken from the certificate itself would
    make the check circular (any certificate matches its own SAN).  Without
    a pin the chain, validity and purpose are verified but the identity is
    not, and that is logged.
    """
    pinned = ssl_options.get("server_hostname")
    if pinned:
        return pinned
    log.debug(
        "Rotated server certificate identity not checked: set ssl.server_hostname "
        "to verify the name peers expect"
    )
    return None


def _trust_only_options(ssl_options):
    """
    ``ssl_options`` reduced to its trust/verification settings.  ``ciphers``
    is deliberately dropped: the probe peer uses a throwaway key and must not
    be failed by an operator cipher list meant for the real peers.

    Revocation checking is dropped as well (``crlfile`` and the
    ``VERIFY_CRL_CHECK_*`` flags).  The CRLs configured here are the ones
    this daemon applies to its *peers*; they need not cover the CA that
    issued the daemon's own certificate, and the probe's throwaway identity
    has no CRL at all, so an OpenSSL CRL check in the probe would reject
    sound material with "unable to get certificate CRL".  Whether the
    daemon's own certificate is revoked is checked directly against the
    configured CRLs instead (see :func:`_check_not_revoked`).
    """
    keep = ("ca_certs", "verify_locations", "verify_flags", "ssl_version")
    opts = {key: ssl_options[key] for key in keep if key in ssl_options}
    if opts.get("verify_flags"):
        opts["verify_flags"] = [
            flag for flag in opts["verify_flags"] if flag.upper() not in _CRL_FLAGS
        ]
    opts["cert_reqs"] = ssl.CERT_REQUIRED
    return opts


def _ephemeral_server_identity(like_public_key):
    """
    A throwaway self-signed server certificate + key (PEM bytes) with the same
    key algorithm as ``like_public_key``.  Used only as the peer when a
    rotated *client* certificate is test-verified; the probing client does
    not verify it, so it never has to be trusted by anything.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

    if isinstance(like_public_key, rsa.RSAPublicKey):
        key = rsa.generate_private_key(65537, 2048)
        algorithm = hashes.SHA256()
    elif isinstance(like_public_key, ed25519.Ed25519PublicKey):
        key = ed25519.Ed25519PrivateKey.generate()
        algorithm = None
    elif isinstance(like_public_key, ed448.Ed448PublicKey):
        key = ed448.Ed448PrivateKey.generate()
        algorithm = None
    elif isinstance(like_public_key, ec.EllipticCurvePublicKey):
        key = ec.generate_private_key(like_public_key.curve)
        algorithm = hashes.SHA256()
    else:
        key = ec.generate_private_key(ec.SECP256R1())
        algorithm = hashes.SHA256()
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, _PROBE_NAME)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(_PROBE_NAME)]), False)
        .sign(key, algorithm)
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )


def _handshake(server_ctx, client_ctx, server_hostname):
    """
    Drive an in-memory TLS handshake between the two contexts.  Raises
    :class:`ssl.SSLError` (typically ``SSLCertVerificationError``) from the
    side whose verification failed.

    Both sides are pumped until both report completion.  Under TLS 1.3 the
    client finishes first and a rejected client certificate surfaces as an
    exception from the *server's* ``do_handshake()`` inside this loop.
    """
    c2s, s2c = ssl.MemoryBIO(), ssl.MemoryBIO()
    server = server_ctx.wrap_bio(c2s, s2c, server_side=True)
    client = client_ctx.wrap_bio(s2c, c2s, server_hostname=server_hostname)
    pending = {client, server}
    for _ in range(64):
        for side in list(pending):
            try:
                side.do_handshake()
            except ssl.SSLWantReadError:
                continue
            pending.discard(side)
        if not pending:
            return
    raise TLSMaterialError("TLS handshake did not complete")


def _verify_with_openssl(
    ssl_options, server_side, certfile, keyfile, leaf, server_name
):
    """
    Verify the rotated certificate the way its real peers will: with OpenSSL,
    against the configured trust anchors and ``verify_flags``.

    * server role: a verifying client (trust anchors, CERT_REQUIRED, hostname
      check against ``server_name`` when one is pinned) must accept the new
      server certificate.
    * client role: a verifying server (trust anchors, CERT_REQUIRED) must
      accept the new client certificate; the server identity it presents is a
      throwaway self-signed certificate the probing client does not check.
    """
    trust = _trust_only_options(ssl_options)
    if server_side:
        probe_server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        probe_server.load_cert_chain(certfile, keyfile)
        probe_client = salt.transport.base.ssl_context(trust, server_side=False)
        if server_name is None:
            # No pinned name: chain, validity and purpose only.
            probe_client.check_hostname = False
            server_name = _PROBE_NAME
        _handshake(probe_server, probe_client, server_name)
        return

    probe_client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    probe_client.check_hostname = False
    probe_client.verify_mode = ssl.CERT_NONE
    probe_client.load_cert_chain(certfile, keyfile)
    probe_server = salt.transport.base.ssl_context(trust, server_side=True)
    cert_pem, key_pem = _ephemeral_server_identity(leaf.public_key())
    tmp = tempfile.mkdtemp(prefix="salt-tls-probe-")
    try:
        ident = os.path.join(tmp, "probe.pem")
        fd = os.open(ident, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key_pem)
            fh.write(cert_pem)
        probe_server.load_cert_chain(ident)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _handshake(probe_server, probe_client, _PROBE_NAME)


def _pem_certificates(data):
    """Every parseable PEM certificate in ``data`` (other PEM blocks ignored)."""
    from cryptography import x509

    certs = []
    for block in _CERT_PEM.findall(data):
        try:
            certs.append(x509.load_pem_x509_certificate(block))
        except ValueError:
            continue
    return certs


def _der_certificates(data):
    """The certificates of concatenated DER ``data`` (as ``cadata`` takes it)."""
    from cryptography import x509

    certs = []
    offset = 0
    while offset + 2 <= len(data) and data[offset] == 0x30:  # SEQUENCE
        length = data[offset + 1]
        header = 2
        if length & 0x80:
            octets = length & 0x7F
            header += octets
            length = int.from_bytes(data[offset + 2 : offset + header], "big")
        end = offset + header + length
        try:
            certs.append(x509.load_der_x509_certificate(data[offset:end]))
        except ValueError:
            break
        offset = end
    return certs


def _issuer_candidates(ssl_options, server_side):
    """
    Certificates that may have signed a configured CRL: every trust anchor
    (``ca_certs`` and ``verify_locations`` bundles, the files of ``capath``
    directories, PEM or DER ``cadata``) plus the certificates of the daemon's
    own certificate chain.  Unreadable files are skipped; they are reported
    by the regular checks.
    """
    files = []
    certs = []
    for location in salt.transport.base._explicit_trust_locations(ssl_options):
        if "cafile" in location:
            files.append(location["cafile"])
        elif "capath" in location:
            capath = location["capath"]
            try:
                names = sorted(os.listdir(capath))
            except OSError:
                continue
            files.extend(
                os.path.join(capath, name)
                for name in names
                if os.path.isfile(os.path.join(capath, name))
            )
        elif "cadata" in location:
            data = location["cadata"]
            if isinstance(data, str):
                certs.extend(_pem_certificates(data.encode("ascii", "ignore")))
            else:
                certs.extend(_der_certificates(bytes(data)))
    certfile = ssl_options.get("certfile")
    if not server_side and ssl_options.get("client_certfile"):
        certfile = ssl_options["client_certfile"]
    if certfile:
        files.append(certfile)
    for path in files:
        try:
            with open(path, "rb") as fh:  # pylint: disable=resource-leakage
                certs.extend(_pem_certificates(fh.read()))
        except OSError:
            continue
    return certs


def load_crls(ssl_options):
    """
    Parse every certificate revocation list named by ``crlfile``.

    Returns a list of ``(path, crl)``.  Raises :class:`TLSMaterialError` when
    a file cannot be read or holds anything but parseable PEM CRLs.
    """
    from cryptography import x509

    crls = []
    for path in salt.transport.base._crl_paths(ssl_options):
        try:
            with open(path, "rb") as fh:  # pylint: disable=resource-leakage
                data = fh.read()
        except OSError as exc:
            raise TLSMaterialError(f"cannot read CRL file {path}: {exc}") from exc
        try:
            blocks = salt.transport.base._crl_pem_blocks(data, path)
        except ValueError as exc:
            raise TLSMaterialError(str(exc)) from exc
        crls.extend((path, x509.load_pem_x509_crl(block)) for block in blocks)
    return crls


def _signed_by(crl, cert):
    try:
        return crl.is_signature_valid(cert.public_key())
    except (TypeError, ValueError):  # unsupported key type
        return False


def _check_crls(crls, issuers, now):
    """
    Each CRL must be current and signed by its issuer, whose certificate has
    to be among ``issuers``.  The signature check is mandatory: CRLs are
    added to a live context, so a forged CRL that made it in would refuse
    every peer of that CA until restart.  A CRL that is not valid yet raises
    :class:`TLSMaterialNotYetValid` so the caller retries it.
    """
    for path, crl in crls:
        issuer = crl.issuer.rfc4514_string()
        this_update = crl.last_update_utc
        next_update = crl.next_update_utc
        if now < this_update:
            raise TLSMaterialNotYetValid(
                f"the CRL in {path} for {issuer} becomes valid at "
                f"{this_update.isoformat()} (now {now.isoformat()})"
            )
        if next_update is not None and now > next_update:
            raise TLSMaterialError(
                f"the CRL in {path} for {issuer} expired at "
                f"{next_update.isoformat()} (now {now.isoformat()})"
            )
        candidates = [cert for cert in issuers if cert.subject == crl.issuer]
        if not candidates:
            raise TLSMaterialError(
                f"cannot verify the signature of the CRL in {path}: its issuer "
                f"{issuer} is not among the trust anchors (ca_certs, "
                "verify_locations including capath directories) or the "
                "daemon's own certificate chain; add the issuer certificate "
                "to verify_locations"
            )
        if not any(_signed_by(crl, cert) for cert in candidates):
            raise TLSMaterialError(
                f"the CRL in {path} is not signed by its issuer {issuer}"
            )


def _check_crls_supersede(crls, in_use, now):
    """
    CRLs are loaded into live contexts, whose stores only grow, and OpenSSL
    uses the current CRL with the latest ``thisUpdate`` of each issuer.  A
    changed CRL that is older than a *current* CRL in use for the same
    issuer (a rollback, or a re-issue within the same second) would silently
    not take effect: reject it.  An in-use CRL that has expired loses to any
    current one, so it does not count.
    """
    from cryptography.hazmat.primitives import serialization

    der = serialization.Encoding.DER
    in_use_der = {crl.public_bytes(der) for _, crl in in_use}
    latest = {}
    for _, crl in in_use:
        if crl.next_update_utc is not None and now > crl.next_update_utc:
            continue
        best = latest.get(crl.issuer)
        if best is None or crl.last_update_utc > best.last_update_utc:
            latest[crl.issuer] = crl
    for path, crl in crls:
        best = latest.get(crl.issuer)
        if best is None or crl.last_update_utc > best.last_update_utc:
            continue
        if crl.public_bytes(der) in in_use_der:
            continue  # unchanged
        raise TLSMaterialError(
            f"the CRL in {path} for {crl.issuer.rfc4514_string()} (thisUpdate "
            f"{crl.last_update_utc.isoformat()}) is not newer than the current "
            f"CRL in use (thisUpdate {best.last_update_utc.isoformat()}); the "
            "running daemon would keep using the CRL in use"
        )


def validate_crls(ssl_options, server_side, now=None, in_use=()):
    """
    Load and check the ``crlfile`` CRLs.  Returns ``[(path, crl), ...]``.
    ``in_use`` are the ``(path, crl)`` already loaded into the live context.
    """
    if now is None:
        now = _now()
    crls = load_crls(ssl_options)
    if crls:
        _check_crls(crls, _issuer_candidates(ssl_options, server_side), now)
        _check_crls_supersede(crls, in_use, now)
    return crls


def _own_leaf(ssl_options, server_side):
    """The certificate this role presents, or ``None`` (best effort)."""
    certfile = ssl_options.get("certfile")
    if not server_side and ssl_options.get("client_certfile"):
        certfile = ssl_options["client_certfile"]
    if not certfile:
        return None
    try:
        return _read_pem_chain(certfile)[0]
    except (OSError, ValueError, IndexError):
        return None


def _check_not_revoked(certfile, leaf, crls):
    """The daemon's own certificate must not be listed in a configured CRL."""
    for path, crl in crls:
        if crl.issuer != leaf.issuer:
            continue
        if crl.get_revoked_certificate_by_serial_number(leaf.serial_number):
            raise TLSMaterialError(
                f"{certfile} (serial {leaf.serial_number:x}) is revoked by the "
                f"CRL in {path}"
            )


def validate_material(ssl_options, server_side, now=None, crls=None):
    """
    Build a fresh context from ``ssl_options`` and check the certificate the
    given role would present.  Returns the new :class:`ssl.SSLContext`.

    ``crls`` are the already validated ``(path, crl)`` the context will use;
    when ``None`` the ``crlfile`` CRLs are loaded and validated here.

    Raises :class:`TLSMaterialError` when the material must not be adopted.
    Synchronous and short (file reads, one in-memory handshake); callers on an
    event loop should expect single-digit milliseconds, more for RSA probes.
    """
    if now is None:
        now = _now()
    if crls is None:
        crls = validate_crls(ssl_options, server_side, now)

    try:
        context = salt.transport.base.ssl_context(ssl_options, server_side=server_side)
    except (ssl.SSLError, OSError, ValueError) as exc:
        raise TLSMaterialError(f"certificate material does not load: {exc}") from exc

    certfile = ssl_options.get("certfile")
    keyfile = ssl_options.get("keyfile")
    if not server_side and ssl_options.get("client_certfile"):
        certfile = ssl_options["client_certfile"]
        keyfile = ssl_options.get("client_keyfile")
    if not certfile:
        return context

    try:
        leaf, _ = _read_pem_chain(certfile)
    except ImportError as exc:  # pragma: no cover - cryptography is a hard dependency
        raise TLSMaterialError(
            "cryptography is required to validate rotated certificates"
        ) from exc
    except (OSError, ValueError) as exc:
        raise TLSMaterialError(f"cannot parse {certfile}: {exc}") from exc

    not_before = leaf.not_valid_before_utc
    not_after = leaf.not_valid_after_utc
    if now < not_before:
        raise TLSMaterialError(
            f"{certfile} is not valid before {not_before.isoformat()} (now {now.isoformat()})"
        )
    if now > not_after:
        raise TLSMaterialError(
            f"{certfile} expired at {not_after.isoformat()} (now {now.isoformat()})"
        )
    _check_not_revoked(certfile, leaf, crls)

    if context.verify_mode == ssl.CERT_NONE:
        # Verification disabled by the operator: a time-valid (possibly
        # self-signed) certificate is all that is required.
        return context
    if not ssl_options.get("reload_verify_chain", True):
        # Split PKI: our own certificate is not issued by the CA we trust for
        # peers, so a chain check against ``ca_certs`` is meaningless.
        return context

    server_name = _server_name(ssl_options) if server_side else None
    try:
        _verify_with_openssl(
            ssl_options, server_side, certfile, keyfile, leaf, server_name
        )
    except ssl.SSLError as exc:
        reason = getattr(exc, "verify_message", None) or exc.strerror or str(exc)
        raise TLSMaterialError(
            f"{certfile} does not verify against the configured trust anchors: {reason}"
        ) from exc
    return context


class ReloadableTLS:
    """
    An :class:`ssl.SSLContext` that follows certificate rotation on disk.

    ``context`` is the live context.  Server-side it is updated *in place* so
    the listening socket (tornado ``TCPServer`` / asyncio ``create_server``)
    serves the rotated certificate to new connections without being rebound.
    Client-side a brand-new context is built, which also drops trust anchors
    that were removed from ``ca_certs``.  (Server-side, removed anchors stay
    trusted until restart: OpenSSL cannot unload them from a live store.)
    """

    def __init__(self, ssl_options, server_side):
        if server_side not in (True, False):
            raise ValueError("server_side must be True or False")
        self.ssl_options = ssl_options
        self.server_side = server_side
        self.interval = ssl_options.get("reload_interval", DEFAULT_RELOAD_INTERVAL)
        self.context = salt.transport.base.ssl_context(
            ssl_options, server_side=server_side
        )
        self._fingerprint = fingerprint(ssl_options, server_side)
        self._material_fp, self._crl_fp = _part_fingerprints(ssl_options, server_side)
        self._anchors = _anchor_digest(ssl_options)
        # Overall fingerprint whose processing failed unexpectedly.
        self._rejected = None
        self._material_rejected = None
        self._crl_rejected = None
        self._crl_pending = None
        self._crls = []  # (path, crl) loaded into the live context
        self._crl_pems = []  # bytes of the crlfile files in use
        self._crls_expired_logged = set()
        self._leaf = _own_leaf(ssl_options, server_side)
        if salt.transport.base._crl_paths(ssl_options):
            self._startup_crls(ssl_options)
        self._handle = None
        self._loop = None

    def _startup_crls(self, ssl_options):
        """
        Check the CRLs loaded at startup.  They are in use whatever the
        outcome (there is no previous CRL to fall back to); a CRL that is
        not current makes OpenSSL reject the affected peers, so say so.
        """
        for path in salt.transport.base._crl_paths(ssl_options):
            try:
                with open(path, "rb") as fh:  # pylint: disable=resource-leakage
                    self._crl_pems.append(fh.read())
            except OSError:
                pass
        try:
            self._crls = load_crls(ssl_options)
            _check_crls(
                self._crls, _issuer_candidates(ssl_options, self.server_side), _now()
            )
        except TLSMaterialNotYetValid as exc:
            log.warning(
                "Configured certificate revocation list is not valid yet; peers "
                "of the affected CA are rejected until then: %s",
                exc,
            )
        except TLSMaterialError as exc:
            log.error(
                "Configured certificate revocation list failed validation: %s. "
                "It is in use anyway (there is no earlier CRL to fall back to): "
                "OpenSSL refuses every peer it cannot check against a current, "
                "correctly signed CRL until ssl.crlfile is fixed",
                exc,
            )

    def _check_crl_expiry(self, now):
        """Log once when a loaded CRL passes its nextUpdate without replacement."""
        for _, crl in self._crls:
            issuer = crl.issuer.rfc4514_string()
            next_update = crl.next_update_utc
            if next_update is None or now <= next_update:
                continue
            if (issuer, next_update) in self._crls_expired_logged:
                continue
            self._crls_expired_logged.add((issuer, next_update))
            log.error(
                "The certificate revocation list for %s expired at %s and no "
                "valid replacement has been loaded: every peer certificate "
                "issued by that CA is rejected until ssl.crlfile is refreshed",
                issuer,
                next_update.isoformat(),
            )

    @property
    def watched(self):
        return _watched_paths(self.ssl_options, self.server_side)

    @property
    def enabled(self):
        """Whether background polling makes sense: an interval and files to watch."""
        return bool(self.interval) and self.interval > 0 and bool(self.watched)

    def check(self):
        """
        Compare the watched files with what is loaded.  Returns ``True`` when
        new, valid material (certificates or CRLs) was adopted.
        """
        if not self.watched:
            return False
        now = _now()
        if self._crls:
            self._check_crl_expiry(now)
        try:
            current = fingerprint(self.ssl_options, self.server_side)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Unable to fingerprint TLS files: %s", exc)
            return False

        def settled(fp):
            # Unchanged (or already reported) and no CRL waiting to become valid.
            return fp == self._rejected or (
                fp == self._fingerprint and self._crl_pending is None
            )

        if settled(current):
            return False
        role = "server" if self.server_side else "client"
        try:
            with _Snapshot(self.ssl_options, self.server_side) as snapshot:
                if settled(snapshot.fingerprint):
                    return False
                adopted = self._process(snapshot, role, now)
                self._fingerprint = snapshot.fingerprint
        except Exception as exc:  # pylint: disable=broad-except
            log.error(
                "Unexpected error validating rotated TLS %s material, keeping "
                "the current certificate: %s",
                role,
                exc,
                exc_info=True,
            )
            self._rejected = current
            return False
        self._rejected = None
        return adopted

    def _process(self, snapshot, role, now):
        """
        Validate and adopt the CRLs and the rest of the material separately:
        a broken CRL refresh does not hold back a valid certificate rotation
        (it is adopted with the CRLs in use), and a rejected certificate
        rotation does not hold back a valid CRL refresh.
        """
        new_crls = None
        if snapshot.crl_fingerprint != self._crl_fp:
            try:
                new_crls = validate_crls(
                    snapshot.options, self.server_side, now, in_use=self._crls
                )
            except TLSMaterialNotYetValid as exc:
                if self._crl_pending != snapshot.crl_fingerprint:
                    log.warning(
                        "Refreshed TLS %s certificate revocation list is not "
                        "valid yet, keeping the CRL in use and re-checking: %s",
                        role,
                        snapshot.describe(str(exc)),
                    )
                self._crl_pending = snapshot.crl_fingerprint
            except TLSMaterialError as exc:
                if self._crl_rejected != snapshot.crl_fingerprint:
                    log.error(
                        "Refreshed TLS %s certificate revocation list rejected, "
                        "keeping the CRL in use: %s",
                        role,
                        snapshot.describe(str(exc)),
                    )
                self._crl_rejected = snapshot.crl_fingerprint
                self._crl_pending = None

        material_adopted = False
        if snapshot.material_fingerprint not in (
            self._material_fp,
            self._material_rejected,
        ):
            if new_crls is not None:
                options, crls = snapshot.options, new_crls
            else:
                options, crls = snapshot.with_crls(self._crl_pems), self._crls
            try:
                candidate = validate_material(
                    options, self.server_side, now=now, crls=crls
                )
            except TLSMaterialError as exc:
                log.error(
                    "Rotated TLS %s certificate material rejected, keeping the "
                    "current certificate: %s",
                    role,
                    snapshot.describe(str(exc)),
                )
                self._material_rejected = snapshot.material_fingerprint
            else:
                try:
                    self._adopt(candidate, options, load_crls=new_crls is not None)
                except (ssl.SSLError, OSError, ValueError) as exc:
                    log.error(
                        "Validated TLS %s material could not be applied, keeping "
                        "the current certificate: %s",
                        role,
                        snapshot.describe(str(exc)),
                    )
                    self._material_rejected = snapshot.material_fingerprint
                    if new_crls is not None and not self.server_side:
                        new_crls = None  # the client context was not replaced
                else:
                    material_adopted = True
                    self._leaf = _own_leaf(snapshot.options, self.server_side)
                    self._material_fp = snapshot.material_fingerprint
                    self._material_rejected = None
                    log.info("Reloaded rotated TLS %s certificate material", role)

        crls_adopted = False
        if new_crls is not None:
            try:
                if not material_adopted:
                    # Added to the live context in place, on both sides.
                    salt.transport.base._load_crl_files(
                        self.context,
                        salt.transport.base._crl_paths(snapshot.options),
                    )
            except (ssl.SSLError, OSError, ValueError) as exc:
                log.error(
                    "Validated TLS %s certificate revocation list could not be "
                    "applied, keeping the CRL in use: %s",
                    role,
                    snapshot.describe(str(exc)),
                )
                self._crl_rejected = snapshot.crl_fingerprint
            else:
                crls_adopted = True
                self._crls = [(snapshot.describe(p), crl) for p, crl in new_crls]
                self._crl_pems = []
                for path in salt.transport.base._crl_paths(snapshot.options):
                    with open(path, "rb") as fh:  # pylint: disable=resource-leakage
                        self._crl_pems.append(fh.read())
                self._crl_fp = snapshot.crl_fingerprint
                self._crl_rejected = self._crl_pending = None
                log.info("Reloaded TLS %s certificate revocation list", role)
                self._warn_if_own_certificate_revoked()
        return material_adopted or crls_adopted

    def _warn_if_own_certificate_revoked(self):
        """
        A refreshed CRL is the CA's word and is adopted even when it revokes
        this daemon's own certificate, but peers checking that CRL now refuse
        this daemon: say so.
        """
        leaf = self._leaf
        if leaf is None:
            return
        for path, crl in self._crls:
            if crl.issuer != leaf.issuer:
                continue
            if crl.get_revoked_certificate_by_serial_number(leaf.serial_number):
                log.error(
                    "The certificate revocation list just loaded from %s revokes "
                    "this daemon's own TLS %s certificate (serial %x): peers "
                    "checking that CRL refuse it; rotate the certificate",
                    path,
                    "server" if self.server_side else "client",
                    leaf.serial_number,
                )

    def _adopt(self, candidate, options, load_crls=True):
        if not self.server_side:
            self.context = candidate
            return
        # Trust anchors first (additive), certificate last: if the anchors
        # cannot be loaded nothing has changed yet.
        anchors = _anchor_digest(options)
        if anchors != self._anchors:
            # Loading into the live store only ever ADDS anchors; one that
            # was removed from the configuration (retired or compromised CA)
            # stays trusted by this process until restart. Say so where an
            # operator handling that rotation will see it.
            log.warning(
                "TLS server trust anchors changed on rotation: new anchors are "
                "trusted now, anchors removed from the configuration stay "
                "trusted until this process restarts"
            )
        for location in salt.transport.base._explicit_trust_locations(options):
            self.context.load_verify_locations(**location)
        if load_crls:
            # Only genuinely new CRLs are added.  OpenSSL uses the most
            # recent current CRL of each issuer; superseded ones stay in
            # memory until restart.
            salt.transport.base._load_crl_files(
                self.context, salt.transport.base._crl_paths(options)
            )
        self._anchors = anchors
        if options.get("certfile"):
            self.context.load_cert_chain(options["certfile"], options.get("keyfile"))

    # -- periodic polling ------------------------------------------------

    def start(self, io_loop):
        """Poll for rotation every ``reload_interval`` seconds on ``io_loop``."""
        if not self.enabled or self._handle is not None:
            return
        self._loop = salt.utils.asynchronous.aioloop(io_loop)
        self._handle = self._loop.call_later(self.interval, self._tick)

    def _tick(self):
        self._handle = None
        try:
            self.check()
        finally:
            if self._loop is not None and not self._loop.is_closed():
                self._handle = self._loop.call_later(self.interval, self._tick)

    def stop(self):
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._loop = None


def client_context(owner, ssl_options, io_loop=None):
    """
    Return the (re)validated client :class:`ssl.SSLContext` for ``owner``.

    Clients build a context per connection attempt, so this caches one
    :class:`ReloadableTLS` on ``owner`` (``owner._tls``) and re-checks the
    files before every connect: rotated, valid material is used for the new
    connection, rejected material is reported once and the current context is
    kept.  With ``io_loop`` the files are also polled every
    ``reload_interval`` seconds (unless ``0``) so a rotation is validated and
    logged when it happens rather than at the next reconnect.  Owners must
    call :func:`stop_polling` from their ``close()``.
    """
    reloader = getattr(owner, "_tls", None)
    if reloader is None or reloader.ssl_options is not ssl_options:
        if reloader is not None:
            reloader.stop()
        reloader = ReloadableTLS(ssl_options, server_side=False)
        owner._tls = reloader  # pylint: disable=protected-access
    else:
        reloader.check()
    if io_loop is not None:
        try:
            reloader.start(io_loop)
        except RuntimeError as exc:
            log.debug("Not polling TLS files for %r: %s", owner, exc)
    return reloader.context


def stop_polling(owner):
    """Cancel the rotation poller cached on ``owner`` (if any)."""
    reloader = getattr(owner, "_tls", None)
    if reloader is not None:
        reloader.stop()
