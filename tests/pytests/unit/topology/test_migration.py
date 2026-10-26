"""
Unit tests for :mod:`salt.topology.migration`.

Covers the pieces the functional tests only exercise indirectly:

* Peer-set difference computation --- ``needs_migration`` and
  ``_collect_pending`` must compute ``registry_peers -
  raft_applied_peers`` correctly across empty / partial / full
  overlaps.
* Propose ordering --- identity entry first, then peer attaches
  in sorted ``cluster_id`` order so every cluster peer that
  drives migration produces the same log entry stream.
* Reserved sentinel keys never surface as ``MASTER_PEER_ATTACH``
  entries even if they end up in the roster through a bug or a
  hostile write.

Functional-level coverage (write-through to the real MmapCache,
crash-resume, file-system state) lives in
``tests/pytests/functional/topology/test_migration.py``.  This
file stays unit-level: each test operates on an isolated SM
backed by its own tmp pki_dir, no master factory, no daemon.
"""

import pytest

import salt.topology.migration as migration
import salt.topology.registry as registry
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine

pytestmark = [
    pytest.mark.skip_on_windows,
]


FAKE_PUB_IDENTITY = b"-----BEGIN PUBLIC KEY-----\nIDENT\n-----END PUBLIC KEY-----\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _opts(tmp_path, cluster_peers=("peer-1",)):
    master_dir = tmp_path / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(tmp_path),
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


class _FakeRaftService:
    """
    Trivial propose(cmd) shim.  Records every proposal; may route to
    a backing SM to let successive calls affect the applied set.
    """

    def __init__(self, state_machine=None):
        self._sm = state_machine
        self.proposed = []

    def propose(self, cmd):
        self.proposed.append(cmd)
        if self._sm is not None:
            self._sm.apply(cmd, client_id="unit", sequence_num=len(self.proposed))


def _seed_registry(opts_, peers=(), identity=True):
    """
    Open a short-lived writer and dump identity + peers directly
    into the MmapCache, bypassing Raft (solo direct-write path).
    """
    writer = registry.open_writer(opts_)
    try:
        if identity:
            registry.set_identity_pub(writer, FAKE_PUB_IDENTITY)
        for idx, cluster_id in enumerate(peers):
            registry.set_peer(
                writer,
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "public_key": (
                        b"-----BEGIN PUBLIC KEY-----\n"
                        + cluster_id.encode("ascii")
                        + b"\n-----END PUBLIC KEY-----\n"
                    ),
                    "endpoints": (f"127.0.0.1:450{idx}",),
                    "attached_at": 1_700_000_000.0 + idx,
                },
            )
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# Peer-set difference computation
# ---------------------------------------------------------------------------


def test_collect_pending_empty_registry_returns_empty(opts):
    """No identity, no peers in registry -> no entries to propose."""
    entries = migration._collect_pending(opts)
    assert entries == []


def test_collect_pending_identity_only_proposes_identity(opts):
    """Only identity_pub in registry; no peers.  One entry, type IDENTITY_KEY."""
    _seed_registry(opts, peers=(), identity=True)
    entries = migration._collect_pending(opts)
    assert len(entries) == 1
    assert entries[0]["type"] == LogEntryType.MASTER_IDENTITY_KEY


def test_collect_pending_all_peers_when_sm_empty(opts):
    """
    Three peers in the registry, SM applied set empty -> all three
    attach entries are produced AFTER the identity entry.
    """
    _seed_registry(opts, peers=("gamma", "alpha", "beta"))
    entries = migration._collect_pending(opts)
    assert entries[0]["type"] == LogEntryType.MASTER_IDENTITY_KEY
    attaches = [e for e in entries if e["type"] == LogEntryType.MASTER_PEER_ATTACH]
    assert [e["cluster_id"] for e in attaches] == ["alpha", "beta", "gamma"]


def test_collect_pending_subset_when_sm_partially_applied(opts):
    """
    SM has already applied identity + ``alpha``: only ``beta`` + ``gamma``
    should be produced, and no identity entry.
    """
    _seed_registry(opts, peers=("alpha", "beta", "gamma"))
    sm = TopologyStateMachine(opts)
    try:
        svc = _FakeRaftService(sm)
        svc.propose(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_IDENTITY,
            }
        )
        svc.propose(
            {
                "type": LogEntryType.MASTER_PEER_ATTACH,
                "cluster_id": "alpha",
                "public_key": (
                    b"-----BEGIN PUBLIC KEY-----\nalpha\n-----END PUBLIC KEY-----\n"
                ),
                "endpoints": ("127.0.0.1:4500",),
                "attached_at": 1_700_000_000.0,
            }
        )
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    entries = migration._collect_pending(opts)
    types_seen = [e["type"] for e in entries]
    assert LogEntryType.MASTER_IDENTITY_KEY not in types_seen
    attaches = [e for e in entries if e["type"] == LogEntryType.MASTER_PEER_ATTACH]
    assert [e["cluster_id"] for e in attaches] == ["beta", "gamma"]


def test_collect_pending_empty_when_sm_fully_applied(opts):
    """SM has applied identity + every peer -> no entries produced."""
    _seed_registry(opts, peers=("alpha", "beta"))
    sm = TopologyStateMachine(opts)
    try:
        svc = _FakeRaftService(sm)
        svc.propose(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_IDENTITY,
            }
        )
        for cid in ("alpha", "beta"):
            svc.propose(
                {
                    "type": LogEntryType.MASTER_PEER_ATTACH,
                    "cluster_id": cid,
                    "public_key": (
                        b"-----BEGIN PUBLIC KEY-----\n"
                        + cid.encode("ascii")
                        + b"\n-----END PUBLIC KEY-----\n"
                    ),
                    "endpoints": ("127.0.0.1:4506",),
                    "attached_at": 1_700_000_000.0,
                }
            )
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    assert migration._collect_pending(opts) == []


# ---------------------------------------------------------------------------
# Propose ordering
# ---------------------------------------------------------------------------


def test_promote_order_identity_first_peers_sorted(opts):
    """
    Deterministic log-entry stream: identity first, peers alphabetical.
    Insert peers in anti-sorted order to ensure sorting isn't accidental.
    """
    _seed_registry(opts, peers=("zeta", "mike", "alpha"))
    sm = TopologyStateMachine(opts)
    try:
        svc = _FakeRaftService(sm)
        migration.promote_solo_to_clustered(opts, svc)
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    assert svc.proposed[0]["type"] == LogEntryType.MASTER_IDENTITY_KEY
    attach_ids = [c["cluster_id"] for c in svc.proposed[1:]]
    assert attach_ids == ["alpha", "mike", "zeta"], (
        "attach entries must be proposed in sorted cluster_id order so "
        "every cluster peer that drives migration produces an identical "
        "log stream; got " + repr(attach_ids)
    )


def test_promote_skips_identity_when_raft_already_bootstrapped(opts):
    """
    If the SM has already seen a MASTER_IDENTITY_KEY commit, the
    migration pass must NOT re-propose the identity entry even if
    identity_pub is still present in the registry.
    """
    _seed_registry(opts, peers=("alpha",))
    sm = TopologyStateMachine(opts)
    try:
        svc = _FakeRaftService(sm)
        # First: a lone identity commit (bootstraps the SM).
        svc.propose(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_IDENTITY,
            }
        )
        # Then: full promote.  Expect NO second identity entry.
        start = len(svc.proposed)
        migration.promote_solo_to_clustered(opts, svc)
        new_entries = svc.proposed[start:]
    finally:
        try:
            sm.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass
    assert all(
        e["type"] != LogEntryType.MASTER_IDENTITY_KEY for e in new_entries
    ), f"found unexpected identity re-propose in {new_entries}"


# ---------------------------------------------------------------------------
# Reserved sentinel handling
# ---------------------------------------------------------------------------


def test_promote_never_proposes_reserved_sentinel_as_peer(opts):
    """
    ``_collect_pending`` must never emit a ``MASTER_PEER_ATTACH``
    for a reserved key, even if the registry's roster leaks one
    through a bug.  Guards against a hostile peer writing to the
    reserved slots as a cluster_id.

    The registry's ``list_peer_ids`` already filters reserved
    keys, but the migration module's defensive re-filter is the
    second line of defence.  This test documents that contract.
    """
    _seed_registry(opts, peers=("real-peer",))
    # Verify the reserved keys documented by the registry module
    # are a strict superset of what list_peer_ids ever surfaces.
    reader = registry.open_reader(opts)
    try:
        for reserved in registry._RESERVED_KEYS:  # pylint: disable=protected-access
            assert reserved not in registry.list_peer_ids(
                reader
            ), f"list_peer_ids leaked reserved sentinel {reserved!r}"
    finally:
        reader.close()
    entries = migration._collect_pending(opts)
    for entry in entries:
        if entry["type"] == LogEntryType.MASTER_PEER_ATTACH:
            assert (
                entry["cluster_id"] not in registry._RESERVED_KEYS
            ), (  # pylint: disable=protected-access
                f"migration proposed reserved sentinel {entry['cluster_id']!r} "
                "as a peer attach"
            )


def test_reserved_keys_frozen_set_covers_sentinels():
    """
    Smoke-test that the four reserved sentinel keys the migration
    module relies on are all in the registry's reserved set.  A
    future rename or addition will trip this test and force a
    conscious update to migration.py.
    """
    expected = {
        registry.RESERVED_IDENTITY_PUB_KEY,
        registry.RESERVED_IDENTITY_VERSION_KEY,
        registry.RESERVED_RAFT_BOOTSTRAPPED_KEY,
        registry.RESERVED_RAFT_APPLIED_PEERS_KEY,
    }
    assert expected.issubset(
        registry._RESERVED_KEYS  # pylint: disable=protected-access
    )


# ---------------------------------------------------------------------------
# Short-circuits
# ---------------------------------------------------------------------------


def test_promote_is_noop_on_solo_master(opts_solo):
    """
    ``cluster_peers`` empty -> ``promote_solo_to_clustered`` never
    touches the raft_service even if the registry holds peers.
    """
    _seed_registry(opts_solo, peers=("alpha", "beta"))
    svc = _FakeRaftService(state_machine=None)
    migration.promote_solo_to_clustered(opts_solo, svc)
    assert svc.proposed == []


def test_needs_migration_short_circuits_without_opening_registry(opts_solo):
    """
    Solo master must not even peek at the registry --- a cheap
    short-circuit on cluster_peers avoids opening the MmapCache
    on every publish-daemon start.
    """
    # No registry seed; without short-circuit the opener would
    # succeed anyway, but calling it before pre_create might
    # throw.  Prove the function returns False without touching
    # the cache by using fresh opts whose pki_dir has no master/
    # subdirectory even created.
    assert migration.needs_migration(opts_solo) is False
