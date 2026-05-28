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


# ---------------------------------------------------------------------------
# Multi-ring registry: named rings stay isolated from each other
# ---------------------------------------------------------------------------


class TestMultiRingRegistry:
    """
    Pin the multi-ring contract: rings are keyed by name, isolated
    from each other; the routing snapshot decides which ring (if any)
    a given data type is bound to.
    """

    def test_get_ring_creates_named_rings_lazily(self):
        jobs = ring_membership.get_ring("jobs")
        events = ring_membership.get_ring("events")
        # Distinct rings, both initially empty.
        assert jobs is not events
        assert jobs.node_count() == 0
        assert events.node_count() == 0

    def test_rebuild_named_ring_does_not_perturb_others(self):
        """
        Rebuilding ring "jobs" must not touch ring "events".  Each
        ring is its own consensus group; sharing state would be a
        correctness bug.
        """
        ring_membership.rebuild("jobs", ["m1", "m2", "m3"])
        ring_membership.rebuild("events", ["m4", "m5"])
        assert sorted(ring_membership.get_ring("jobs").nodes()) == [
            "m1",
            "m2",
            "m3",
        ]
        assert sorted(ring_membership.get_ring("events").nodes()) == ["m4", "m5"]

    def test_default_ring_name_is_cluster(self):
        """
        ``get_ring()`` without a name returns the "cluster" ring so
        pre-multi-ring callers keep working.  Equivalently,
        ``rebuild(voters)`` (legacy single-arg) keeps populating that
        same ring.
        """
        ring_membership.rebuild(["m1", "m2"])
        assert ring_membership.get_ring() is ring_membership.get_ring("cluster")
        assert sorted(ring_membership.get_ring("cluster").nodes()) == ["m1", "m2"]

    def test_owns_takes_ring_name(self):
        ring_membership.rebuild("jobs", ["m1", "m2", "m3"])
        owners = [
            m
            for m in ("m1", "m2", "m3")
            if ring_membership.owns(_opts(m), "jid-X", ring="jobs")
        ]
        assert len(owners) == 1

    def test_drop_ring_makes_subsequent_lookups_empty(self):
        """
        After ``drop_ring``, the registry creates a fresh empty ring
        on the next ``get_ring`` call so this master is treated as a
        non-member of the destroyed ring.
        """
        ring_membership.rebuild("jobs", ["m1", "m2"])
        ring_membership.drop_ring("jobs")
        # A subsequent get_ring call lazily creates a new empty
        # HashRing under "jobs" again.
        assert ring_membership.get_ring("jobs").node_count() == 0


# ---------------------------------------------------------------------------
# Routing + owns_for: the multi-ring gate
# ---------------------------------------------------------------------------


class TestOwnsFor:
    """
    Pin the contract of :func:`ring_membership.owns_for`: it consults
    the routing snapshot, then defers to the named ring (or broadcasts
    if no route exists).  This is what the gate sites in
    :mod:`salt.master` will call.
    """

    def test_unrouted_data_type_broadcasts(self):
        """
        With no routing entry, every master owns every key for that
        data type — the broadcast behaviour that pre-multi-ring code
        relied on.
        """
        assert ring_membership.owns_for(_opts("m1"), "jobs", "jid-1") is True

    def test_route_cleared_to_none_broadcasts(self):
        """
        An explicit ``set_route(data_type, None)`` is equivalent to
        clearing the route — the data type returns to broadcast.
        """
        ring_membership.set_route("jobs", "jobs_ring")
        ring_membership.set_route("jobs", None)
        assert ring_membership.owns_for(_opts("m1"), "jobs", "jid-1") is True

    def test_routed_to_unknown_ring_returns_false(self):
        """
        A data type routed to a ring this master does not host
        locally (no Node, ring not in the registry, or empty ring)
        is a non-owner — the master no-ops writes for routed data
        it doesn't own.
        """
        ring_membership.set_route("jobs", "jobs_ring")
        # No master ever rebuilt "jobs_ring" — empty / unknown.
        assert ring_membership.owns_for(_opts("m1"), "jobs", "jid-1") is False

    def test_routed_to_known_ring_defers_to_ring_owns(self):
        """
        With a routed ring populated, ``owns_for`` answers whatever
        the ring's consistent-hash thinks.  Exactly one member of
        the ring's voter set wins for any given key.
        """
        ring_membership.rebuild("jobs_ring", ["m1", "m2", "m3"])
        ring_membership.set_route("jobs", "jobs_ring")
        owners = [
            m
            for m in ("m1", "m2", "m3")
            if ring_membership.owns_for(_opts(m), "jobs", "jid-1")
        ]
        assert len(owners) == 1

    def test_routes_are_returned_as_a_copy(self):
        ring_membership.set_route("jobs", "jobs_ring")
        snap = ring_membership.get_routes()
        # Mutating the returned copy must not bleed into the
        # registry's snapshot.
        snap["jobs"] = "different"
        assert ring_membership.get_routes() == {"jobs": "jobs_ring"}


# ---------------------------------------------------------------------------
# Drop accounting — surfaces silent non-member drops to operators
# ---------------------------------------------------------------------------


class TestDropStats:
    """
    Pin the contract that :func:`ring_membership.owns_for` records
    why it answered ``False`` so an operator can spot a misconfigured
    load balancer (traffic for a routed data type landing on
    masters that aren't in the ring).
    """

    def test_no_drops_when_no_route(self):
        # Broadcast (no route) writes never drop.
        assert ring_membership.owns_for(_opts("m1"), "jobs", "k1") is True
        assert ring_membership.drop_stats() == {}

    def test_not_a_member_bucket_counts_drops(self):
        """
        Route exists, ring unknown to this master → ``not_a_member``
        bucket counts every drop.  This is the misconfig signal.
        """
        ring_membership.set_route("jobs", "jobs_ring")
        for _ in range(3):
            assert ring_membership.owns_for(_opts("m1"), "jobs", "k") is False
        stats = ring_membership.drop_stats()
        assert stats["jobs"]["ring_id"] == "jobs_ring"
        assert stats["jobs"]["not_a_member"] == 3
        assert stats["jobs"]["other_ring_member"] == 0

    def test_other_ring_member_bucket_counts_sharded_misses(self):
        """
        With a populated ring, keys owned by sibling voters get
        counted under ``other_ring_member`` — that's the expected
        sharded-traffic shape, not a misconfig.  Pin it so an
        operator inspecting drop_stats knows which bucket is signal.
        """
        ring_membership.rebuild("jobs_ring", ["m1", "m2", "m3"])
        ring_membership.set_route("jobs", "jobs_ring")
        # Burn through 30 keys; some will hash to m1 (returns True),
        # the rest to siblings (False with reason "other_ring_member").
        seen_owned = seen_other = 0
        for i in range(30):
            if ring_membership.owns_for(_opts("m1"), "jobs", f"k-{i}"):
                seen_owned += 1
            else:
                seen_other += 1
        assert seen_owned and seen_other  # sanity: hash distributes
        stats = ring_membership.drop_stats()
        assert stats["jobs"]["other_ring_member"] == seen_other
        assert stats["jobs"]["not_a_member"] == 0

    def test_reset_clears_drop_stats(self):
        ring_membership.set_route("jobs", "jobs_ring")
        ring_membership.owns_for(_opts("m1"), "jobs", "k")
        assert ring_membership.drop_stats()
        ring_membership.reset()
        assert ring_membership.drop_stats() == {}


# ---------------------------------------------------------------------------
# Optional xxhash: master must still start when the package is missing
# ---------------------------------------------------------------------------


def test_ring_module_imports_without_xxhash(monkeypatch):
    """
    Windows NSIS upgrades from 3007.14 don't carry xxhash forward.
    ``salt.master`` always imports ``salt.cluster.ring_membership``
    which imports ``salt.cluster.ring``; if that import fails the
    master can't start at all.

    Pin the contract: with xxhash absent, the empty/self-only ring's
    ``owns()`` still returns True without hashing, and any operation
    that needs xxhash raises a clear ``RuntimeError`` pointing at the
    missing dependency.

    Implementation note: we don't actually re-import the modules
    under an import blocker -- that path would leak ``_xxhash = None``
    into the live module's namespace, and the ``HashRing`` class's
    ``__globals__`` still points at that namespace for the lifetime
    of the test process.  Subsequent tests in the same suite would
    then trip the RuntimeError.  Instead, ``monkeypatch.setattr``
    swaps the module's ``_xxhash`` attribute to ``None`` for the
    test's lifetime; pytest restores the original on teardown.
    """
    from salt.cluster import ring as ring_mod

    monkeypatch.setattr(ring_mod, "_xxhash", None)

    # Empty ring works without xxhash.
    ring = ring_mod.HashRing()
    assert ring.owns("anything", "me") is True
    assert ring.node_count() == 0

    # add_node / rebuild / get_owner raise a clear message.
    with pytest.raises(RuntimeError, match="xxhash"):
        ring.add_node("m1")
    with pytest.raises(RuntimeError, match="xxhash"):
        ring.rebuild(["m1", "m2"])
    with pytest.raises(RuntimeError, match="xxhash"):
        ring_mod._key_hash("anything")
    with pytest.raises(RuntimeError, match="xxhash"):
        ring_mod._token("m1", 0)
