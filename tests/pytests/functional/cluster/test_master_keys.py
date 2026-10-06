"""
Functional tests for cluster master keys and the shared cluster PKI dir.

These tests exercise :class:`salt.crypt.MasterKeys` against a real
filesystem layout -- no daemons are started -- to lock in the invariants
the cluster join/rotation code relies on:

* every cluster master publishes its own pub key under
  ``{cluster_pki_dir}/peers/{id}.pub``
* the cluster signing keypair (``cluster.pem`` / ``cluster.pub``) is
  generated once and re-used by every subsequent master that points at
  the same ``cluster_pki_dir``
* a stale / mismatched peer pub key on disk is surfaced as a hard
  failure instead of being silently overwritten
"""

import pathlib

import pytest

import salt.crypt
import salt.exceptions


@pytest.fixture
def cluster_pki_dir(tmp_path):
    """
    Shared cluster pki dir with the ``peers`` sub-directory the cluster
    code expects.
    """
    path = tmp_path / "cluster_pki"
    path.mkdir()
    (path / "peers").mkdir()
    return path


def _cluster_master_opts(master_opts, pki_dir, master_id, cluster_pki_dir):
    """
    Derive a master opts dict configured as a cluster member with its
    own private ``pki_dir`` but the shared ``cluster_pki_dir``.
    """
    opts = master_opts.copy()
    opts["id"] = master_id
    opts["pki_dir"] = str(pki_dir)
    opts["cluster_id"] = "master_cluster"
    opts["cluster_pki_dir"] = str(cluster_pki_dir)
    opts["cluster_peers"] = []
    opts["cluster_key_pass"] = None
    opts["cluster_secret"] = None
    opts["key_pass"] = None
    opts["master_sign_pubkey"] = False
    return opts


def test_cluster_master_keys_promote_pub_to_peers(
    master_opts, tmp_path, cluster_pki_dir
):
    """
    Starting ``MasterKeys`` with ``cluster_id`` set must copy the
    master's own pub key into ``{cluster_pki_dir}/peers/{id}.pub`` and
    generate the shared ``cluster.pem`` / ``cluster.pub`` pair.
    """
    master_pki = tmp_path / "master_pki"
    master_pki.mkdir()
    opts = _cluster_master_opts(master_opts, master_pki, "127.0.0.1", cluster_pki_dir)

    salt.crypt.MasterKeys(opts)

    assert (cluster_pki_dir / "cluster.pem").exists()
    assert (cluster_pki_dir / "cluster.pub").exists()

    shared_pub = cluster_pki_dir / "peers" / "127.0.0.1.pub"
    assert shared_pub.exists()

    own_pub = master_pki / "master.pub"
    assert shared_pub.read_text(encoding="utf-8") == own_pub.read_text(encoding="utf-8")


def test_cluster_master_keys_shared_cluster_keypair(
    master_opts, tmp_path, cluster_pki_dir
):
    """
    Two masters sharing the same ``cluster_pki_dir`` must share the same
    cluster keypair (the second does not regenerate it) and must both
    advertise distinct, non-colliding per-master pub keys in ``peers/``.
    """
    pki_one = tmp_path / "one"
    pki_one.mkdir()
    pki_two = tmp_path / "two"
    pki_two.mkdir()
    opts_one = _cluster_master_opts(master_opts, pki_one, "127.0.0.1", cluster_pki_dir)
    opts_two = _cluster_master_opts(master_opts, pki_two, "127.0.0.2", cluster_pki_dir)

    keys_one = salt.crypt.MasterKeys(opts_one)
    cluster_pem_after_one = (cluster_pki_dir / "cluster.pem").read_text(
        encoding="utf-8"
    )

    keys_two = salt.crypt.MasterKeys(opts_two)
    cluster_pem_after_two = (cluster_pki_dir / "cluster.pem").read_text(
        encoding="utf-8"
    )

    # The second master must NOT rotate the shared cluster keypair.
    assert cluster_pem_after_one == cluster_pem_after_two
    assert keys_one.cluster_rsa_path == keys_two.cluster_rsa_path

    peer_one_pub = cluster_pki_dir / "peers" / "127.0.0.1.pub"
    peer_two_pub = cluster_pki_dir / "peers" / "127.0.0.2.pub"
    assert peer_one_pub.exists()
    assert peer_two_pub.exists()

    # Per-master pub keys must actually differ -- each master has its
    # own master.pem and therefore its own master.pub.
    assert peer_one_pub.read_text(encoding="utf-8") != peer_two_pub.read_text(
        encoding="utf-8"
    )


def test_cluster_master_keys_mismatched_shared_pub_raises(
    master_opts, tmp_path, cluster_pki_dir
):
    """
    If ``peers/{id}.pub`` already exists but does NOT match the master's
    own pub key (e.g. stale key from a previous host with the same id),
    :class:`MasterKeys` must raise :class:`MasterExit` rather than
    silently clobber one of the keys.
    """
    master_pki = tmp_path / "master_pki"
    master_pki.mkdir()
    opts = _cluster_master_opts(master_opts, master_pki, "127.0.0.1", cluster_pki_dir)

    # Pre-seed the master's own pub key so ``check_master_shared_pub``
    # has something to compare against.
    salt.crypt.MasterKeys(
        _cluster_master_opts(
            master_opts,
            master_pki,
            "127.0.0.1",
            tmp_path / "unused_cluster",
        )
    )

    # Drop a mismatched key into the shared cluster pki dir.
    stale = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAK3fakekeyfakekeyfakekeyfake\n"
        "key+fakekeyfakekeyfakekeyfakekeyfakekeyfakekeyfakekeyCAwEAAQ==\n"
        "-----END PUBLIC KEY-----\n"
    )
    (cluster_pki_dir / "peers" / "127.0.0.1.pub").write_text(stale, encoding="utf-8")

    with pytest.raises(salt.exceptions.MasterExit):
        salt.crypt.MasterKeys(opts)


def test_cluster_master_keys_survive_restart(master_opts, tmp_path, cluster_pki_dir):
    """
    Instantiating :class:`MasterKeys` a second time for the same master
    must be idempotent: the same on-disk keys are reused, the shared
    cluster key is not rotated, and the master's pub key in ``peers/``
    is left alone.
    """
    master_pki = tmp_path / "master_pki"
    master_pki.mkdir()
    opts = _cluster_master_opts(master_opts, master_pki, "127.0.0.1", cluster_pki_dir)

    salt.crypt.MasterKeys(opts)
    first_master_pub = pathlib.Path(master_pki, "master.pub").read_text(
        encoding="utf-8"
    )
    first_cluster_pem = (cluster_pki_dir / "cluster.pem").read_text(encoding="utf-8")
    first_shared_pub = (cluster_pki_dir / "peers" / "127.0.0.1.pub").read_text(
        encoding="utf-8"
    )

    salt.crypt.MasterKeys(opts)

    assert (
        pathlib.Path(master_pki, "master.pub").read_text(encoding="utf-8")
        == first_master_pub
    )
    assert (cluster_pki_dir / "cluster.pem").read_text(
        encoding="utf-8"
    ) == first_cluster_pem
    assert (cluster_pki_dir / "peers" / "127.0.0.1.pub").read_text(
        encoding="utf-8"
    ) == first_shared_pub
