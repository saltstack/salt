"""
Functional tests for :class:`salt.crypt.MasterIdentityKey` and the
minion-side auth-response ``cluster_id`` injection hook.

Exercises the thin reader/writer on real on-disk PKI directories:

* ``generate()`` returns valid RSA PEM bytes parseable by
  :class:`salt.crypt.PublicKey` and :class:`salt.crypt.PrivateKey`.
* ``write()`` + ``load()`` round-trip is byte-exact.
* File permissions after ``write()``: private is 0400, public is 0444.
* ``exists()`` is False before the first write, True after both files
  land on disk.
* ``write()`` is idempotent: a second write with the same bytes does
  not change the file's mtime.
* ``fingerprint()`` is stable across calls and uses
  ``opts["hash_type"]``.

Plus the minion auth-response hook in
:meth:`AsyncAuth.handle_signin_response`: when the master's response
carries ``cluster_id`` and the minion has ``topology_enabled`` +
``topology_push_cluster_grain``, the resulting ``auth`` dict exposes
``cluster_id``.  When either opt is False, the field is absent.
"""

import os
import stat
import time

import pytest

import salt.crypt
import salt.payload

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.slow_test,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pki_dir(tmp_path):
    """
    Isolated ``pki_dir`` with a ``master/`` subdir, mirroring the
    on-disk layout the RFC specifies for master-identity keys.
    """
    root = tmp_path / "pki"
    (root / "master").mkdir(parents=True)
    return root


@pytest.fixture
def opts(pki_dir):
    """
    Minimal master opts dict carrying the fields
    :class:`MasterIdentityKey` reads: ``pki_dir``, ``hash_type``,
    ``keysize``.
    """
    return {
        "pki_dir": str(pki_dir),
        "hash_type": "sha256",
        "keysize": 2048,
    }


@pytest.fixture
def identity_key(opts):
    """A fresh :class:`MasterIdentityKey` bound to the per-test opts."""
    return salt.crypt.MasterIdentityKey(opts)


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


def test_generate_returns_bytes_tuple(identity_key):
    """generate() returns a (pub_pem, priv_pem) tuple of bytes."""
    pub, priv = identity_key.generate()
    assert isinstance(pub, bytes)
    assert isinstance(priv, bytes)
    assert pub.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert priv.startswith(b"-----BEGIN RSA PRIVATE KEY-----") or priv.startswith(
        b"-----BEGIN PRIVATE KEY-----"
    )


def test_generate_pub_parseable_by_publickey(identity_key):
    """The pub PEM generate() returns must load via PublicKey.from_str."""
    pub, _priv = identity_key.generate()
    pk = salt.crypt.PublicKey.from_str(pub)
    assert pk.key is not None


def test_generate_priv_parseable_by_privatekey(identity_key):
    """The priv PEM generate() returns must load via PrivateKey.from_str."""
    _pub, priv = identity_key.generate()
    sk = salt.crypt.PrivateKey.from_str(priv)
    assert sk.key is not None


def test_generate_default_keysize_at_least_2048(identity_key):
    """The default generated key must be >= 2048 bits."""
    pub, _priv = identity_key.generate()
    pk = salt.crypt.PublicKey.from_str(pub)
    assert pk.key.key_size >= 2048


# ---------------------------------------------------------------------------
# write() + load() round-trip
# ---------------------------------------------------------------------------


def test_write_then_load_roundtrip(identity_key):
    """load() returns byte-exact the pub/priv pair most recently written."""
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    loaded_pub, loaded_priv = identity_key.load()
    assert loaded_pub == pub
    assert loaded_priv == priv


def test_write_creates_files_at_expected_paths(identity_key, pki_dir):
    """
    The on-disk filenames are ``master_identity.pub`` and
    ``master_identity.pem`` under ``pki_dir/master/``.
    """
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    assert (pki_dir / "master" / "master_identity.pub").is_file()
    assert (pki_dir / "master" / "master_identity.pem").is_file()


def test_load_raises_when_absent(identity_key):
    """load() must raise when no keypair has been written."""
    with pytest.raises((FileNotFoundError, OSError)):
        identity_key.load()


# ---------------------------------------------------------------------------
# File permissions
# ---------------------------------------------------------------------------


@pytest.mark.skip_on_windows(reason="POSIX file-mode semantics only")
def test_write_sets_private_perm_0400(identity_key, pki_dir):
    """master_identity.pem is written with mode 0400."""
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    priv_path = pki_dir / "master" / "master_identity.pem"
    mode = stat.S_IMODE(os.stat(priv_path).st_mode)
    assert mode == 0o400, f"expected 0400, got {mode:o}"


@pytest.mark.skip_on_windows(reason="POSIX file-mode semantics only")
def test_write_sets_public_perm_0444(identity_key, pki_dir):
    """master_identity.pub is written with mode 0444."""
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    pub_path = pki_dir / "master" / "master_identity.pub"
    mode = stat.S_IMODE(os.stat(pub_path).st_mode)
    assert mode == 0o444, f"expected 0444, got {mode:o}"


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------


def test_exists_false_before_write(identity_key):
    """exists() returns False before any key is written."""
    assert identity_key.exists() is False


def test_exists_true_after_write(identity_key):
    """exists() returns True once both files are on disk."""
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    assert identity_key.exists() is True


def test_exists_false_when_only_pub_present(identity_key, pki_dir):
    """
    exists() is True only when *both* files are present; a lone pub
    (operator cleanup gone wrong) must not report present.
    """
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    (pki_dir / "master" / "master_identity.pem").unlink()
    assert identity_key.exists() is False


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.skip_on_windows(reason="mtime stability requires POSIX semantics")
def test_write_idempotent_mtime_unchanged(identity_key, pki_dir):
    """
    A second write() with the same bytes is a no-op: the on-disk mtime
    of neither file changes.
    """
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    priv_path = pki_dir / "master" / "master_identity.pem"
    pub_path = pki_dir / "master" / "master_identity.pub"
    first_priv_mtime = os.stat(priv_path).st_mtime_ns
    first_pub_mtime = os.stat(pub_path).st_mtime_ns

    # Sleep long enough that any filesystem would record a new mtime
    # if the write actually re-touched the file.
    time.sleep(1.1)

    identity_key.write(pub, priv)
    assert os.stat(priv_path).st_mtime_ns == first_priv_mtime
    assert os.stat(pub_path).st_mtime_ns == first_pub_mtime


def test_write_rotates_when_bytes_differ(identity_key):
    """
    Writing a different pub/priv pair replaces the on-disk key; the
    second load() reflects the new bytes.
    """
    pub1, priv1 = identity_key.generate()
    identity_key.write(pub1, priv1)
    pub2, priv2 = identity_key.generate()
    assert (pub1, priv1) != (pub2, priv2)
    identity_key.write(pub2, priv2)
    loaded_pub, loaded_priv = identity_key.load()
    assert loaded_pub == pub2
    assert loaded_priv == priv2


# ---------------------------------------------------------------------------
# fingerprint()
# ---------------------------------------------------------------------------


def test_fingerprint_stable_across_calls(identity_key):
    """fingerprint() returns the same value on repeat calls."""
    pub, priv = identity_key.generate()
    identity_key.write(pub, priv)
    f1 = identity_key.fingerprint()
    f2 = identity_key.fingerprint()
    assert f1 == f2
    assert isinstance(f1, str)
    assert f1  # non-empty


def test_fingerprint_changes_on_rotation(identity_key):
    """A new keypair has a different fingerprint."""
    pub1, priv1 = identity_key.generate()
    identity_key.write(pub1, priv1)
    f1 = identity_key.fingerprint()

    pub2, priv2 = identity_key.generate()
    identity_key.write(pub2, priv2)
    f2 = identity_key.fingerprint()

    assert f1 != f2


# ---------------------------------------------------------------------------
# Minion auth-response: cluster_id injection
# ---------------------------------------------------------------------------
#
# AsyncAuth.handle_signin_response() receives the master's clear-signed
# payload and builds the per-connection ``auth`` dict.  The topology
# hook mirrors the pattern already used for ``publish_port``: pull
# ``cluster_id`` from the response into ``auth`` when both
# ``topology_enabled`` and ``topology_push_cluster_grain`` are truthy.
#
# These tests drive handle_signin_response() with a synthetic
# clear-signed envelope.  The master-pub path on disk is intentionally
# left absent so signature verification is skipped; the inner payload
# omits ``pub_key`` so verify_master() is skipped; no ``ret`` is set so
# the retry/full branches are skipped.  Everything the real method
# needs to reach the publish_port / cluster_id lines is driven from
# the inner dict.


def _build_minion_opts(topology_enabled, topology_push_cluster_grain, pki_dir):
    """Return a minion opts dict covering handle_signin_response's reads."""
    return {
        "pki_dir": str(pki_dir),
        "master_uri": "tcp://127.0.0.1:4506",
        "hash_type": "sha256",
        "encryption_algorithm": "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA1",
        "acceptance_wait_time": 10,
        "rejected_retry": False,
        "topology_enabled": topology_enabled,
        "topology_push_cluster_grain": topology_push_cluster_grain,
    }


class _MinionAuthHarness:
    """
    Minimal object exposing just enough surface for
    AsyncAuth.handle_signin_response: ``opts``, ``mpub``, and the bound
    method under test.  Everything else the method touches is
    inert in the branches the inner-payload shape selects.
    """

    # Point at a file that does NOT exist, so the method's
    # ``if os.path.exists(master_pubkey_path)`` check skips signature
    # verification entirely.
    mpub = "master.pub_does_not_exist"

    def __init__(self, opts):
        self.opts = opts

    handle_signin_response = salt.crypt.AsyncAuth.handle_signin_response


def _invoke_hook(opts, cluster_id_in_payload):
    """
    Invoke handle_signin_response() with a synthetic clear-signed
    payload and return the resulting ``auth`` dict (or whatever the
    method chose to return).
    """
    inner = {"nonce": "n", "publish_port": 4505}
    if cluster_id_in_payload is not None:
        inner["cluster_id"] = cluster_id_in_payload
    envelope = {
        "load": salt.payload.dumps(inner),
        "sig": b"",
    }
    sign_in_payload = {"nonce": "n"}
    harness = _MinionAuthHarness(opts)
    return harness.handle_signin_response(sign_in_payload, envelope)


def test_auth_response_includes_cluster_id_when_both_opts_true(pki_dir):
    """
    With topology_enabled=True AND topology_push_cluster_grain=True,
    the resulting auth dict exposes the response's cluster_id.
    """
    opts = _build_minion_opts(True, True, pki_dir)
    auth = _invoke_hook(opts, cluster_id_in_payload="east")
    assert auth is not False
    assert auth.get("publish_port") == 4505
    assert auth.get("cluster_id") == "east"


def test_auth_response_omits_cluster_id_when_topology_disabled(pki_dir):
    """
    With topology_enabled=False, cluster_id is NOT propagated even
    when the master's response carries it.
    """
    opts = _build_minion_opts(False, True, pki_dir)
    auth = _invoke_hook(opts, cluster_id_in_payload="east")
    assert auth is not False
    assert "cluster_id" not in auth


def test_auth_response_omits_cluster_id_when_push_grain_disabled(pki_dir):
    """
    With topology_push_cluster_grain=False, cluster_id is NOT
    propagated even when topology is enabled.
    """
    opts = _build_minion_opts(True, False, pki_dir)
    auth = _invoke_hook(opts, cluster_id_in_payload="east")
    assert auth is not False
    assert "cluster_id" not in auth


def test_auth_response_omits_cluster_id_when_payload_lacks_it(pki_dir):
    """
    A non-topology master sends no cluster_id; the hook must not
    invent one.
    """
    opts = _build_minion_opts(True, True, pki_dir)
    auth = _invoke_hook(opts, cluster_id_in_payload=None)
    assert auth is not False
    assert "cluster_id" not in auth
