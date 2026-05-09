"""
Unit tests for ``salt.cluster.ring_membership`` — the high-level
ownership query layer that wraps :class:`salt.cluster.ring.HashRing`
for the rest of the cluster code.

The :class:`HashRing` class itself is tested exhaustively in
``test_ring.py``; these tests pin the additional contract:

* the per-process singleton starts empty so ``owns`` returns ``True``
  (preserving today's broadcast behaviour in any subprocess that has
  not received a rebuild);
* :func:`rebuild` populates the ring; :func:`owns` then routes by the
  ring's consistent-hash answer;
* :func:`reset` returns the singleton to its empty state for tests.
"""

import pytest

from salt.cluster import ring_membership


@pytest.fixture(autouse=True)
def _isolate_ring():
    """Each test gets a fresh empty ring; cleanup leaves a fresh one too."""
    ring_membership.reset()
    yield
    ring_membership.reset()


def _opts(interface):
    return {"interface": interface}


# ---------------------------------------------------------------------------
# Default (empty ring) semantics — matches today's broadcast behaviour
# ---------------------------------------------------------------------------


def test_owns_returns_true_for_empty_ring():
    """
    Stage 0 invariant: with no rebuild having run, every master owns
    every key.  The gate sites in master.py rely on this so behaviour
    is unchanged from the pre-ring code path.
    """
    assert ring_membership.owns(_opts("master-1"), "jid-123") is True
    assert ring_membership.owns(_opts("master-1"), "minion-A") is True


def test_owns_true_when_interface_missing():
    """
    Defensive: opts dicts without an ``interface`` (some test fixtures)
    are treated as standalone — every key is owned locally.
    """
    assert ring_membership.owns({}, "jid-99") is True
    assert ring_membership.owns({"id": "host"}, "jid-99") is True


def test_get_ring_returns_singleton():
    """``get_ring`` exposes the same instance across calls."""
    a = ring_membership.get_ring()
    b = ring_membership.get_ring()
    assert a is b


# ---------------------------------------------------------------------------
# Populated ring — proves the gate sites will actually shard once ring
# mode is flipped on in stage 1
# ---------------------------------------------------------------------------


def test_rebuild_populates_ring_with_voters():
    """``rebuild`` is the hook RaftService._on_membership_change calls."""
    ring_membership.rebuild(["m1", "m2", "m3"])
    assert sorted(ring_membership.get_ring().nodes()) == ["m1", "m2", "m3"]


def test_owns_routes_by_consistent_hash_after_rebuild():
    """
    After rebuild, exactly one of the cluster members owns any given
    key.  The exact owner is consistent-hash determined; we don't pin
    a specific assignment but we do assert the constraint that exactly
    one master answers ``True`` for each key.
    """
    members = ["m1", "m2", "m3"]
    ring_membership.rebuild(members)
    for key in (
        "jid-20260508-A",
        "jid-20260508-B",
        "minion-foo",
        "minion-bar",
        b"binary-key-bytes",
    ):
        owners = [m for m in members if ring_membership.owns(_opts(m), key)]
        assert len(owners) == 1, (
            f"key {key!r}: expected exactly one owner among {members}, " f"got {owners}"
        )


def test_rebuild_replaces_previous_membership():
    """A second rebuild atomically swaps the ring contents."""
    ring_membership.rebuild(["m1", "m2", "m3"])
    ring_membership.rebuild(["m4", "m5"])
    assert sorted(ring_membership.get_ring().nodes()) == ["m4", "m5"]


def test_rebuild_to_empty_makes_everyone_an_owner_again():
    """An empty rebuild returns to the ``owns == True`` standalone state."""
    ring_membership.rebuild(["m1", "m2"])
    ring_membership.rebuild([])
    assert ring_membership.owns(_opts("anywhere"), "jid-99") is True


# ---------------------------------------------------------------------------
# reset() — test infrastructure contract
# ---------------------------------------------------------------------------


def test_reset_restores_empty_ring():
    ring_membership.rebuild(["m1", "m2"])
    assert ring_membership.get_ring().node_count() == 2
    ring_membership.reset()
    assert ring_membership.get_ring().node_count() == 0
    # And owns is back to broadcast.
    assert ring_membership.owns(_opts("anywhere"), "jid-1") is True


def test_reset_swaps_singleton_identity():
    """
    ``reset`` builds a fresh HashRing rather than mutating the existing
    one in place.  Tests that hold a reference to the pre-reset ring
    must see it unchanged; only the module's exported singleton flips.
    """
    pre = ring_membership.get_ring()
    ring_membership.rebuild(["m1", "m2"])
    ring_membership.reset()
    post = ring_membership.get_ring()
    assert pre is not post
    # The pre-reset reference still holds the populated ring; it's
    # detached from the module singleton.
    assert pre.node_count() == 2
