"""
Unit tests for :class:`salt.crypt.MasterIdentityKey`.

Narrow coverage focused on edge cases that are expensive or awkward
to drive through the functional suite:

* ``__init__`` validates ``opts["pki_dir"]``.
* ``write()`` raises when the parent directory is unwritable.
* ``fingerprint()`` honors ``opts["hash_type"]``.
* ``generate(key_size=1024)`` honors the explicit key_size override
  (though the default must stay >= 2048).
"""

import os
import stat

import pytest

import salt.crypt
import salt.utils.crypt

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def pki_dir(tmp_path):
    root = tmp_path / "pki"
    (root / "master").mkdir(parents=True)
    return root


def _opts(pki_dir, hash_type="sha256", keysize=2048):
    return {
        "pki_dir": str(pki_dir),
        "hash_type": hash_type,
        "keysize": keysize,
    }


# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------


def test_init_rejects_missing_pki_dir():
    """A missing or empty opts['pki_dir'] is a programmer error."""
    with pytest.raises((KeyError, ValueError)):
        salt.crypt.MasterIdentityKey({})


def test_init_rejects_empty_pki_dir():
    with pytest.raises((KeyError, ValueError)):
        salt.crypt.MasterIdentityKey({"pki_dir": ""})


def test_init_derives_file_paths(pki_dir):
    """The pub/priv paths are under opts['pki_dir']/master/."""
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir))
    assert key.pub_path == str(pki_dir / "master" / "master_identity.pub")
    assert key.priv_path == str(pki_dir / "master" / "master_identity.pem")


# ---------------------------------------------------------------------------
# write() permission failures
# ---------------------------------------------------------------------------


@pytest.mark.skip_on_windows(reason="POSIX dir-mode semantics only")
def test_write_raises_when_parent_dir_unwritable(pki_dir):
    """
    When the ``master/`` directory under pki_dir is not writable,
    write() surfaces an OSError rather than silently dropping bytes.
    """
    if os.geteuid() == 0:
        pytest.skip("root bypasses POSIX write-perm checks")
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir))
    pub, priv = key.generate(key_size=2048)
    # Strip write bits from the master/ subdir.
    master_dir = pki_dir / "master"
    original_mode = stat.S_IMODE(os.stat(master_dir).st_mode)
    os.chmod(master_dir, 0o500)
    try:
        with pytest.raises(OSError):
            key.write(pub, priv)
    finally:
        os.chmod(master_dir, original_mode)


# ---------------------------------------------------------------------------
# fingerprint() honors hash_type
# ---------------------------------------------------------------------------


def test_fingerprint_uses_sha256_by_default(pki_dir):
    """The default hash_type is sha256 and the output matches it."""
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir))
    pub, priv = key.generate(key_size=2048)
    key.write(pub, priv)
    expected = salt.utils.crypt.pem_finger(path=key.pub_path, sum_type="sha256")
    assert key.fingerprint() == expected


def test_fingerprint_honors_hash_type_sha512(pki_dir):
    """
    Switching opts['hash_type'] changes the fingerprint and the
    output matches pem_finger invoked with the same hash.
    """
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir, hash_type="sha512"))
    pub, priv = key.generate(key_size=2048)
    key.write(pub, priv)
    expected = salt.utils.crypt.pem_finger(path=key.pub_path, sum_type="sha512")
    assert key.fingerprint() == expected
    # And the sha512 fingerprint must differ from the sha256 one for
    # the same key: proves the hash_type opt actually flows through.
    sha256 = salt.utils.crypt.pem_finger(path=key.pub_path, sum_type="sha256")
    assert key.fingerprint() != sha256


def test_fingerprint_empty_when_no_key_on_disk(pki_dir):
    """
    pem_finger returns "" for a missing file; the wrapper preserves
    that contract so callers can distinguish "no key yet" from "bad
    key" without catching exceptions.
    """
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir))
    assert key.fingerprint() == ""


# ---------------------------------------------------------------------------
# generate(key_size=...) override
# ---------------------------------------------------------------------------


def test_generate_key_size_override_1024(pki_dir):
    """
    Explicit key_size=1024 produces a 1024-bit key (small keys are
    valid for tests but must never be the default).
    """
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir))
    pub, _priv = key.generate(key_size=1024)
    pk = salt.crypt.PublicKey.from_str(pub)
    assert pk.key.key_size == 1024


def test_generate_default_key_size_is_2048_or_more(pki_dir):
    """
    The default (no key_size argument, no opts['keysize']) must be
    at least 2048 bits.  Protects against a reviewer accidentally
    dropping the floor.
    """
    key = salt.crypt.MasterIdentityKey({"pki_dir": str(pki_dir), "hash_type": "sha256"})
    pub, _priv = key.generate()
    pk = salt.crypt.PublicKey.from_str(pub)
    assert pk.key.key_size >= 2048


def test_generate_opts_keysize_honored(pki_dir):
    """
    When no explicit key_size is given, generate() falls back to
    opts['keysize'].
    """
    key = salt.crypt.MasterIdentityKey(_opts(pki_dir, keysize=3072))
    pub, _priv = key.generate()
    pk = salt.crypt.PublicKey.from_str(pub)
    assert pk.key.key_size == 3072
