"""
Unit tests for :class:`salt.cluster.consensus.raft.topology.PeerState`
serialization schema versioning (RFC implementation-follow-up item 6).

The RFC spec:

* PeerState is serialized as a dict with named keys for both Raft log
  entries and snapshot payloads.
* Every peer dict carries ``__schema_version__`` identifying the field
  layout.
* On apply + restore, unknown versions are refused with a clear log so
  a future field reorder across releases never silently misreads data.
* Pre-schema-version data (no ``__schema_version__`` field) is
  implicitly treated as v1 for backward compatibility --- existing
  snapshots must still restore cleanly.

These tests use :func:`sm.get_snapshot` / :func:`sm.restore_snapshot`
round-trips and construct hand-crafted alternate-layout payloads to
prove the field-reorder scenario is caught.
"""

import logging

import pytest

import salt.topology.registry as registry
import salt.utils.msgpack
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import (
    PEER_STATE_SCHEMA_VERSION,
    TOPOLOGY_SNAPSHOT_VERSION,
    TopologyStateMachine,
    build_peer_attach_entry,
)

pytestmark = [
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def opts(tmp_path):
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
    }


@pytest.fixture
def sm(opts):
    machine = TopologyStateMachine(opts)
    try:
        yield machine
    finally:
        try:
            machine.registry.close()
        except Exception:  # pylint: disable=broad-except
            pass


# ---------------------------------------------------------------------------
# build_peer_attach_entry stamps the schema version
# ---------------------------------------------------------------------------


def test_build_peer_attach_entry_includes_schema_version():
    """Every MASTER_PEER_ATTACH entry carries ``__schema_version__``."""
    entry = build_peer_attach_entry(
        cluster_id="east",
        public_key=b"PEM-EAST",
        endpoints=(),
        attached_at=1_700_000_000.0,
    )
    assert entry["__schema_version__"] == PEER_STATE_SCHEMA_VERSION
    assert entry["type"] == LogEntryType.MASTER_PEER_ATTACH
    assert entry["cluster_id"] == "east"


def test_build_peer_attach_entry_passes_through_extras():
    """Extra kwargs (force_replace, etc.) survive the builder."""
    entry = build_peer_attach_entry(
        cluster_id="east",
        public_key=b"PEM-EAST",
        endpoints=(),
        attached_at=0.0,
        force_replace=True,
    )
    assert entry["force_replace"] is True


def test_peer_state_schema_version_is_an_int():
    """The constant is a plain int (so it round-trips through msgpack cleanly)."""
    assert isinstance(PEER_STATE_SCHEMA_VERSION, int)
    assert PEER_STATE_SCHEMA_VERSION >= 1


# ---------------------------------------------------------------------------
# Round-trip serialize/deserialize preserves all fields
# ---------------------------------------------------------------------------


def test_round_trip_preserves_all_fields(sm):
    """Apply + snapshot + restore_snapshot preserves every PeerState field."""
    original = {
        "cluster_id": "east",
        "public_key": b"PEM-EAST",
        "endpoints": ("127.0.0.1:4506", "10.0.0.2:4506"),
        "attached_at": 1_700_000_000.0,
    }
    sm.apply(
        build_peer_attach_entry(
            cluster_id=original["cluster_id"],
            public_key=original["public_key"],
            endpoints=original["endpoints"],
            attached_at=original["attached_at"],
        )
    )
    snap = sm.get_snapshot()
    payload = salt.utils.msgpack.unpackb(bytes(snap), raw=False)
    assert payload["version"] == TOPOLOGY_SNAPSHOT_VERSION
    assert "east" in payload["peers"]
    east = payload["peers"]["east"]
    assert east["__schema_version__"] == PEER_STATE_SCHEMA_VERSION
    assert east["cluster_id"] == "east"
    assert east["public_key"] == b"PEM-EAST"
    assert tuple(east["endpoints"]) == original["endpoints"]
    assert east["attached_at"] == pytest.approx(original["attached_at"])

    # And restore_snapshot repopulates the registry byte-identically.
    sm.restore_snapshot(snap)
    restored = registry.get_peer(sm.registry, "east")
    assert restored is not None
    assert restored["public_key"] == b"PEM-EAST"
    assert tuple(restored["endpoints"]) == original["endpoints"]
    assert restored["attached_at"] == pytest.approx(original["attached_at"])


def test_round_trip_preserves_multiple_peers(sm):
    """Snapshot restore handles multiple peers without cross-contamination."""
    peers = {
        "east": (b"PEM-EAST", ("127.0.0.1:4506",), 1.0),
        "south": (b"PEM-SOUTH", ("127.0.0.1:4507",), 2.0),
        "west": (b"PEM-WEST", (), 3.0),
    }
    for cid, (pub, eps, at) in peers.items():
        sm.apply(
            build_peer_attach_entry(
                cluster_id=cid, public_key=pub, endpoints=eps, attached_at=at
            )
        )
    snap = sm.get_snapshot()
    sm.restore_snapshot(snap)
    for cid, (pub, eps, at) in peers.items():
        restored = registry.get_peer(sm.registry, cid)
        assert restored is not None, cid
        assert restored["public_key"] == pub
        assert tuple(restored["endpoints"]) == eps
        assert restored["attached_at"] == pytest.approx(at)


# ---------------------------------------------------------------------------
# Older-version (and unknown-version) snapshots refuse to restore
# ---------------------------------------------------------------------------


def _bogus_version_snapshot(peer_version):
    """Build a snapshot payload where a peer carries *peer_version*."""
    return salt.utils.msgpack.packb(
        {
            "version": TOPOLOGY_SNAPSHOT_VERSION,
            "identity_pub": b"",
            "identity_version": 0,
            "peers": {
                "east": {
                    "__schema_version__": peer_version,
                    "cluster_id": "east",
                    "public_key": b"PEM-EAST",
                    "endpoints": (),
                    "attached_at": 0.0,
                },
            },
        },
        use_bin_type=True,
    )


def test_restore_snapshot_refuses_future_peer_schema_version(sm, caplog):
    """A peer dict with __schema_version__=999 is REFUSED (no partial restore)."""
    # Pre-apply a real peer so we can prove the registry is untouched.
    sm.apply(
        build_peer_attach_entry(
            cluster_id="south",
            public_key=b"PEM-SOUTH",
            endpoints=(),
            attached_at=1.0,
        )
    )
    bogus = _bogus_version_snapshot(peer_version=999)
    with caplog.at_level(logging.ERROR, logger="salt.cluster.consensus.raft.topology"):
        sm.restore_snapshot(bogus)
    assert registry.get_peer(sm.registry, "east") is None
    # Pre-existing peer must still be present (restore refused, didn't blow
    # away the registry).
    assert registry.get_peer(sm.registry, "south") is not None
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "__schema_version__" in text


def test_restore_snapshot_refuses_zero_peer_schema_version(sm, caplog):
    """``__schema_version__ = 0`` is not in the known set -> refuse."""
    bogus = _bogus_version_snapshot(peer_version=0)
    with caplog.at_level(logging.ERROR, logger="salt.cluster.consensus.raft.topology"):
        sm.restore_snapshot(bogus)
    assert registry.get_peer(sm.registry, "east") is None


def test_restore_snapshot_refuses_garbage_peer_schema_version(sm, caplog):
    """A non-int ``__schema_version__`` is REFUSED (not silently coerced)."""
    bogus = _bogus_version_snapshot(peer_version="not-an-int")
    with caplog.at_level(logging.ERROR, logger="salt.cluster.consensus.raft.topology"):
        sm.restore_snapshot(bogus)
    assert registry.get_peer(sm.registry, "east") is None


# ---------------------------------------------------------------------------
# Backward compat: pre-schema-version snapshots still restore (treated as v1)
# ---------------------------------------------------------------------------


def test_restore_snapshot_pre_schema_version_treated_as_v1(sm):
    """An existing snapshot without __schema_version__ restores as v1."""
    legacy = salt.utils.msgpack.packb(
        {
            "version": TOPOLOGY_SNAPSHOT_VERSION,
            "identity_pub": b"",
            "identity_version": 0,
            "peers": {
                "east": {
                    # Deliberately NO __schema_version__ field.
                    "cluster_id": "east",
                    "public_key": b"PEM-EAST-OLD",
                    "endpoints": ("127.0.0.1:4506",),
                    "attached_at": 1.0,
                },
            },
        },
        use_bin_type=True,
    )
    sm.restore_snapshot(legacy)
    restored = registry.get_peer(sm.registry, "east")
    assert restored is not None
    assert restored["public_key"] == b"PEM-EAST-OLD"
    assert tuple(restored["endpoints"]) == ("127.0.0.1:4506",)


# ---------------------------------------------------------------------------
# Field-reorder robustness: alternate-order payload hand-crafted by a
# hypothetical future release still deserializes correctly because the dict
# is keyed by name (not position).
# ---------------------------------------------------------------------------


def test_restore_snapshot_handles_alternate_field_order(sm):
    """A snapshot where peer dict keys were serialized in a different order
    must still restore --- the fix is to key by name, not position."""
    # Hand-serialize a peer dict in a totally different key order.  msgpack
    # preserves insertion order for dicts; we're proving that the restore
    # code doesn't assume cluster_id/public_key/endpoints/attached_at order.
    alternate_order = {
        "attached_at": 42.0,
        "endpoints": ("10.0.0.9:4506",),
        "__schema_version__": PEER_STATE_SCHEMA_VERSION,
        "public_key": b"PEM-EAST-ALT",
        "cluster_id": "east",
    }
    snap = salt.utils.msgpack.packb(
        {
            "version": TOPOLOGY_SNAPSHOT_VERSION,
            "identity_pub": b"",
            "identity_version": 0,
            "peers": {"east": alternate_order},
        },
        use_bin_type=True,
    )
    sm.restore_snapshot(snap)
    restored = registry.get_peer(sm.registry, "east")
    assert restored is not None
    # All four fields survive the alternate-order serialization.
    assert restored["cluster_id"] == "east"
    assert restored["public_key"] == b"PEM-EAST-ALT"
    assert tuple(restored["endpoints"]) == ("10.0.0.9:4506",)
    assert restored["attached_at"] == pytest.approx(42.0)


# ---------------------------------------------------------------------------
# MASTER_PEER_ATTACH apply path: unknown __schema_version__ is rejected
# ---------------------------------------------------------------------------


def test_apply_peer_attach_rejects_future_schema_version(sm, caplog):
    """Apply handler refuses an entry with __schema_version__ beyond the
    known set, with a clear CRITICAL log."""
    entry = {
        "type": LogEntryType.MASTER_PEER_ATTACH,
        "__schema_version__": 42,
        "cluster_id": "east",
        "public_key": b"PEM-EAST",
        "endpoints": (),
        "attached_at": 0.0,
    }
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        sm.apply(entry)
    assert registry.get_peer(sm.registry, "east") is None
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "__schema_version__" in text


def test_apply_peer_attach_absent_schema_version_treated_as_v1(sm):
    """A legacy entry without __schema_version__ still applies cleanly."""
    legacy_entry = {
        "type": LogEntryType.MASTER_PEER_ATTACH,
        # Deliberately NO __schema_version__ field.
        "cluster_id": "east",
        "public_key": b"PEM-EAST-LEGACY",
        "endpoints": (),
        "attached_at": 1.0,
    }
    sm.apply(legacy_entry)
    restored = registry.get_peer(sm.registry, "east")
    assert restored is not None
    assert restored["public_key"] == b"PEM-EAST-LEGACY"
