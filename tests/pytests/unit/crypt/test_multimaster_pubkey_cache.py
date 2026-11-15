"""
Regression tests for the multimaster ``AsyncAuth`` pubkey cache race.

When ``salt.minion.MultiMinion`` spawns one ``Minion`` per master in
``master_type: str`` list mode (and in ``failover``/``distributed``
after narrowing), every sibling ``AsyncAuth`` shares a ``pki_dir``.
Before the fix, each instance used the same filename
``minion_master.pub`` for its cached master pubkey, and the children
clobbered each other during the initial auth. The loser later failed
signature verification in ``decrypt_aes`` with
``ValueError('Unable to decrypt message')`` and dropped off that
master.

The fix (``salt/crypt.py: _resolve_mpub``) shards the cache filename by
``opts["master"]`` when ``opts["multimaster"]`` is truthy. Single-master
deployments keep the historical ``minion_master.pub`` name untouched.
"""

import os

import pytest

import salt.crypt as crypt
import salt.utils.files


def _minion_opts(pki_dir, master, master_uri, *, multimaster, role="minion"):
    return {
        "id": "minion",
        "__role": role,
        "pki_dir": str(pki_dir),
        "master": master,
        "master_uri": master_uri,
        "multimaster": multimaster,
        "keysize": 4096,
        "acceptance_wait_time": 60,
        "acceptance_wait_time_max": 60,
        "keys.cache_driver": "localfs_key",
        "open_mode": False,
        "verify_master_pubkey_sign": False,
        "always_verify_signature": False,
    }


@pytest.fixture
def pki_dir(tmp_path):
    path = tmp_path / "pki"
    path.mkdir()
    return path


def test_resolve_mpub_single_master_keeps_legacy_name():
    """
    Single-master installs (no ``multimaster`` flag) MUST retain the
    historical ``minion_master.pub`` filename so existing on-disk
    caches remain valid after upgrade.
    """
    opts = {"__role": "minion", "master": "salt", "multimaster": False}
    assert crypt._resolve_mpub(opts) == "minion_master.pub"


def test_resolve_mpub_syndic_unchanged():
    """
    Syndic role resolves to ``syndic_master.pub`` regardless of the
    multimaster flag.
    """
    opts = {
        "__role": "syndic",
        "master": "salt",
        "multimaster": True,
    }
    assert crypt._resolve_mpub(opts) == "syndic_master.pub"


def test_resolve_mpub_multimaster_shards_by_master_name():
    """
    Two masters in multimaster mode MUST resolve to distinct filenames
    derived from ``opts["master"]``.
    """
    a = {"__role": "minion", "master": "master-a", "multimaster": True}
    b = {"__role": "minion", "master": "master-b", "multimaster": True}
    name_a = crypt._resolve_mpub(a)
    name_b = crypt._resolve_mpub(b)
    assert name_a != name_b
    assert name_a == "minion_master.master-a.pub"
    assert name_b == "minion_master.master-b.pub"


@pytest.mark.parametrize(
    "master,expected",
    [
        ("10.0.0.1", "minion_master.10.0.0.1.pub"),
        ("fe80::1", "minion_master.fe80__1.pub"),
        ("master/weird", "minion_master.master_weird.pub"),
        ("A_B.c-d", "minion_master.A_B.c-d.pub"),
    ],
)
def test_resolve_mpub_sanitizes_unsafe_chars(master, expected):
    """
    ``opts["master"]`` can carry characters unsafe in filenames
    (``:``, ``/``, etc). The resolver must map them deterministically
    to filesystem-safe placeholders.
    """
    opts = {"__role": "minion", "master": master, "multimaster": True}
    assert crypt._resolve_mpub(opts) == expected


def test_async_auth_multimaster_uses_distinct_mpub(pki_dir, io_loop):
    """
    Two ``AsyncAuth`` instances for different masters sharing a
    ``pki_dir`` must land on DIFFERENT ``self.mpub`` paths so that
    their initial writes do not clobber each other.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    opts_a = _minion_opts(pki_dir, "master-a", "tcp://master-a:4506", multimaster=True)
    opts_b = _minion_opts(pki_dir, "master-b", "tcp://master-b:4506", multimaster=True)

    auth_a = crypt.AsyncAuth(opts_a, io_loop)
    auth_b = crypt.AsyncAuth(opts_b, io_loop)

    assert auth_a is not auth_b
    assert auth_a.mpub != auth_b.mpub
    assert auth_a.mpub == "minion_master.master-a.pub"
    assert auth_b.mpub == "minion_master.master-b.pub"

    # The derived on-disk paths must also differ.
    path_a = os.path.join(opts_a["pki_dir"], auth_a.mpub)
    path_b = os.path.join(opts_b["pki_dir"], auth_b.mpub)
    assert path_a != path_b


def test_async_auth_single_master_keeps_legacy_mpub(pki_dir, io_loop):
    """
    Without ``multimaster``, ``AsyncAuth.mpub`` must still be the
    historical ``minion_master.pub``.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    opts = _minion_opts(pki_dir, "salt", "tcp://salt:4506", multimaster=False)
    auth = crypt.AsyncAuth(opts, io_loop)
    assert auth.mpub == "minion_master.pub"


def test_async_auth_multimaster_cached_writes_do_not_overlap(pki_dir, io_loop):
    """
    Simulate each child ``AsyncAuth`` writing its own master pubkey
    through the sharded cache path. The two files must be independent:
    writing A's key must not alter B's cached bytes.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    opts_a = _minion_opts(pki_dir, "master-a", "tcp://master-a:4506", multimaster=True)
    opts_b = _minion_opts(pki_dir, "master-b", "tcp://master-b:4506", multimaster=True)
    auth_a = crypt.AsyncAuth(opts_a, io_loop)
    auth_b = crypt.AsyncAuth(opts_b, io_loop)

    key_a = b"-----BEGIN PUBLIC KEY-----\nAAA\n-----END PUBLIC KEY-----\n"
    key_b = b"-----BEGIN PUBLIC KEY-----\nBBB\n-----END PUBLIC KEY-----\n"

    path_a = os.path.join(opts_a["pki_dir"], auth_a.mpub)
    path_b = os.path.join(opts_b["pki_dir"], auth_b.mpub)
    with salt.utils.files.fopen(path_a, "wb") as fh:
        fh.write(key_a)
    with salt.utils.files.fopen(path_b, "wb") as fh:
        fh.write(key_b)

    # Each master's cache MUST contain its own key, untouched by the
    # sibling's write. This is the exact invariant the pre-fix race
    # violated.
    with salt.utils.files.fopen(path_a, "rb") as fh:
        assert fh.read() == key_a
    with salt.utils.files.fopen(path_b, "rb") as fh:
        assert fh.read() == key_b


def test_async_auth_cross_read_mismatches(pki_dir, io_loop):
    """
    Reading master A's pubkey through master B's ``AsyncAuth`` must
    surface a mismatch. Before the fix, auth B's ``m_pub_fn`` resolved
    to the same filename as A's, so B silently read A's key and
    proceeded to the signature verification step (which then failed
    with the user-visible ``Unable to decrypt message``).  After the
    fix, B's ``m_pub_fn`` is a distinct path that does not exist (nor
    is it ever written by A), which is the healthy baseline.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    opts_a = _minion_opts(pki_dir, "master-a", "tcp://master-a:4506", multimaster=True)
    opts_b = _minion_opts(pki_dir, "master-b", "tcp://master-b:4506", multimaster=True)
    auth_a = crypt.AsyncAuth(opts_a, io_loop)
    auth_b = crypt.AsyncAuth(opts_b, io_loop)

    key_a = b"-----BEGIN PUBLIC KEY-----\nAAA\n-----END PUBLIC KEY-----\n"
    path_a = os.path.join(opts_a["pki_dir"], auth_a.mpub)
    with salt.utils.files.fopen(path_a, "wb") as fh:
        fh.write(key_a)

    # B must NOT see A's cached pubkey -- its own file is still absent.
    path_b = os.path.join(opts_b["pki_dir"], auth_b.mpub)
    assert not os.path.exists(path_b)
    assert path_a != path_b


def test_async_auth_legacy_mpub_migrates_into_new_shard(pki_dir, io_loop):
    """
    Upgrade path: a single-master deployment that previously trusted
    one master via ``minion_master.pub`` is reconfigured for
    multimaster. On first construction of a multimaster ``AsyncAuth``,
    the legacy file is copied into the per-master shard so
    trust-on-first-use is not re-triggered.

    Only one shard receives the migration in practice (the one that
    corresponds to the formerly-trusted master); constructing an
    ``AsyncAuth`` for any of the new masters seeds its own shard from
    the legacy file. That is acceptable because the legacy file is
    exactly the pubkey the minion has already accepted.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    legacy_bytes = b"-----BEGIN PUBLIC KEY-----\nLEGACY\n-----END PUBLIC KEY-----\n"
    legacy_path = pki_dir / "minion_master.pub"
    legacy_path.write_bytes(legacy_bytes)

    opts = _minion_opts(pki_dir, "master-a", "tcp://master-a:4506", multimaster=True)
    auth = crypt.AsyncAuth(opts, io_loop)

    new_path = os.path.join(opts["pki_dir"], auth.mpub)
    assert auth.mpub == "minion_master.master-a.pub"
    assert os.path.exists(new_path)
    with salt.utils.files.fopen(new_path, "rb") as fh:
        assert fh.read() == legacy_bytes
    # Legacy file left in place for rollback safety.
    assert legacy_path.read_bytes() == legacy_bytes


def test_async_auth_legacy_migration_does_not_overwrite(pki_dir, io_loop):
    """
    If a per-master shard already exists (second start after the
    sharded code has been running), the legacy migration MUST NOT
    overwrite it. This guards against a stale ``minion_master.pub``
    silently rolling back the per-master cache.
    """
    crypt.write_keys(str(pki_dir), "minion", 4096)

    fresh_bytes = b"-----BEGIN PUBLIC KEY-----\nFRESH\n-----END PUBLIC KEY-----\n"
    stale_bytes = b"-----BEGIN PUBLIC KEY-----\nSTALE\n-----END PUBLIC KEY-----\n"
    (pki_dir / "minion_master.pub").write_bytes(stale_bytes)
    (pki_dir / "minion_master.master-a.pub").write_bytes(fresh_bytes)

    opts = _minion_opts(pki_dir, "master-a", "tcp://master-a:4506", multimaster=True)
    auth = crypt.AsyncAuth(opts, io_loop)
    with salt.utils.files.fopen(os.path.join(opts["pki_dir"], auth.mpub), "rb") as fh:
        assert fh.read() == fresh_bytes
