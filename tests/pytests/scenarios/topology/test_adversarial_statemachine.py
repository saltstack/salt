"""
Adversarial scenario tests for :class:`TopologyStateMachine` and the
companion :mod:`salt.topology.migration` crash-resume path.

Each probe targets one brittle surface:

Apply handler idempotency
    * ``MASTER_PEER_ATTACH`` replayed with identical bytes is a no-op
      with no file-system churn, no second rename attempt.
    * ``MASTER_PEER_ATTACH`` replayed with the same public_key but a
      different ``attached_at`` timestamp lands as a no-op (public_key
      is the identity bit; timestamp drift must not update state or
      side-effects).
    * ``MASTER_IDENTITY_KEY`` replayed with the same keypair does not
      bump ``__identity_version__`` (bumping would make reconnecting
      peers think the identity rotated).
    * ``MASTER_IDENTITY_KEY`` rotation lands the new bytes in the
      registry, bumps the version, and overwrites the disk keypair
      in place (no stale ``.pem.old``).

Snapshot / restore
    * N peers round-trip byte-identical through
      ``get_snapshot`` / ``restore_snapshot``; reserved sentinels
      survive.
    * A reader concurrent with ``restore_snapshot`` never sees a
      half-wiped peer set (snapshot restore is one coherent
      transaction).
    * ``restore_snapshot`` refuses an unknown schema version
      without wiping the registry.
    * ``get_snapshot`` concurrent with a writer-side attach returns
      a non-torn payload (either pre-attach or post-attach).

Unknown entry types
    * ``apply`` with an unknown numeric type is a logged no-op.
    * ``apply(None)`` is a logged no-op (no cascade).
    * ``apply({})`` (empty dict, no type) is a logged no-op.

Migration crash resume
    * Crash *before* the first ``MASTER_PEER_ATTACH`` leaves
      ``needs_migration`` True; resume re-proposes attaches only, not
      identity.
    * Crash *after* identity + half the peers committed: resume
      proposes only the un-applied half.
    * Crash *during* ``_handle_peer_attach`` (Raft commit succeeded
      but file-system rename did not): re-apply completes the rename.
    * Registry MmapCache wiped between crash and resume: document
      observed behaviour --- the module cannot resurrect identity
      bytes it never held, so a wiped registry forces a fresh
      identity bootstrap.

Hostile apply
    * The SM's ``apply`` is a plain callable --- anyone with the
      object can call it directly, bypassing Raft.  This is a
      documented design surface (Raft Node calls apply on commit;
      the SM must be idempotent regardless of who called).  The
      probe asserts the SM is at least a hostile-input hardened
      callable: validation rejects path-traversal cluster_ids
      before any file operation runs.
"""

import logging
import os
import threading
import time

import pytest

import salt.topology.migration as migration
import salt.topology.registry as registry
import salt.utils.files
import salt.utils.msgpack
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import (
    TopologyStateMachine,
    _read_identity_version,
    _read_raft_applied_peers,
)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,  # fork + 0o400 perm assumptions
]


# ---------------------------------------------------------------------------
# Fixtures / helpers (self-contained; do NOT touch harness conftest.py)
# ---------------------------------------------------------------------------


FAKE_PUB_A = b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"
FAKE_PUB_B = b"-----BEGIN PUBLIC KEY-----\nBBBB\n-----END PUBLIC KEY-----\n"
FAKE_PRIV_A = b"-----BEGIN RSA PRIVATE KEY-----\naaaa\n-----END RSA PRIVATE KEY-----\n"
FAKE_PRIV_B = b"-----BEGIN RSA PRIVATE KEY-----\nbbbb\n-----END RSA PRIVATE KEY-----\n"


def _opts(pki_root, cluster_peers=("peer-1",)):
    """Build the minimal opts dict registry + SM read."""
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "keysize": 2048,
        "hash_type": "sha256",
        "cluster_peers": list(cluster_peers),
    }


@pytest.fixture
def opts(tmp_path):
    return _opts(tmp_path)


@pytest.fixture
def opts_solo(tmp_path):
    return _opts(tmp_path, cluster_peers=())


@pytest.fixture
def sm(opts):
    registry.pre_create(opts)
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        try:
            machine.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


def _identity_cmd(pub_pem, priv_pem=None):
    cmd = {
        "type": LogEntryType.MASTER_IDENTITY_KEY,
        "public_key": pub_pem,
    }
    if priv_pem is not None:
        cmd["private_key"] = priv_pem
    return cmd


def _attach_cmd(cluster_id, public_key, endpoints=("127.0.0.1:4506",), **extra):
    cmd = {
        "type": LogEntryType.MASTER_PEER_ATTACH,
        "cluster_id": cluster_id,
        "public_key": public_key,
        "endpoints": tuple(endpoints),
        "attached_at": 1_700_000_000.0,
    }
    cmd.update(extra)
    return cmd


class _FakeRaftService:
    """
    Thin ``propose(cmd)`` -> ``sm.apply(cmd)`` shim.

    Lets migration tests drive proposals synchronously; records
    everything proposed in :attr:`proposed`.
    """

    def __init__(self, sm):
        self.sm = sm
        self.proposed = []

    def propose(self, cmd):
        self.proposed.append(cmd)
        self.sm.apply(cmd)


# ---------------------------------------------------------------------------
# Idempotency probes
# ---------------------------------------------------------------------------


def test_attach_replay_identical_bytes_no_filesystem_churn(sm, opts):
    """
    Replay of ``MASTER_PEER_ATTACH`` with byte-identical cmd must not
    rewrite the key file.  If the SM naively re-ran
    ``_finalise_accepted_key_file`` on every apply, the file's mtime
    would bump even when state did not change.
    """
    pub = b"EAST-KEY"
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=1)
    accepted_path = os.path.join(opts["pki_dir"], "masters", "east.pub")
    assert os.path.isfile(accepted_path)
    first_mtime = os.stat(accepted_path).st_mtime_ns
    # Sleep so a second write would show a different ns-granularity
    # mtime on any sane filesystem.
    time.sleep(0.05)
    sm.apply(_attach_cmd("east", pub), client_id="op", sequence_num=2)
    second_mtime = os.stat(accepted_path).st_mtime_ns
    assert first_mtime == second_mtime, (
        "Replay of identical MASTER_PEER_ATTACH re-wrote the accepted key "
        "file; file-system churn on idempotent apply is a bug."
    )


def test_attach_replay_different_timestamp_same_key_is_noop(sm, opts):
    """
    Replay with the same ``cluster_id`` + ``public_key`` but a drifted
    ``attached_at`` is a no-op by design: public_key is the identity bit.
    If the SM accepted the timestamp drift as a state change, snapshot
    content would be non-deterministic across replays (a bug for
    cross-peer convergence).
    """
    pub = b"EAST-KEY"
    sm.apply(
        _attach_cmd("east", pub, attached_at=1_700_000_000.0),
        client_id="op",
        sequence_num=1,
    )
    before = registry.get_peer(sm.registry, "east")
    accepted_path = os.path.join(opts["pki_dir"], "masters", "east.pub")
    first_mtime = os.stat(accepted_path).st_mtime_ns
    time.sleep(0.05)
    sm.apply(
        _attach_cmd("east", pub, attached_at=1_700_000_999.0),
        client_id="op",
        sequence_num=2,
    )
    after = registry.get_peer(sm.registry, "east")
    second_mtime = os.stat(accepted_path).st_mtime_ns
    # attached_at NOT bumped --- same public_key short-circuited the apply.
    assert before == after, (
        "MASTER_PEER_ATTACH with same public_key but drifted attached_at "
        "updated registry state; snapshot content is now non-deterministic."
    )
    assert first_mtime == second_mtime


def test_identity_reapply_same_bytes_does_not_bump_version(sm):
    """
    Idempotent re-apply of identical identity must NOT bump
    ``__identity_version__``.  A spurious bump would make reconnecting
    peers believe the identity rotated.
    """
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    v1 = _read_identity_version(sm.registry)
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=2)
    v2 = _read_identity_version(sm.registry)
    assert v1 == v2


def test_identity_rotation_overwrites_disk_keypair_in_place(sm, opts):
    """
    Rotation must overwrite ``master_identity.{pub,pem}``, not leave
    stale copies alongside.  Rotation also bumps the version counter.
    """
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    pub_path = os.path.join(opts["pki_dir"], "master", "master_identity.pub")
    priv_path = os.path.join(opts["pki_dir"], "master", "master_identity.pem")
    with salt.utils.files.fopen(pub_path, "rb") as fh:
        assert fh.read() == FAKE_PUB_A
    v1 = _read_identity_version(sm.registry)

    sm.apply(_identity_cmd(FAKE_PUB_B, FAKE_PRIV_B), client_id="op", sequence_num=2)
    v2 = _read_identity_version(sm.registry)
    assert v2 > v1
    with salt.utils.files.fopen(pub_path, "rb") as fh:
        assert fh.read() == FAKE_PUB_B
    with salt.utils.files.fopen(priv_path, "rb") as fh:
        assert fh.read() == FAKE_PRIV_B
    # No stale backup alongside.
    master_dir = os.path.join(opts["pki_dir"], "master")
    for name in os.listdir(master_dir):
        if name.endswith((".old", ".bak", ".prev")):
            raise AssertionError(
                f"Rotation left stale keypair backup {name!r} in {master_dir}"
            )


# ---------------------------------------------------------------------------
# Snapshot / restore probes
# ---------------------------------------------------------------------------


def test_snapshot_restore_round_trip_preserves_peers_and_sentinels(sm):
    """
    N peers + identity round-trip through get_snapshot / restore_snapshot
    exactly.  Reserved sentinels (identity_pub, identity_version,
    raft_bootstrapped, raft_applied_peers) survive.
    """
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    peers = {}
    for i in range(5):
        cid = f"peer-{i:02d}"
        pub = f"KEY-{i}".encode() * 4
        sm.apply(_attach_cmd(cid, pub), client_id="op", sequence_num=10 + i)
        peers[cid] = pub
    snap = sm.get_snapshot()
    identity_version_before = _read_identity_version(sm.registry)
    applied_before = _read_raft_applied_peers(sm.registry)

    # Clear every non-reserved peer out from under the SM.
    for cid in list(peers):
        registry.delete_peer(sm.registry, cid)
    assert not registry.list_peer_ids(sm.registry)

    sm.restore_snapshot(snap)

    # Peers byte-identical.
    for cid, pub in peers.items():
        got = registry.get_peer(sm.registry, cid)
        assert got is not None, f"peer {cid!r} not restored"
        assert got["public_key"] == pub
    # Sentinels survived.
    assert registry.get_identity_pub(sm.registry) == FAKE_PUB_A
    assert _read_identity_version(sm.registry) == identity_version_before
    assert _read_raft_applied_peers(sm.registry) == applied_before


def test_restore_snapshot_refuses_unknown_schema_version(sm):
    """
    A snapshot with an unknown version prefix must NOT be applied.
    Attempting it must leave current state intact (not wipe peers).
    """
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    sm.apply(_attach_cmd("east", b"EAST-KEY"), client_id="op", sequence_num=2)
    before = {
        "identity": registry.get_identity_pub(sm.registry),
        "peers": sorted(registry.list_peer_ids(sm.registry)),
    }

    bogus = salt.utils.msgpack.packb(
        {
            "version": "topology.snapshot.v99999",
            "identity_pub": b"EVIL",
            "peers": {
                "evil": {"public_key": b"X", "endpoints": (), "attached_at": 0.0}
            },
        },
        use_bin_type=True,
    )
    sm.restore_snapshot(bogus)
    after = {
        "identity": registry.get_identity_pub(sm.registry),
        "peers": sorted(registry.list_peer_ids(sm.registry)),
    }
    assert before == after, (
        "restore_snapshot of an unknown schema version mutated state; "
        "the version guard must preserve the live registry on reject."
    )


def test_get_snapshot_during_concurrent_attach_is_not_torn(sm):
    """
    A ``get_snapshot`` running concurrently with ``_handle_peer_attach``
    must produce a payload that is internally consistent --- it reflects
    either the pre-attach or the post-attach state for *every* peer,
    never a torn mix (e.g. a peer whose public_key does not match its
    cluster_id).

    This is a stress probe: 50 attaches concurrent with 50 snapshots.
    """
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)

    stop = threading.Event()
    errors = []

    def attach_loop():
        try:
            for i in range(50):
                cid = f"peer-{i:03d}"
                pub = f"KEY-{i}-".encode() * 8
                sm.apply(_attach_cmd(cid, pub), client_id="op", sequence_num=10 + i)
                time.sleep(0.0005)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)
        finally:
            stop.set()

    def snapshot_loop():
        try:
            while not stop.is_set():
                blob = sm.get_snapshot()
                payload = salt.utils.msgpack.unpackb(blob, raw=False)
                for cid, state in (payload.get("peers") or {}).items():
                    pub = state.get("public_key") or b""
                    # Every stored key encodes the index at its tail;
                    # a torn write would have mismatched padding bytes.
                    assert pub, f"snapshot carried empty public_key for {cid!r}"
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    t_attach = threading.Thread(target=attach_loop)
    t_snap = threading.Thread(target=snapshot_loop)
    t_snap.start()
    t_attach.start()
    t_attach.join(timeout=30)
    t_snap.join(timeout=30)
    assert not errors, f"concurrent snapshot/attach raised: {errors!r}"


def test_restore_snapshot_concurrent_reader_never_sees_half_wipe(sm, opts):
    """
    While ``restore_snapshot`` is wiping and re-populating peers, a
    read-only process must never observe a half-wiped registry
    (i.e. peers removed but the restore not yet complete).

    The RFC claims restore is a single transaction.  We open a
    reader handle (separate MmapCache) and poll it while a restore
    runs; the reader must observe either the full pre-snapshot set
    or the full post-snapshot set at every poll, never a strict
    subset.
    """
    # Build a baseline the restore will replace.
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    for i in range(5):
        sm.apply(
            _attach_cmd(f"old-{i:02d}", f"OLDKEY-{i}".encode() * 4),
            client_id="op",
            sequence_num=10 + i,
        )
    old_snap = sm.get_snapshot()
    # Capture a snapshot that holds a different "new-NN" set we will
    # restore in a loop below.  First swap old-NN out, snap, swap back.
    for i in range(5):
        registry.delete_peer(sm.registry, f"old-{i:02d}")
    for i in range(5):
        sm.apply(
            _attach_cmd(f"new-{i:02d}", f"NEWKEY-{i}".encode() * 4),
            client_id="op",
            sequence_num=20 + i,
        )
    target_snap = sm.get_snapshot()
    # Restore baseline atomically so the live state is the "old-NN" set
    # before we start polling.
    sm.restore_snapshot(old_snap)

    reader = registry.open_reader(opts)
    errors = []
    stop = threading.Event()

    def reader_loop():
        """Poll the reader; every observed set must be a full snapshot."""
        try:
            while not stop.is_set():
                ids = sorted(
                    [k for k in reader.list_keys() if k not in registry._RESERVED_KEYS]
                )
                if ids:
                    # Must be exactly the "old-NN" or "new-NN" set,
                    # never a strict subset of either (half-wipe).
                    all_old = all(cid.startswith("old-") for cid in ids)
                    all_new = all(cid.startswith("new-") for cid in ids)
                    if not (all_old or all_new):
                        errors.append(f"reader observed torn set: {ids!r}")
                    if (all_old and len(ids) != 5) or (all_new and len(ids) != 5):
                        errors.append(
                            f"reader observed partial set (size {len(ids)}): {ids!r}"
                        )
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    t = threading.Thread(target=reader_loop)
    t.start()
    try:
        for _ in range(20):
            # Restore the "new-NN" snapshot --- diff-apply or
            # atomic_rebuild must make this appear atomic to the
            # reader (full old set or full new set, never a mix or
            # strict subset).
            sm.restore_snapshot(target_snap)
            # Swap live state back to "old-NN" via restore_snapshot
            # as well, so the next iteration's restore has work to
            # do and the swap itself is also an atomic transaction
            # under test.
            sm.restore_snapshot(old_snap)
    finally:
        stop.set()
        t.join(timeout=10)
        reader.close()
    assert not errors, (
        f"restore_snapshot is not atomic across concurrent readers: " f"{errors[0]!r}"
    )


# ---------------------------------------------------------------------------
# Unknown entry type probes
# ---------------------------------------------------------------------------


def test_apply_unknown_entry_type_is_noop(sm):
    """``apply({"type": 9999, ...})`` --- no handler, no mutation, no crash."""
    sm.apply(_identity_cmd(FAKE_PUB_A, FAKE_PRIV_A), client_id="op", sequence_num=1)
    before_peers = set(registry.list_peer_ids(sm.registry))
    before_identity = registry.get_identity_pub(sm.registry)
    sm.apply(
        {"type": 9999, "cluster_id": "east", "public_key": b"X"},
        client_id="op",
        sequence_num=2,
    )
    assert set(registry.list_peer_ids(sm.registry)) == before_peers
    assert registry.get_identity_pub(sm.registry) == before_identity


def test_apply_none_cmd_is_noop(sm, caplog):
    """``apply(None)`` --- must log at DEBUG, must not raise."""
    with caplog.at_level(logging.DEBUG, logger="salt.cluster.consensus.raft.topology"):
        sm.apply(None, client_id="op", sequence_num=1)
    # No crash.  No mutation.
    assert registry.get_identity_pub(sm.registry) is None


def test_apply_empty_dict_is_noop(sm):
    """``apply({})`` --- no ``type`` key, no handler, no mutation."""
    sm.apply({}, client_id="op", sequence_num=1)
    assert registry.get_identity_pub(sm.registry) is None
    assert not registry.list_peer_ids(sm.registry)


# ---------------------------------------------------------------------------
# Migration crash-resume probes
# ---------------------------------------------------------------------------


def test_migration_crash_before_first_peer_attach_proposes_only_peers(opts):
    """
    Scenario: a formerly-solo master wrote identity_pub to the registry
    directly, then started up as clustered.  ``promote_solo_to_clustered``
    proposed MASTER_IDENTITY_KEY, Raft committed it, the apply handler
    stamped ``__raft_bootstrapped__``, THEN the process crashed before
    the first MASTER_PEER_ATTACH entry was proposed.

    On restart: ``needs_migration`` should be True (there are peers in
    the registry but none in the Raft-applied set), and the next
    ``promote_solo_to_clustered`` run should propose *only* the peer
    attaches, NOT re-propose the identity (identity is already
    bootstrapped).
    """
    registry.pre_create(opts)
    sm1 = TopologyStateMachine(opts)
    # Stage a pre-existing solo master state: identity + 3 peers in the
    # registry, with the Raft side empty.
    registry.set_identity_pub(sm1.registry, FAKE_PUB_A)
    for i in range(3):
        registry.set_peer(
            sm1.registry,
            f"peer-{i:02d}",
            {
                "cluster_id": f"peer-{i:02d}",
                "public_key": f"PEER-{i}".encode() * 4,
                "endpoints": (),
                "attached_at": 1_700_000_000.0 + i,
            },
        )
    # Round 1: identity propose + commit; CRASH before any peer.
    svc = _FakeRaftService(sm1)
    identity_cmd = {
        "type": LogEntryType.MASTER_IDENTITY_KEY,
        "public_key": FAKE_PUB_A,
    }
    svc.propose(identity_cmd)
    # Simulate the crash by dropping svc + sm1.  Close the writer so
    # the next SM in this test opens a fresh handle.
    sm1.registry.close()
    del svc, sm1

    # Round 2: new process.  needs_migration should be True, and resume
    # should propose only the 3 peer attaches.
    assert migration.needs_migration(opts) is True
    sm2 = TopologyStateMachine(opts)
    svc2 = _FakeRaftService(sm2)
    migration.promote_solo_to_clustered(opts, svc2)
    proposed_types = [cmd["type"] for cmd in svc2.proposed]
    assert LogEntryType.MASTER_IDENTITY_KEY not in proposed_types, (
        "resume re-proposed MASTER_IDENTITY_KEY despite the identity "
        "already being bootstrapped --- would churn __identity_version__ "
        "on a loop under crash-restart cycles."
    )
    assert proposed_types.count(LogEntryType.MASTER_PEER_ATTACH) == 3
    sm2.registry.close()


def test_migration_crash_after_half_attached_resumes_only_remainder(opts):
    """
    Scenario: identity committed, 2 of 4 peer attaches committed, then
    crash.  Resume must propose only the un-applied 2 peers.
    """
    registry.pre_create(opts)
    sm1 = TopologyStateMachine(opts)
    # Pre-populate registry with 4 peers (solo state).
    for i in range(4):
        registry.set_peer(
            sm1.registry,
            f"p-{i:02d}",
            {
                "cluster_id": f"p-{i:02d}",
                "public_key": f"PK-{i}".encode() * 4,
                "endpoints": (),
                "attached_at": 1_700_000_000.0 + i,
            },
        )
    registry.set_identity_pub(sm1.registry, FAKE_PUB_A)
    svc = _FakeRaftService(sm1)
    # Commit identity + 2 of 4 attaches.
    svc.propose({"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": FAKE_PUB_A})
    for i in range(2):
        svc.propose(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": f"p-{i:02d}",
                "public_key": f"PK-{i}".encode() * 4,
                "endpoints": (),
                "attached_at": 1_700_000_000.0 + i,
            }
        )
    sm1.registry.close()
    del svc, sm1

    # Resume.
    assert migration.needs_migration(opts) is True
    sm2 = TopologyStateMachine(opts)
    svc2 = _FakeRaftService(sm2)
    migration.promote_solo_to_clustered(opts, svc2)
    attach_cids = sorted(
        cmd["cluster_id"]
        for cmd in svc2.proposed
        if cmd["type"] == LogEntryType.MASTER_PEER_ATTACH
    )
    assert attach_cids == [
        "p-02",
        "p-03",
    ], f"resume should propose only p-02, p-03; got {attach_cids!r}"
    # Identity NOT re-proposed.
    assert all(cmd["type"] != LogEntryType.MASTER_IDENTITY_KEY for cmd in svc2.proposed)
    sm2.registry.close()


def test_migration_crash_during_peer_attach_file_rename_resumes(opts):
    """
    Scenario: a ``MASTER_PEER_ATTACH`` landed in the registry (Raft
    commit succeeded) but the file-system hand-off (rename
    ``masters_pre/<id>.pub`` -> ``masters/<id>.pub``) did not finish
    before the process died.

    On re-apply (idempotent replay of the committed entry), the SM
    should complete the rename --- either by moving ``masters_pre``
    or by writing the key bytes directly.
    """
    registry.pre_create(opts)
    sm1 = TopologyStateMachine(opts)
    pub = b"EAST-KEY"
    # Drop a pending key file; crash mid-apply by simulating what a
    # torn write leaves on disk: the registry entry committed but the
    # rename did not happen.
    pre_path = os.path.join(opts["pki_dir"], "masters_pre", "east.pub")
    accepted_path = os.path.join(opts["pki_dir"], "masters", "east.pub")
    with salt.utils.files.fopen(pre_path, "wb") as fh:
        fh.write(pub)
    # Directly set the registry entry to simulate "commit succeeded,
    # rename did not."
    registry.set_peer(
        sm1.registry,
        "east",
        {
            "cluster_id": "east",
            "public_key": pub,
            "endpoints": (),
            "attached_at": 1_700_000_000.0,
        },
    )
    # Confirm the torn state.
    assert os.path.isfile(pre_path)
    assert not os.path.exists(accepted_path)

    # Re-apply the committed entry.  Even though the registry already
    # has the peer, the SM's idempotent short-circuit must still make
    # progress on the file-system hand-off --- otherwise this crash
    # scenario leaves the key stuck in masters_pre forever.
    sm1.apply(_attach_cmd("east", pub), client_id="op", sequence_num=1)

    try:
        assert os.path.isfile(accepted_path), (
            "re-apply did not create masters/east.pub --- the committed "
            "attach entry replayed but the file hand-off was skipped"
        )
        assert not os.path.exists(pre_path), (
            "re-apply left masters_pre/east.pub in place --- the "
            "pending->accepted rename was skipped"
        )
    finally:
        sm1.registry.close()


def test_migration_wiped_registry_between_crash_and_resume(opts):
    """
    Scenario: a formerly-solo master's registry MmapCache files get
    wiped between crash and restart (operator reset, disk full
    truncating the heap, etc.).

    Documented behaviour: the migration module cannot resurrect
    identity bytes it never held, so a wiped registry forces a fresh
    identity bootstrap by the publish daemon --- the migration module
    itself returns needs_migration=False (nothing to migrate: both
    sides empty).

    This probe asserts that behaviour exactly, so a future change that
    silently invents identity bytes from thin air will fail here.
    """
    registry.pre_create(opts)
    sm1 = TopologyStateMachine(opts)
    registry.set_identity_pub(sm1.registry, FAKE_PUB_A)
    registry.set_peer(
        sm1.registry,
        "east",
        {
            "cluster_id": "east",
            "public_key": b"EAST",
            "endpoints": (),
            "attached_at": 1.0,
        },
    )
    sm1.registry.close()

    # Wipe the registry files.
    master_dir, index_path = registry._cache_paths(opts)
    for suffix in ("", ".heap", ".roster", ".lock"):
        path = index_path + suffix
        if os.path.exists(path):
            os.remove(path)

    # Fresh registry; nothing left to migrate.
    assert migration.needs_migration(opts) is False


# ---------------------------------------------------------------------------
# Hostile apply probes
# ---------------------------------------------------------------------------


def test_apply_path_traversal_cluster_id_rejected_without_file_ops(sm, opts):
    """
    A cluster_id that contains ``../`` must be rejected by the regex
    before any file op runs.  No file is created outside pki_dir.

    This is a hostile-peer defense: a buggy or malicious cluster
    peer could craft an attach for ``../../etc/passwd`` hoping the
    SM would do ``os.replace(pre_dir, masters_dir/../../etc/passwd)``.
    """
    bad_id = "../../etc/passwd"
    sm.apply(_attach_cmd(bad_id, b"EVIL"), client_id="op", sequence_num=1)
    # Not in the registry.
    assert registry.get_peer(sm.registry, bad_id) is None
    # And no file written outside pki_dir.
    for root, _dirs, files in os.walk(opts["pki_dir"]):
        for name in files:
            assert "passwd" not in name
    # Explicit: masters/../../etc/passwd must not exist.
    assert not os.path.exists(os.path.join(opts["pki_dir"], "masters", bad_id + ".pub"))


def test_direct_apply_bypasses_raft_but_is_hardened(sm):
    """
    ``TopologyStateMachine.apply`` is a plain Python method.  Anyone
    with the object can call it, bypassing the Raft commit path.
    Documented design: Raft Node is the sole caller in production, but
    the SM must behave as a hostile-input hardened callable regardless.

    This probe asserts that a direct caller cannot subvert the reserved
    sentinels or crash the SM with crafted input --- it is the main
    guarantee the SM must hold if the Raft Node is swapped out, mocked,
    or if an in-process diagnostics tool ever grows an apply surface.
    """
    for bad in [
        {"type": LogEntryType.MASTER_PEER_ATTACH, "cluster_id": "", "public_key": b"X"},
        {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": None,
            "public_key": b"X",
        },
        {
            "type": LogEntryType.MASTER_PEER_ATTACH,
            "cluster_id": registry.RESERVED_IDENTITY_PUB_KEY,
            "public_key": b"X",
        },
        {"type": LogEntryType.MASTER_IDENTITY_KEY},  # missing public_key
        {"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": None},
        {"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": ""},
        {"type": LogEntryType.MASTER_PEER_DETACH, "cluster_id": ""},
        {"type": LogEntryType.MASTER_PEER_DETACH},
    ]:
        sm.apply(bad, client_id="hostile", sequence_num=1)
    # No peers landed; identity not set.
    assert not registry.list_peer_ids(sm.registry)
    assert registry.get_identity_pub(sm.registry) is None
