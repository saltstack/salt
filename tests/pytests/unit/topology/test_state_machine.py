"""
Unit tests for :mod:`salt.cluster.consensus.raft.topology`.

Covers the pieces the functional tests only exercise indirectly:

* Dispatch table shape --- every ``MASTER_*`` ``LogEntryType`` maps
  to the right handler, and no stale ``MASTER_PEER_ROUTE`` /
  ``MASTER_PEER_SUMMARY`` entries slipped in.
* ``PeerState`` NamedTuple shape --- correct fields, immutable.
* Snapshot schema version prefix --- ``get_snapshot`` emits the
  current :data:`TOPOLOGY_SNAPSHOT_VERSION` and
  ``restore_snapshot`` refuses older/unknown versions as a no-op.
* ``generate_identity_key`` --- returns ``(pub_pem, priv_pem)`` as
  bytes and the public half parses through
  :class:`salt.crypt.PublicKey.from_str`.

Functional-level coverage (write-through to the real MmapCache,
file-move semantics, hostile-peer validation) lives in
``tests/pytests/functional/topology/test_state_machine.py`` --- this
file stays unit-level and operates on an isolated SM backed by its
own tmp pki_dir.
"""

import pytest

import salt.crypt
import salt.topology.registry as registry
import salt.utils.msgpack
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import (
    TOPOLOGY_SNAPSHOT_VERSION,
    PeerState,
    TopologyStateMachine,
)

pytestmark = [
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Fixture: minimal opts + SM
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
# PeerState shape
# ---------------------------------------------------------------------------


def test_peer_state_fields():
    """PeerState exposes exactly the four documented fields in order."""
    assert PeerState._fields == (
        "cluster_id",
        "public_key",
        "endpoints",
        "attached_at",
    )
    # No ``last_summary`` --- summaries must stay out of snapshotted state.
    assert "last_summary" not in PeerState._fields
    assert "routes" not in PeerState._fields


def test_peer_state_is_tuple_subclass():
    """PeerState is a NamedTuple (immutable, tuple subclass)."""
    inst = PeerState(
        cluster_id="east",
        public_key=b"PEM",
        endpoints=("127.0.0.1:4506",),
        attached_at=1_700_000_000.0,
    )
    assert isinstance(inst, tuple)
    # Positional unpack works.
    cid, pub, eps, at = inst
    assert cid == "east"
    assert pub == b"PEM"
    assert eps == ("127.0.0.1:4506",)
    assert at == 1_700_000_000.0


def test_peer_state_immutable():
    """Field assignment on a NamedTuple instance must raise."""
    inst = PeerState(
        cluster_id="east",
        public_key=b"PEM",
        endpoints=(),
        attached_at=0.0,
    )
    with pytest.raises(AttributeError):
        inst.cluster_id = "west"


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


def test_dispatch_table_maps_identity_entry(sm):
    """MASTER_IDENTITY_KEY dispatches to _handle_identity_key."""
    handler = sm._handlers[LogEntryType.MASTER_IDENTITY_KEY]
    assert handler == sm._handle_identity_key


def test_dispatch_table_maps_peer_attach(sm):
    """MASTER_PEER_ATTACH dispatches to _handle_peer_attach."""
    assert sm._handlers[LogEntryType.MASTER_PEER_ATTACH] == sm._handle_peer_attach


def test_dispatch_table_maps_peer_detach(sm):
    """MASTER_PEER_DETACH dispatches to _handle_peer_detach."""
    assert sm._handlers[LogEntryType.MASTER_PEER_DETACH] == sm._handle_peer_detach


def test_dispatch_table_no_summary_handler(sm):
    """Summaries are soft state --- no SM handler should exist for them."""
    # The attribute itself may not exist on LogEntryType (we expressly
    # didn't add MASTER_PEER_SUMMARY), but if a future draft adds one
    # the dispatch table must still not route to a Raft handler.
    assert not hasattr(LogEntryType, "MASTER_PEER_SUMMARY")


def test_dispatch_table_no_route_handler(sm):
    """Routes are derived locally --- no SM handler should exist for them."""
    assert not hasattr(LogEntryType, "MASTER_PEER_ROUTE")


def test_dispatch_table_handler_count(sm):
    """Only three master-topology entry types are routed."""
    assert len(sm._handlers) == 3
    assert set(sm._handlers.keys()) == {
        LogEntryType.MASTER_IDENTITY_KEY,
        LogEntryType.MASTER_PEER_ATTACH,
        LogEntryType.MASTER_PEER_DETACH,
    }


def test_log_entry_type_values_distinct():
    """New MASTER_* ids don't collide with existing LogEntryType values."""
    existing = {
        LogEntryType.COMMAND,
        LogEntryType.CONFIG,
        LogEntryType.SNAPSHOT,
        LogEntryType.RING_CONFIG,
        LogEntryType.RING_REGISTRY,
        LogEntryType.ROUTE,
    }
    masters = {
        LogEntryType.MASTER_IDENTITY_KEY,
        LogEntryType.MASTER_PEER_ATTACH,
        LogEntryType.MASTER_PEER_DETACH,
    }
    assert not existing & masters, "MASTER_* values collide with pre-existing types"
    assert len(masters) == 3, "duplicate MASTER_* values"


# ---------------------------------------------------------------------------
# Snapshot schema version
# ---------------------------------------------------------------------------


def test_snapshot_envelope_version_present(sm):
    """Snapshot payload carries the current schema version prefix."""
    snap = sm.get_snapshot()
    assert isinstance(snap, (bytes, bytearray))
    payload = salt.utils.msgpack.unpackb(bytes(snap), raw=False)
    assert isinstance(payload, dict)
    assert payload.get("version") == TOPOLOGY_SNAPSHOT_VERSION


def test_snapshot_envelope_version_value_shape():
    """Schema version is a short dotted string identifier."""
    assert isinstance(TOPOLOGY_SNAPSHOT_VERSION, str)
    assert TOPOLOGY_SNAPSHOT_VERSION.startswith("topology.snapshot.")


def test_restore_snapshot_rejects_unknown_version(sm):
    """A snapshot with an unknown envelope version is a no-op (safe refuse)."""
    bogus = salt.utils.msgpack.packb(
        {
            "version": "topology.snapshot.v999",
            "identity_pub": b"EVIL",
            "identity_version": 1,
            "peers": {"east": {"cluster_id": "east", "public_key": b"EVIL"}},
        },
        use_bin_type=True,
    )
    # Pre-apply some real state so we can check the restore didn't
    # overwrite it with the bogus payload.
    sm.apply(
        {
            "type": LogEntryType.MASTER_IDENTITY_KEY,
            "public_key": b"-----BEGIN PUBLIC KEY-----\nREAL\n-----END PUBLIC KEY-----\n",
        }
    )
    sm.restore_snapshot(bogus)
    assert registry.get_peer(sm.registry, "east") is None
    assert registry.get_identity_pub(sm.registry) != b"EVIL"


def test_restore_snapshot_none_is_noop(sm):
    """``restore_snapshot(None)`` is a quiet no-op."""
    sm.restore_snapshot(None)  # must not raise


def test_restore_snapshot_bad_payload_is_noop(sm):
    """A malformed (non-msgpack) payload is a logged no-op, not a raise."""
    sm.restore_snapshot(b"not valid msgpack \xff\xfe\xfd")  # must not raise


# ---------------------------------------------------------------------------
# generate_identity_key
# ---------------------------------------------------------------------------


def test_generate_identity_key_returns_bytes(sm):
    """Return value is ``(pub_pem, priv_pem)`` as bytes."""
    pub, priv = sm.generate_identity_key()
    assert isinstance(pub, bytes)
    assert isinstance(priv, bytes)
    assert b"BEGIN PUBLIC KEY" in pub
    assert b"BEGIN" in priv and b"PRIVATE KEY" in priv


def test_generate_identity_key_parses_through_crypt(sm):
    """The pub half is a valid PEM RSA key parseable by salt.crypt.PublicKey."""
    pub, _priv = sm.generate_identity_key()
    key = salt.crypt.PublicKey.from_str(pub)
    assert key is not None


def test_generate_identity_key_pair_is_fresh(sm):
    """Two generations produce distinct keypairs."""
    pub_a, _ = sm.generate_identity_key()
    pub_b, _ = sm.generate_identity_key()
    assert pub_a != pub_b


def test_generate_identity_key_does_not_persist(sm, opts):
    """``generate_identity_key`` does not touch disk or MmapCache."""
    import os

    pub_before = registry.get_identity_pub(sm.registry)
    sm.generate_identity_key()
    pub_after = registry.get_identity_pub(sm.registry)
    assert pub_before == pub_after
    pub_path = os.path.join(opts["pki_dir"], "master", "master_identity.pub")
    assert not os.path.isfile(pub_path)
