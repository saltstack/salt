"""
Functional tests for :mod:`salt.topology.registry`.

Exercises the real :class:`salt.utils.mmap_cache.MmapCache` backing
store on disk --- no mocks.  The master harness in ``conftest.py``
is intentionally not used here: the registry API is tested in
isolation (real filesystem, real mmap, real fork) so a failure in
master startup never masks a registry regression.

Coverage
--------
* ``pre_create`` materializes the mmap files and is idempotent.
* Identity public key write/read round-trip (including None, then
  overwrite, then idempotent re-write).
* Peer set/get/delete round-trip with full PeerState shape.
* ``set_peer`` rejects reserved cluster_id names
  (``__identity_pub__`` and ``__identity_version__``).
* ``list_peer_ids`` returns the full attached-peer set and no
  reserved keys.
* Cross-process read: parent writes, child reads via
  ``open_reader`` and sees the write.
* Owner-PID guard: ``set_peer`` from a forked child raises.
* ``delete_peer`` on a never-attached id is a no-op.
* ``set_peer`` overwrites an existing entry.
"""

import multiprocessing
import os

import pytest

import salt.topology.registry as registry

pytestmark = [
    pytest.mark.skip_on_windows,  # fork(2) semantics required
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opts(pki_root):
    """
    Build the minimal opts dict the registry module reads.

    ``pki_dir`` is the parent of ``master/`` --- the cache files
    live at ``<pki_dir>/master/topology_registry.mmap*``.  Sizes
    are small to keep the on-disk footprint of the test
    manageable but large enough for every test's peer count.
    """
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
    }


def _peer_state(
    cluster_id, pubkey=b"-----BEGIN FAKE-----\n", endpoints=("127.0.0.1:4506",)
):
    """Return a PeerState-shaped dict for use with set_peer()."""
    return {
        "cluster_id": cluster_id,
        "public_key": pubkey,
        "endpoints": tuple(endpoints),
        "attached_at": 1_700_000_000.0,
    }


@pytest.fixture
def opts(tmp_path):
    return _opts(tmp_path)


@pytest.fixture
def writer(opts):
    """Pre-create then open a writer; close at end of test."""
    registry.pre_create(opts)
    cache = registry.open_writer(opts)
    try:
        yield cache
    finally:
        if hasattr(cache, "close"):
            try:
                cache.close()
            except Exception:  # pylint: disable=broad-except
                pass


# ---------------------------------------------------------------------------
# pre_create
# ---------------------------------------------------------------------------


def test_pre_create_materializes_files(opts):
    """``pre_create`` creates the mmap index + heap files on disk."""
    registry.pre_create(opts)
    master_dir = os.path.join(opts["pki_dir"], "master")
    index_path = os.path.join(master_dir, "topology_registry.mmap")
    heap_path = index_path + ".heap"
    assert os.path.isfile(index_path), "index file not created"
    assert os.path.isfile(heap_path), "heap file not created"


def test_pre_create_is_idempotent(opts):
    """Calling ``pre_create`` twice is a no-op --- files, size, contents unchanged."""
    registry.pre_create(opts)
    index_path = os.path.join(opts["pki_dir"], "master", "topology_registry.mmap")
    size_before = os.path.getsize(index_path)
    # Second call must not raise and must not truncate.
    registry.pre_create(opts)
    size_after = os.path.getsize(index_path)
    assert size_before == size_after


# ---------------------------------------------------------------------------
# Identity public key
# ---------------------------------------------------------------------------


def test_identity_pub_initially_none(writer):
    """Before any write, ``get_identity_pub`` returns None."""
    assert registry.get_identity_pub(writer) is None


def test_identity_pub_round_trip(writer):
    """Writing identity pub bytes makes them readable verbatim."""
    pem = b"-----BEGIN PUBLIC KEY-----\nABCDEF==\n-----END PUBLIC KEY-----\n"
    registry.set_identity_pub(writer, pem)
    assert registry.get_identity_pub(writer) == pem


def test_identity_pub_overwrite(writer):
    """A second ``set_identity_pub`` call replaces the stored bytes."""
    registry.set_identity_pub(writer, b"first")
    registry.set_identity_pub(writer, b"second")
    assert registry.get_identity_pub(writer) == b"second"


def test_identity_pub_idempotent_rewrite(writer):
    """Re-writing identical bytes must not raise and must preserve the value."""
    pem = b"same-bytes-every-time"
    registry.set_identity_pub(writer, pem)
    registry.set_identity_pub(writer, pem)
    assert registry.get_identity_pub(writer) == pem


# ---------------------------------------------------------------------------
# Peer round-trip
# ---------------------------------------------------------------------------


def test_peer_set_get_round_trip(writer):
    """``set_peer`` then ``get_peer`` returns the same dict shape and values."""
    state = _peer_state("east")
    registry.set_peer(writer, "east", state)
    got = registry.get_peer(writer, "east")
    assert got is not None
    assert got["cluster_id"] == "east"
    assert got["public_key"] == state["public_key"]
    assert tuple(got["endpoints"]) == state["endpoints"]
    assert got["attached_at"] == pytest.approx(state["attached_at"])


def test_get_peer_missing_returns_none(writer):
    """Unknown cluster_id returns None (not KeyError, not {})."""
    assert registry.get_peer(writer, "no-such-peer") is None


def test_peer_delete_round_trip(writer):
    """After ``delete_peer`` the peer is gone from ``get_peer`` and ``list_peer_ids``."""
    registry.set_peer(writer, "west", _peer_state("west"))
    assert registry.get_peer(writer, "west") is not None
    registry.delete_peer(writer, "west")
    assert registry.get_peer(writer, "west") is None
    assert "west" not in registry.list_peer_ids(writer)


def test_delete_peer_missing_is_idempotent(writer):
    """``delete_peer`` on an id that was never attached must not raise."""
    # Deliberately never set.
    registry.delete_peer(writer, "ghost")  # must be a quiet no-op


def test_set_peer_overwrites_existing(writer):
    """A second ``set_peer`` for the same id replaces the stored dict."""
    registry.set_peer(writer, "north", _peer_state("north", pubkey=b"KEY-A"))
    registry.set_peer(writer, "north", _peer_state("north", pubkey=b"KEY-B"))
    got = registry.get_peer(writer, "north")
    assert got["public_key"] == b"KEY-B"


# ---------------------------------------------------------------------------
# Reserved-key defense
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reserved",
    [
        registry.RESERVED_IDENTITY_PUB_KEY,
        registry.RESERVED_IDENTITY_VERSION_KEY,
    ],
)
def test_set_peer_rejects_reserved_cluster_id(writer, reserved):
    """``set_peer`` with a reserved cluster_id raises --- defense against hostile peers."""
    with pytest.raises((ValueError, RuntimeError)):
        registry.set_peer(writer, reserved, _peer_state(reserved))


# ---------------------------------------------------------------------------
# list_peer_ids
# ---------------------------------------------------------------------------


def test_list_peer_ids_empty(writer):
    """Fresh registry lists no peers."""
    assert registry.list_peer_ids(writer) == []


def test_list_peer_ids_returns_all_attached(writer):
    """``list_peer_ids`` enumerates every live peer, excluding reserved keys."""
    registry.set_identity_pub(writer, b"identity-bytes")
    for cid in ("alpha", "bravo", "charlie"):
        registry.set_peer(writer, cid, _peer_state(cid))
    ids = set(registry.list_peer_ids(writer))
    assert ids == {"alpha", "bravo", "charlie"}
    # Reserved keys must never surface as peer ids.
    assert registry.RESERVED_IDENTITY_PUB_KEY not in ids
    assert registry.RESERVED_IDENTITY_VERSION_KEY not in ids


def test_list_peer_ids_reflects_delete(writer):
    """After a delete the id is no longer listed."""
    for cid in ("alpha", "bravo"):
        registry.set_peer(writer, cid, _peer_state(cid))
    registry.delete_peer(writer, "alpha")
    assert registry.list_peer_ids(writer) == ["bravo"]


# ---------------------------------------------------------------------------
# Cross-process read via fork
# ---------------------------------------------------------------------------


def _reader_child(opts, cluster_id, result_queue):
    """Child process body: open reader, fetch the peer, enqueue result."""
    try:
        reader = registry.open_reader(opts)
        got = registry.get_peer(reader, cluster_id)
        pub = registry.get_identity_pub(reader)
        result_queue.put(("ok", got, pub, list(registry.list_peer_ids(reader))))
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(("err", repr(exc)))


def test_cross_process_read_via_fork(writer, opts):
    """A fork child opening ``open_reader`` sees peers written by the parent."""
    registry.set_identity_pub(writer, b"PARENT-IDENTITY-PEM")
    registry.set_peer(
        writer, "across-fork", _peer_state("across-fork", pubkey=b"CHILD-SEES-THIS")
    )

    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    proc = ctx.Process(target=_reader_child, args=(opts, "across-fork", q))
    proc.start()
    proc.join(timeout=30)
    assert proc.exitcode == 0, f"child exit {proc.exitcode}"
    status, *payload = q.get(timeout=5)
    assert status == "ok", f"child error: {payload}"
    got, pub, ids = payload
    assert got is not None, "child could not read peer"
    assert got["public_key"] == b"CHILD-SEES-THIS"
    assert pub == b"PARENT-IDENTITY-PEM"
    assert ids == ["across-fork"]


# ---------------------------------------------------------------------------
# Owner-PID guard
# ---------------------------------------------------------------------------


def _writer_child(opts, result_queue):
    """
    Child body: try to call ``set_peer`` using the parent-owned writer handle.

    The parent sends the writer handle via module-level globals that
    fork-copied into the child; the owner-PID guard captured at
    ``open_writer`` time must reject any write issued from a PID that
    isn't the one that opened the cache.
    """
    try:
        # Re-open: this fresh handle is owned by the child PID and must work.
        child_handle = registry.open_writer(opts)
        # The child's own handle is NOT what we want to test; discard.
        del child_handle
        # Rebuild the parent-owned handle by poking at module state the
        # test shares via the queue.  The simpler contract: calling
        # ``set_peer`` on a parent handle from a child PID must raise.
        parent_handle = _writer_child.parent_handle  # set below before fork
        registry.set_peer(parent_handle, "forbidden", _peer_state("forbidden"))
        result_queue.put(("no-raise",))
    except RuntimeError as exc:
        result_queue.put(("raised", repr(exc)))
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(("other", repr(exc)))


def test_owner_pid_guard_rejects_fork_write(writer, opts):
    """
    ``set_peer`` from a forked child using the parent's writer handle raises.

    The guard protects against MWorkers inheriting the publish
    daemon's writer handle via fork and performing silent writes.
    """
    # Stash the parent handle where the forked child body can see it.
    # multiprocessing-fork children inherit module globals, so this works.
    _writer_child.parent_handle = writer  # noqa: SLF001

    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    proc = ctx.Process(target=_writer_child, args=(opts, q))
    proc.start()
    proc.join(timeout=30)
    status, *detail = q.get(timeout=5)
    assert (
        status == "raised"
    ), f"owner-PID guard failed: status={status} detail={detail}"
