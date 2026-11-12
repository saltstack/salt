"""
Unit tests for :mod:`salt.topology.registry`.

Focuses on invariants that do NOT require a running master or
multiple processes: PeerState dict shape round-trip, reserved-key
completeness, and the owner-PID guard behavior under threads
(share PID --- must be allowed) versus forks (differ PID ---
rejected).

The fork-based rejection is also covered by the functional
suite; this file asserts the thread-safe branch which the
functional file cannot cover without a fork.
"""

import multiprocessing
import os
import threading

import pytest

import salt.topology.registry as registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opts(pki_root):
    (pki_root / "master").mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
    }


def _peer_state(cluster_id):
    return {
        "cluster_id": cluster_id,
        "public_key": b"-----BEGIN FAKE-----\n",
        "endpoints": ("127.0.0.1:4506",),
        "attached_at": 1_700_000_000.0,
    }


@pytest.fixture
def opts(tmp_path):
    return _opts(tmp_path)


@pytest.fixture
def writer(opts):
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
# PeerState shape (named-keys dict, not positional tuple)
# ---------------------------------------------------------------------------


def test_peer_state_shape_named_keys(writer):
    """
    ``get_peer`` returns a dict with named keys matching PeerState
    fields --- cluster_id, public_key, endpoints, attached_at ---
    not a positional sequence.  The named-dict shape is the
    contract so this module does not have to import the Raft
    state machine for reader processes.
    """
    state = _peer_state("east")
    registry.set_peer(writer, "east", state)
    got = registry.get_peer(writer, "east")
    assert isinstance(got, dict), f"get_peer returned {type(got)!r}, want dict"
    assert set(got) >= {"cluster_id", "public_key", "endpoints", "attached_at"}
    # Positional access must not work (dict, not tuple).
    with pytest.raises((KeyError, TypeError)):
        _ = got[0]  # type: ignore[index]


def test_peer_state_preserves_bytes_vs_str(writer):
    """``public_key`` round-trips as bytes --- not str, not decoded utf-8."""
    pub = b"\x00\x01\x02binary-pem"
    state = _peer_state("east")
    state["public_key"] = pub
    registry.set_peer(writer, "east", state)
    got = registry.get_peer(writer, "east")
    assert isinstance(got["public_key"], (bytes, bytearray))
    assert bytes(got["public_key"]) == pub


def test_peer_state_endpoints_tuple(writer):
    """``endpoints`` round-trips as a sequence of strings."""
    state = _peer_state("east")
    state["endpoints"] = ("10.0.0.1:4506", "10.0.0.2:4506")
    registry.set_peer(writer, "east", state)
    got = registry.get_peer(writer, "east")
    endpoints = tuple(got["endpoints"])
    assert endpoints == ("10.0.0.1:4506", "10.0.0.2:4506")


# ---------------------------------------------------------------------------
# Reserved key list completeness
# ---------------------------------------------------------------------------


def test_reserved_key_names_exact():
    """The two reserved sentinels have the exact string values the Raft side expects."""
    assert registry.RESERVED_IDENTITY_PUB_KEY == "__identity_pub__"
    assert registry.RESERVED_IDENTITY_VERSION_KEY == "__identity_version__"


def test_reserved_keys_use_double_underscore_prefix():
    """
    Reserved keys use ``__`` prefix+suffix so they cannot collide
    with any valid cluster_id, which must match
    ``[a-z0-9][a-z0-9_-]*`` --- never starts with an underscore.
    """
    for key in (
        registry.RESERVED_IDENTITY_PUB_KEY,
        registry.RESERVED_IDENTITY_VERSION_KEY,
    ):
        assert key.startswith("__") and key.endswith("__"), key


@pytest.mark.parametrize(
    "reserved",
    [
        registry.RESERVED_IDENTITY_PUB_KEY,
        registry.RESERVED_IDENTITY_VERSION_KEY,
    ],
)
def test_set_peer_refuses_each_reserved_key(writer, reserved):
    """Every reserved key is rejected by ``set_peer``."""
    with pytest.raises((ValueError, RuntimeError)):
        registry.set_peer(writer, reserved, _peer_state(reserved))


# ---------------------------------------------------------------------------
# Owner-PID guard: threads share PID (allowed) vs forks differ (rejected)
# ---------------------------------------------------------------------------


def test_owner_pid_guard_allows_same_pid_thread(writer):
    """
    A worker thread shares the opener's PID so ``set_peer`` must succeed.

    The guard protects against **fork**, not **thread**: the publish
    daemon's own thread pool must be able to issue writes.
    """
    errors = []

    def _worker():
        try:
            registry.set_peer(writer, "from-thread", _peer_state("from-thread"))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(exc)

    t = threading.Thread(target=_worker)
    t.start()
    t.join(timeout=10)
    assert not errors, f"thread write failed: {errors}"
    assert registry.get_peer(writer, "from-thread") is not None


def _child_body(opts, writer_pid, result_queue):
    """
    Fork child body for owner-PID guard: open a writer in the parent,
    pass its PID through, then confirm from the child that the guard
    rejects write attempts.

    The child cannot inherit the parent's live handle via Queue
    (not picklable), so we re-create a handle locally with the
    *parent's* PID forced via ``_owner_pid`` to simulate what
    happens when fork duplicates the module global.
    """
    try:
        child_handle = registry.open_writer(opts)
        # Simulate fork-inherited handle: force _owner_pid to the
        # parent's PID.  The guard compares against os.getpid().
        child_handle._owner_pid = writer_pid  # noqa: SLF001
        try:
            registry.set_peer(child_handle, "forbidden", _peer_state("forbidden"))
        except RuntimeError:
            result_queue.put("rejected")
            return
        result_queue.put("not-rejected")
    except Exception as exc:  # pylint: disable=broad-except
        result_queue.put(f"error: {exc!r}")


@pytest.mark.skip_on_windows
def test_owner_pid_guard_rejects_different_pid(opts):
    """A write issued from a PID other than the opener's is rejected."""
    registry.pre_create(opts)
    writer = registry.open_writer(opts)
    try:
        ctx = multiprocessing.get_context("fork")
        q = ctx.Queue()
        proc = ctx.Process(target=_child_body, args=(opts, os.getpid(), q))
        proc.start()
        proc.join(timeout=15)
        result = q.get(timeout=5)
        assert result == "rejected", f"guard did not fire: {result}"
    finally:
        if hasattr(writer, "close"):
            try:
                writer.close()
            except Exception:  # pylint: disable=broad-except
                pass
