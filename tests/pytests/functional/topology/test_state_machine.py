"""
Functional tests for :class:`salt.cluster.consensus.raft.topology.TopologyStateMachine`.

Exercises the SM against the real
:class:`salt.utils.mmap_cache.MmapCache` backing the registry (no
mocks of :mod:`salt.topology.registry`).  The Raft ``Node`` is not
spun up here --- the SM's ``apply`` is a plain Python callable, so
we drive it directly as the Node does on commit.  This keeps the
test boundary at the SM contract (``apply`` + ``get_snapshot`` +
``restore_snapshot``) and avoids the integration-weight single-cluster
fixture when it isn't needed to prove the SM semantics.

Covered:

* ``MASTER_IDENTITY_KEY`` apply: fresh bootstrap writes identity pub
  + version=0; identical re-apply is idempotent (version unchanged);
  rotation replaces bytes and bumps version.
* ``MASTER_PEER_ATTACH`` apply: valid attach writes PeerState into
  the registry and moves the pending key file from ``masters_pre/``
  to ``masters/``; invalid ``cluster_id`` (regex violation OR reserved
  name) is rejected at apply time with CRITICAL log and no registry
  mutation; existing peer with mismatched public_key is rejected
  unless ``force_replace`` is set.
* ``MASTER_PEER_DETACH`` apply: entry removes peer from registry;
  file moves to ``masters_denied/`` for ``reason="rejected"`` and
  is deleted for ``reason="revoked"``.
* ``get_snapshot`` / ``restore_snapshot`` round-trip: a snapshot
  taken after N attaches + an identity write restores exactly those
  peers + identity, and NEVER carries ``last_summary`` / routes.
* ``apply`` with an unknown entry type is a logged no-op (registry
  untouched).
"""

import logging
import os

import pytest

import salt.topology.registry as registry
import salt.utils.files
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import (
    PeerState,
    TopologyStateMachine,
    _read_identity_version,
)

pytestmark = [
    pytest.mark.skip_on_windows,  # fork(2) + 0o400 permissions assumptions
]


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _opts(pki_root):
    """
    Build the minimal opts dict the SM + registry read.

    ``pki_dir`` is the parent of ``master/``; the cache files live
    at ``<pki_dir>/master/topology_registry.mmap*`` and the
    ``masters*/`` directories live directly under ``pki_dir`` to
    match salt-key's convention.
    """
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    # Pre-create the acceptance-state directories so file-move
    # assertions have real paths to point at.
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "keysize": 2048,
        "hash_type": "sha256",
    }


@pytest.fixture
def opts(tmp_path):
    return _opts(tmp_path)


@pytest.fixture
def sm(opts):
    """
    Build a :class:`TopologyStateMachine` wired to the real registry.
    """
    registry.pre_create(opts)
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        # Release the writer handle so the next test opens a fresh
        # one against its own tmp pki_dir.
        cache = getattr(machine, "registry", None)
        if cache is not None and hasattr(cache, "close"):
            try:
                cache.close()
            except Exception:  # pylint: disable=broad-except
                pass


def _identity_cmd(pub_pem, priv_pem=None):
    """Build a MASTER_IDENTITY_KEY cmd payload."""
    cmd = {
        "type": LogEntryType.MASTER_IDENTITY_KEY,
        "public_key": pub_pem,
    }
    if priv_pem is not None:
        cmd["private_key"] = priv_pem
    return cmd


def _attach_cmd(cluster_id, public_key, endpoints=("127.0.0.1:4506",), **extra):
    """Build a MASTER_PEER_ATTACH cmd payload."""
    cmd = {
        "type": LogEntryType.MASTER_PEER_ATTACH,
        "cluster_id": cluster_id,
        "public_key": public_key,
        "endpoints": tuple(endpoints),
        "attached_at": 1_700_000_000.0,
    }
    cmd.update(extra)
    return cmd


def _detach_cmd(cluster_id, reason="revoked"):
    """Build a MASTER_PEER_DETACH cmd payload."""
    return {
        "type": LogEntryType.MASTER_PEER_DETACH,
        "cluster_id": cluster_id,
        "reason": reason,
    }


def _place_pending_key(opts_, cluster_id, pub_bytes):
    """Drop a pub file into ``pki_dir/masters_pre/<cluster_id>.pub``."""
    path = os.path.join(opts_["pki_dir"], "masters_pre", f"{cluster_id}.pub")
    with salt.utils.files.fopen(path, "wb") as fh:
        fh.write(pub_bytes)
    return path


# ---------------------------------------------------------------------------
# MASTER_IDENTITY_KEY
# ---------------------------------------------------------------------------


FAKE_PUB_A = b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"
FAKE_PUB_B = b"-----BEGIN PUBLIC KEY-----\nBBBB\n-----END PUBLIC KEY-----\n"
FAKE_PRIV_A = b"-----BEGIN RSA PRIVATE KEY-----\naaaa\n-----END RSA PRIVATE KEY-----\n"
FAKE_PRIV_B = b"-----BEGIN RSA PRIVATE KEY-----\nbbbb\n-----END RSA PRIVATE KEY-----\n"


def test_identity_key_fresh_bootstrap(sm, opts):
    """Fresh apply writes identity_pub into the registry and bootstraps the SM."""
    assert sm.is_bootstrapped() is False
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    assert registry.get_identity_pub(sm.registry) == FAKE_PUB_A
    assert sm.is_bootstrapped() is True
    # Public half persisted on disk at the master-identity path.
    pub_path = os.path.join(opts["pki_dir"], "master", "master_identity.pub")
    assert os.path.isfile(pub_path)
    with salt.utils.files.fopen(pub_path, "rb") as fh:
        assert fh.read() == FAKE_PUB_A


def test_identity_key_idempotent_reapply(sm):
    """Re-applying identical identity bytes does not bump identity_version."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    first_version = _read_identity_version(sm.registry)
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=2)
    second_version = _read_identity_version(sm.registry)
    assert first_version == second_version


def test_identity_key_rotation_bumps_version(sm):
    """A rotation (new bytes) replaces identity_pub and increments identity_version."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    v1 = _read_identity_version(sm.registry)
    sm.apply(_identity_cmd(FAKE_PUB_B, FAKE_PRIV_B), client_id="op", sequence_num=2)
    v2 = _read_identity_version(sm.registry)
    assert registry.get_identity_pub(sm.registry) == FAKE_PUB_B
    assert v2 > v1


def test_identity_private_key_permissions(sm, opts):
    """Rotation writes master_identity.pem with 0400 (owner read-only)."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    priv_path = os.path.join(opts["pki_dir"], "master", "master_identity.pem")
    assert os.path.isfile(priv_path)
    mode = os.stat(priv_path).st_mode & 0o777
    assert mode == 0o400, f"priv-key permissions {oct(mode)} not 0400"


# ---------------------------------------------------------------------------
# MASTER_PEER_ATTACH
# ---------------------------------------------------------------------------


def test_peer_attach_valid_writes_registry(sm, opts):
    """Valid attach writes the peer to the registry MmapCache."""
    pub = b"-----BEGIN PUBLIC KEY-----\nEAST\n-----END PUBLIC KEY-----\n"
    _place_pending_key(opts, "east", pub)
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=10)
    got = registry.get_peer(sm.registry, "east")
    assert got is not None
    assert got["cluster_id"] == "east"
    assert got["public_key"] == pub


def test_peer_attach_moves_file_from_masters_pre_to_masters(sm, opts):
    """Apply moves ``masters_pre/<id>.pub`` to ``masters/<id>.pub``."""
    pub = b"PENDING-EAST"
    pre_path = _place_pending_key(opts, "east", pub)
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=10)
    accepted_path = os.path.join(opts["pki_dir"], "masters", "east.pub")
    assert os.path.isfile(accepted_path)
    assert not os.path.exists(pre_path)
    with salt.utils.files.fopen(accepted_path, "rb") as fh:
        assert fh.read() == pub


def test_peer_attach_writes_file_if_absent(sm, opts):
    """Follower that joined after attach: file not present locally gets written."""
    pub = b"EAST-FROM-APPLY"
    # Deliberately no masters_pre entry --- this follower learned about
    # the attach from the committed Raft log.
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=10)
    accepted_path = os.path.join(opts["pki_dir"], "masters", "east.pub")
    assert os.path.isfile(accepted_path)
    with salt.utils.files.fopen(accepted_path, "rb") as fh:
        assert fh.read() == pub


@pytest.mark.parametrize(
    "bad_id",
    [
        "UPPERCASE",  # regex: lowercase only
        "has space",  # regex: no spaces
        "-leading-dash",  # regex: must start [a-z0-9]
        "with/slash",  # regex: shell-sensitive
        "__identity_pub__",  # reserved MmapCache sentinel
        "__identity_version__",  # reserved MmapCache sentinel
    ],
)
def test_peer_attach_rejects_invalid_cluster_id(sm, bad_id, caplog):
    """Hostile/invalid cluster_id -> CRITICAL log, no registry mutation."""
    pub = b"X" * 16
    before = set(registry.list_peer_ids(sm.registry))
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        sm.apply(_attach_cmd(bad_id, pub), client_id="op", sequence_num=11)
    after = set(registry.list_peer_ids(sm.registry))
    assert before == after
    assert registry.get_peer(sm.registry, bad_id) is None
    # And a CRITICAL-level log was emitted for the rejection.
    assert any(
        rec.levelno >= logging.CRITICAL for rec in caplog.records
    ), f"expected a CRITICAL log for rejected cluster_id {bad_id!r}"


def test_peer_attach_conflict_rejects_without_force(sm, caplog):
    """Attach of same cluster_id with different public_key is refused by default."""
    pub_a = b"KEY-A" * 8
    pub_b = b"KEY-B" * 8
    sm.apply(_attach_cmd("east", pub_a), client_id="op", sequence_num=20)
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        sm.apply(_attach_cmd("east", pub_b), client_id="op", sequence_num=21)
    # Original key still wins; conflict logged at CRITICAL.
    got = registry.get_peer(sm.registry, "east")
    assert got["public_key"] == pub_a
    assert any(rec.levelno >= logging.CRITICAL for rec in caplog.records)


def test_peer_attach_conflict_force_replace_overwrites(sm):
    """With force_replace=True, the new key wins."""
    pub_a = b"KEY-A" * 8
    pub_b = b"KEY-B" * 8
    sm.apply(_attach_cmd("east", pub_a), client_id="op", sequence_num=20)
    sm.apply(
        _attach_cmd("east", pub_b, force_replace=True),
        client_id="op",
        sequence_num=21,
    )
    got = registry.get_peer(sm.registry, "east")
    assert got["public_key"] == pub_b


def test_peer_attach_same_key_idempotent(sm):
    """Second attach with identical bytes is a quiet no-op."""
    pub = b"EAST-SAME"
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=20)
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=21)
    got = registry.get_peer(sm.registry, "east")
    assert got["public_key"] == pub


# ---------------------------------------------------------------------------
# MASTER_PEER_DETACH
# ---------------------------------------------------------------------------


def test_peer_detach_removes_from_registry(sm):
    """Detach removes the peer entry from the registry MmapCache."""
    pub = b"WEST-KEY"
    sm.apply(_attach_cmd("west", pub), client_id="op", sequence_num=30)
    assert registry.get_peer(sm.registry, "west") is not None
    sm.apply(_detach_cmd("west"), client_id="op", sequence_num=31)
    assert registry.get_peer(sm.registry, "west") is None
    assert "west" not in registry.list_peer_ids(sm.registry)


def test_peer_detach_moves_file_to_masters_denied_on_reject(sm, opts):
    """``reason=rejected`` -> file ends up in ``masters_denied/``."""
    pub = b"WEST-KEY"
    sm.apply(_attach_cmd("west", pub), client_id="op", sequence_num=30)
    accepted_path = os.path.join(opts["pki_dir"], "masters", "west.pub")
    assert os.path.isfile(accepted_path)
    sm.apply(_detach_cmd("west", reason="rejected"), client_id="op", sequence_num=31)
    denied_path = os.path.join(opts["pki_dir"], "masters_denied", "west.pub")
    assert os.path.isfile(denied_path)
    assert not os.path.exists(accepted_path)
    with salt.utils.files.fopen(denied_path, "rb") as fh:
        assert fh.read() == pub


def test_peer_detach_deletes_file_on_revoke(sm, opts):
    """``reason=revoked`` -> file deleted outright."""
    pub = b"WEST-KEY"
    sm.apply(_attach_cmd("west", pub), client_id="op", sequence_num=30)
    accepted_path = os.path.join(opts["pki_dir"], "masters", "west.pub")
    assert os.path.isfile(accepted_path)
    sm.apply(_detach_cmd("west", reason="revoked"), client_id="op", sequence_num=31)
    assert not os.path.exists(accepted_path)
    denied_path = os.path.join(opts["pki_dir"], "masters_denied", "west.pub")
    assert not os.path.exists(denied_path)


def test_peer_detach_unknown_is_idempotent(sm):
    """Detaching an unknown cluster_id must not raise."""
    sm.apply(_detach_cmd("ghost"), client_id="op", sequence_num=40)  # no raise


# ---------------------------------------------------------------------------
# Snapshot / restore
# ---------------------------------------------------------------------------


def test_snapshot_round_trip_preserves_identity_and_peers(sm, opts):
    """get_snapshot -> restore_snapshot reproduces identity + peer registry."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    sm.apply(_attach_cmd("east", b"EAST"), client_id="op", sequence_num=2)
    sm.apply(_attach_cmd("west", b"WEST"), client_id="op", sequence_num=3)
    snap = sm.get_snapshot()
    assert isinstance(snap, (bytes, bytearray))

    # Fresh SM, same opts: feed it the snapshot and expect identical reads.
    other = TopologyStateMachine(opts)
    other.restore_snapshot(snap)
    try:
        assert registry.get_identity_pub(other.registry) == FAKE_PUB_A
        east = registry.get_peer(other.registry, "east")
        west = registry.get_peer(other.registry, "west")
        assert east is not None and east["public_key"] == b"EAST"
        assert west is not None and west["public_key"] == b"WEST"
        assert sorted(registry.list_peer_ids(other.registry)) == ["east", "west"]
    finally:
        other.registry.close()


def test_snapshot_does_not_carry_last_summary(sm):
    """Snapshot must omit last_summary / routes --- soft state only."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    sm.apply(_attach_cmd("east", b"EAST"), client_id="op", sequence_num=2)
    snap_bytes = sm.get_snapshot()
    # Shape-level: no 'last_summary', 'routes', or 'summaries' key anywhere.
    assert b"last_summary" not in snap_bytes
    assert b"routes" not in snap_bytes
    assert b"summaries" not in snap_bytes


def test_snapshot_replaces_prior_state(sm, opts):
    """restore_snapshot into a non-empty SM replaces the entire registry."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    sm.apply(_attach_cmd("east", b"EAST"), client_id="op", sequence_num=2)
    snap = sm.get_snapshot()

    # Dirty a different SM with unrelated state, then restore.
    other = TopologyStateMachine(opts)
    try:
        other.apply(
            _identity_cmd(FAKE_PUB_B, FAKE_PRIV_B),
            client_id="op",
            sequence_num=10,
        )
        other.apply(_attach_cmd("stale", b"STALE"), client_id="op", sequence_num=11)
        other.restore_snapshot(snap)
        assert registry.get_identity_pub(other.registry) == FAKE_PUB_A
        # Peer 'stale' from the pre-restore state must be gone.
        assert registry.get_peer(other.registry, "stale") is None
        assert sorted(registry.list_peer_ids(other.registry)) == ["east"]
    finally:
        other.registry.close()


# ---------------------------------------------------------------------------
# Unknown entry type dispatch
# ---------------------------------------------------------------------------


def test_apply_unknown_entry_type_is_noop(sm, caplog):
    """Unknown cmd types are logged at DEBUG and leave the registry untouched."""
    before = set(registry.list_peer_ids(sm.registry))
    pub_before = registry.get_identity_pub(sm.registry)
    with caplog.at_level(logging.DEBUG, logger="salt.cluster.consensus.raft.topology"):
        sm.apply(
            {"type": 99999, "cluster_id": "east"},
            client_id="op",
            sequence_num=50,
        )
    after = set(registry.list_peer_ids(sm.registry))
    pub_after = registry.get_identity_pub(sm.registry)
    assert before == after
    assert pub_before == pub_after


# ---------------------------------------------------------------------------
# PeerState shape (functional guard against future refactors)
# ---------------------------------------------------------------------------


def test_peer_state_is_namedtuple():
    """PeerState must stay a NamedTuple with the four documented fields."""
    assert issubclass(PeerState, tuple)
    assert PeerState._fields == ("cluster_id", "public_key", "endpoints", "attached_at")
    inst = PeerState(
        cluster_id="east",
        public_key=b"X",
        endpoints=("127.0.0.1:4506",),
        attached_at=1_700_000_000.0,
    )
    # Immutable: tuple attribute set must raise.
    with pytest.raises(AttributeError):
        inst.cluster_id = "west"
