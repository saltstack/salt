"""
Regression tests for peer-master key placement on solo vs. clustered
masters.

Covers the documented contract in
``doc/topics/master-topology/index.md`` section "Trust directories":
peer identity keys land under ``<pki_dir>/masters*/`` on a solo master
but under ``<cluster_pki_dir>/masters*/`` on a clustered master.
Both the inbound handshake (``_handle_master_auth`` via
``_masters_subdir``) and the operator CLI (``salt-key --master`` via
``MasterKey._bucket_path``) must agree on the same root; a mismatch
was the regression that the phase-1 annotation at 4e8a37d92d3
corrected.

These tests are intentionally thin: no MmapCache, no event bus, no
Raft SM.  They assert only the directory-selection branch.
"""

import asyncio
import os

import pytest

import salt.key
import salt.topology.link_manager as lm
import salt.utils.files


def _run(coro):
    """Run a coroutine on a fresh event loop; Python 3.14 removed the
    implicit main-thread loop so ``asyncio.get_event_loop`` raises
    inside a sync test."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


FAKE_PUB = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"test-cluster-identity-key\n"
    b"-----END PUBLIC KEY-----\n"
)


def _make_pki_tree(root):
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (root / sub).mkdir(parents=True, exist_ok=True)


@pytest.fixture
def solo_opts(tmp_path):
    pki = tmp_path / "pki"
    _make_pki_tree(pki)
    return {
        "pki_dir": str(pki),
        # Solo masters leave both cluster_id and cluster_pki_dir unset.
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock"),
        "transport": "zeromq",
        "keys.cache_driver": "localfs_key",
        "key_cache": "",
        "preserve_minions": False,
        "rotate_aes_key": False,
        "hash_type": "sha256",
        "keysize": 2048,
        "__role": "master",
        "id": "solo-master",
        "user": "root",
        "signing_key_pass": None,
    }


@pytest.fixture
def clustered_opts(tmp_path, solo_opts):
    """Opts for a clustered master: cluster_id set, cluster_pki_dir
    distinct from pki_dir.  Keys must land under cluster_pki_dir."""
    cluster_pki = tmp_path / "cluster_pki"
    _make_pki_tree(cluster_pki)
    opts = dict(solo_opts)
    opts["cluster_id"] = "local-cluster"
    opts["cluster_pki_dir"] = str(cluster_pki)
    return opts


# ---------------------------------------------------------------------------
# _masters_subdir (link_manager inbound handshake)
# ---------------------------------------------------------------------------


def test_masters_subdir_solo_uses_pki_dir(solo_opts):
    path = lm._masters_subdir(solo_opts, "masters_pre")
    assert path == os.path.join(solo_opts["pki_dir"], "masters_pre")


def test_masters_subdir_clustered_uses_cluster_pki_dir(clustered_opts):
    """Phase-1 fix: when cluster_id AND cluster_pki_dir are set, inbound
    handshake must write pending keys under cluster_pki_dir, not
    pki_dir."""
    path = lm._masters_subdir(clustered_opts, "masters_pre")
    assert path == os.path.join(clustered_opts["cluster_pki_dir"], "masters_pre")
    # Negative: must NOT point at the per-node pki_dir.
    assert path != os.path.join(clustered_opts["pki_dir"], "masters_pre")


def test_masters_subdir_clustered_without_cluster_pki_dir_falls_back(clustered_opts):
    """``cluster_id`` without a configured ``cluster_pki_dir`` falls
    back to the per-node ``pki_dir``.  Defensive: a misconfigured
    cluster must not silently write to ``""``."""
    clustered_opts.pop("cluster_pki_dir")
    path = lm._masters_subdir(clustered_opts, "masters")
    assert path == os.path.join(clustered_opts["pki_dir"], "masters")


# ---------------------------------------------------------------------------
# MasterKey (salt-key --master operator CLI)
# ---------------------------------------------------------------------------


def test_master_key_solo_bucket_path_uses_pki_dir(solo_opts):
    mk = salt.key.MasterKey(solo_opts)
    assert mk.pki_dir == solo_opts["pki_dir"]
    assert mk._bucket_path("masters_pre") == os.path.join(
        solo_opts["pki_dir"], "masters_pre"
    )


def test_master_key_clustered_bucket_path_uses_cluster_pki_dir(clustered_opts):
    """``salt-key -L --master`` on a clustered master must list the
    same directory the handshake wrote into --- otherwise operators
    never see pending peers."""
    mk = salt.key.MasterKey(clustered_opts)
    assert mk.pki_dir == clustered_opts["cluster_pki_dir"]
    assert mk._bucket_path("masters") == os.path.join(
        clustered_opts["cluster_pki_dir"], "masters"
    )


@pytest.mark.parametrize(
    "opts_name,root_key",
    [
        ("solo_opts", "pki_dir"),
        ("clustered_opts", "cluster_pki_dir"),
    ],
)
def test_master_key_acc_symbol_resolves_to_right_root(request, opts_name, root_key):
    """``MasterKey.ACC`` (the accepted-bucket name) must resolve through
    ``_bucket_path`` to the same root ``_masters_subdir`` picks in the
    handshake --- i.e. ``pki_dir`` on solo, ``cluster_pki_dir`` on
    clustered.  Pins the class-attribute symbol, not just the literal
    string ``"masters"``, so a rename cannot silently diverge from the
    handshake."""
    opts = request.getfixturevalue(opts_name)
    mk = salt.key.MasterKey(opts)
    expected_root = opts[root_key]
    assert mk._bucket_path(mk.ACC) == os.path.join(expected_root, mk.ACC)
    # And every state bucket (PEND/REJ/DEN) must share that same root.
    for bucket in (mk.PEND, mk.REJ, mk.DEN):
        assert mk._bucket_path(bucket) == os.path.join(expected_root, bucket)
    # Handshake and CLI must agree on the ACC root.
    assert mk._bucket_path(mk.ACC) == lm._masters_subdir(opts, mk.ACC)


# ---------------------------------------------------------------------------
# Cross-check: handshake-written keys are visible to MasterKey.list_keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "opts_name,root_key",
    [
        ("solo_opts", "pki_dir"),
        ("clustered_opts", "cluster_pki_dir"),
    ],
)
def test_handshake_write_visible_to_master_key_list(
    request, opts_name, root_key, monkeypatch
):
    """End-to-end on-disk contract: a key landed in ``masters_pre/`` by
    the inbound handshake must be enumerable by ``salt-key -L --master``.
    Protects against the exact shape of bug the phase-1 annotation
    documents: inbound wrote to cluster_pki_dir, CLI read from pki_dir,
    operator never saw pending peers on clustered masters.
    """
    opts = request.getfixturevalue(opts_name)

    # Prime globals so _current_opts returns our test opts and no
    # Raft/propose side-effects fire.
    monkeypatch.setattr(lm, "_OPTS", opts, raising=False)
    monkeypatch.setattr(lm, "_maybe_propose_attach", lambda *a, **k: None)

    load = {
        "cluster_id": "peer-east",
        "public_key": FAKE_PUB,
    }
    reply = _run(lm._handle_master_auth(load))
    assert reply["status"] == "retry"

    # The pending file is on disk under the documented root.
    expected_pending = os.path.join(opts[root_key], "masters_pre", "peer-east.pub")
    assert os.path.exists(expected_pending), expected_pending

    # salt-key --master sees it in the pending bucket.
    mk = salt.key.MasterKey(opts)
    buckets = mk.list_keys()
    assert "peer-east" in buckets["pending"]
    assert "peer-east" not in buckets["accepted"]


# ---------------------------------------------------------------------------
# rejected handling: handshake refuses a peer whose key is in masters_rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("opts_name", ["solo_opts", "clustered_opts"])
def test_rejected_peer_handshake_returns_rejected(request, opts_name, monkeypatch):
    opts = request.getfixturevalue(opts_name)
    root = opts.get("cluster_pki_dir") or opts["pki_dir"]
    rejected_path = os.path.join(root, "masters_rejected", "peer-west.pub")
    with salt.utils.files.fopen(rejected_path, "wb") as fh:
        fh.write(FAKE_PUB)

    monkeypatch.setattr(lm, "_OPTS", opts, raising=False)
    monkeypatch.setattr(lm, "_maybe_propose_attach", lambda *a, **k: None)

    reply = _run(
        lm._handle_master_auth({"cluster_id": "peer-west", "public_key": FAKE_PUB})
    )
    assert reply["status"] == "rejected"
