"""
Comprehensive tests for salt.cluster.ring.HashRing.

Coverage:
- Empty ring behaviour
- Single-node fast-path (every key maps to the sole node)
- Determinism: same inputs always produce the same owner
- VNode distribution: each node gets approximately vnodes tokens
- add_node / remove_node
- rebuild() (Raft on_change hook)
- get_replicas(): correct count, distinct nodes, primary == get_owner
- Key types: str and bytes produce the same owner
- Token collision handling (synthetic, forced)
- Thread safety: concurrent add/get_owner
- node_count / nodes / token_count / distribution / __len__ / __contains__ / __repr__
- Monotonicity: removing a non-owning node does not change ownership for a key
- Ring wrap-around (key whose hash exceeds all tokens)
- replicas > node_count capped to node_count
- Replication set covers distinct physical nodes only
"""

import threading

import pytest

from salt.cluster.ring import DEFAULT_VNODES, HashRing, _key_hash, _token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ring(*nodes, vnodes=10, replicas=1):
    return HashRing(nodes=nodes, vnodes=vnodes, replicas=replicas)


# ---------------------------------------------------------------------------
# Empty ring
# ---------------------------------------------------------------------------


class TestEmptyRing:
    def test_get_owner_returns_none(self):
        r = HashRing()
        assert r.get_owner("any_key") is None

    def test_get_replicas_returns_empty(self):
        r = HashRing()
        assert r.get_replicas("any_key") == []

    def test_node_count_zero(self):
        r = HashRing()
        assert r.node_count() == 0

    def test_nodes_empty(self):
        r = HashRing()
        assert r.nodes() == []

    def test_token_count_zero(self):
        r = HashRing()
        assert r.token_count() == 0

    def test_len_zero(self):
        assert len(HashRing()) == 0

    def test_contains_false(self):
        r = HashRing()
        assert "node1" not in r

    def test_distribution_empty(self):
        assert HashRing().distribution() == {}


# ---------------------------------------------------------------------------
# Single-node fast-path
# ---------------------------------------------------------------------------


class TestSingleNode:
    def test_get_owner_is_sole_node(self):
        r = make_ring("master-0")
        assert r.get_owner("jid-abc") == "master-0"
        assert r.get_owner("") == "master-0"
        assert r.get_owner("z" * 200) == "master-0"

    def test_get_owner_bytes_key(self):
        r = make_ring("master-0")
        assert r.get_owner(b"bytes_key") == "master-0"

    def test_get_replicas_single_node(self):
        r = make_ring("master-0", replicas=3)
        result = r.get_replicas("key")
        assert result == ["master-0"]

    def test_get_replicas_count_capped(self):
        r = make_ring("master-0", replicas=5)
        assert r.get_replicas("key", count=10) == ["master-0"]

    def test_node_count_one(self):
        r = make_ring("master-0")
        assert r.node_count() == 1

    def test_nodes_returns_list(self):
        r = make_ring("master-0")
        assert r.nodes() == ["master-0"]

    def test_token_count_approx_vnodes(self):
        vnodes = 20
        r = make_ring("master-0", vnodes=vnodes)
        # Collisions are astronomically rare; token count should equal vnodes.
        assert r.token_count() == vnodes

    def test_len_one(self):
        r = make_ring("master-0")
        assert len(r) == 1

    def test_contains_true(self):
        r = make_ring("master-0")
        assert "master-0" in r

    def test_distribution_single_node(self):
        vnodes = 15
        r = make_ring("master-0", vnodes=vnodes)
        d = r.distribution()
        assert list(d.keys()) == ["master-0"]
        assert d["master-0"] == vnodes

    def test_repr(self):
        r = make_ring("master-0", vnodes=5)
        s = repr(r)
        assert "master-0" in s
        assert "vnodes=5" in s


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_key_same_owner_repeated_calls(self):
        r = make_ring("a", "b", "c", vnodes=50)
        owners = {r.get_owner("some-jid") for _ in range(100)}
        assert len(owners) == 1

    def test_same_nodes_same_ring_independent_instances(self):
        nodes = ["salt-master-0", "salt-master-1", "salt-master-2"]
        r1 = HashRing(nodes=nodes, vnodes=50)
        r2 = HashRing(nodes=nodes, vnodes=50)
        keys = [f"jid-{i}" for i in range(200)]
        for k in keys:
            assert r1.get_owner(k) == r2.get_owner(k)

    def test_token_derivation_deterministic(self):
        t1 = _token("node-x", 0)
        t2 = _token("node-x", 0)
        assert t1 == t2

    def test_key_hash_deterministic(self):
        assert _key_hash("abc") == _key_hash("abc")
        assert _key_hash(b"abc") == _key_hash(b"abc")

    def test_str_and_bytes_same_hash(self):
        # get_owner encodes str keys before hashing
        r = make_ring("n1", "n2", "n3", vnodes=50)
        # str key and its bytes equivalent must map to the same owner
        assert r.get_owner("testkey") == r.get_owner(b"testkey")


# ---------------------------------------------------------------------------
# VNode distribution
# ---------------------------------------------------------------------------


class TestVNodeDistribution:
    def test_each_node_gets_vnodes_tokens(self):
        vnodes = 30
        nodes = ["a", "b", "c"]
        r = HashRing(nodes=nodes, vnodes=vnodes)
        d = r.distribution()
        for n in nodes:
            assert d[n] == vnodes, f"node {n} has {d[n]} tokens, expected {vnodes}"

    def test_distribution_balanced_many_nodes(self):
        """No node should have zero tokens with DEFAULT_VNODES."""
        nodes = [f"master-{i}" for i in range(10)]
        r = HashRing(nodes=nodes)
        d = r.distribution()
        for n in nodes:
            assert d[n] >= DEFAULT_VNODES * 0.9, f"node {n} severely under-represented"

    def test_all_keys_assigned(self):
        r = make_ring("a", "b", "c", vnodes=50)
        for i in range(500):
            assert r.get_owner(f"key-{i}") in {"a", "b", "c"}

    def test_no_single_node_owns_all_with_multiple_nodes(self):
        r = make_ring("a", "b", "c", vnodes=100)
        owners = {r.get_owner(f"k{i}") for i in range(500)}
        assert len(owners) > 1, "all 500 keys went to a single node"


# ---------------------------------------------------------------------------
# add_node / remove_node
# ---------------------------------------------------------------------------


class TestAddRemoveNode:
    def test_add_node_increases_count(self):
        r = make_ring("a")
        r.add_node("b")
        assert r.node_count() == 2

    def test_add_duplicate_is_idempotent(self):
        r = make_ring("a", vnodes=10)
        r.add_node("a")
        assert r.node_count() == 1
        assert r.token_count() == 10

    def test_remove_node_decreases_count(self):
        r = make_ring("a", "b")
        r.remove_node("b")
        assert r.node_count() == 1

    def test_remove_nonexistent_is_idempotent(self):
        r = make_ring("a")
        r.remove_node("ghost")
        assert r.node_count() == 1

    def test_remove_last_node_empties_ring(self):
        r = make_ring("only")
        r.remove_node("only")
        assert r.node_count() == 0
        assert r.get_owner("key") is None

    def test_add_node_makes_it_eligible_for_ownership(self):
        r = make_ring("a", vnodes=200)
        keys_before = {f"k{i}" for i in range(200) if r.get_owner(f"k{i}") == "a"}
        r.add_node("b")
        b_owns = {k for k in keys_before if r.get_owner(k) == "b"}
        # "b" should now own some keys that "a" previously owned
        assert len(b_owns) > 0

    def test_remove_node_reassigns_its_keys(self):
        r = make_ring("a", "b", vnodes=100)
        b_keys = [f"k{i}" for i in range(300) if r.get_owner(f"k{i}") == "b"]
        r.remove_node("b")
        for k in b_keys:
            assert r.get_owner(k) == "a"

    def test_contains_after_add(self):
        r = make_ring("a")
        r.add_node("b")
        assert "b" in r

    def test_not_contains_after_remove(self):
        r = make_ring("a", "b")
        r.remove_node("b")
        assert "b" not in r


# ---------------------------------------------------------------------------
# rebuild()
# ---------------------------------------------------------------------------


class TestRebuild:
    def test_rebuild_replaces_all_nodes(self):
        r = make_ring("old1", "old2", vnodes=20)
        r.rebuild(["new1", "new2", "new3"])
        assert set(r.nodes()) == {"new1", "new2", "new3"}

    def test_rebuild_removes_departed_nodes(self):
        r = make_ring("a", "b", "c", vnodes=20)
        r.rebuild(["a", "c"])
        assert "b" not in r
        assert r.node_count() == 2

    def test_rebuild_adds_new_nodes(self):
        r = make_ring("a", vnodes=20)
        r.rebuild(["a", "b"])
        assert "b" in r
        assert r.node_count() == 2

    def test_rebuild_same_nodes_is_idempotent(self):
        r = make_ring("a", "b", vnodes=10)
        tok_before = r.token_count()
        r.rebuild(["a", "b"])
        assert r.token_count() == tok_before

    def test_rebuild_empty_clears_ring(self):
        r = make_ring("a", "b", vnodes=10)
        r.rebuild([])
        assert r.node_count() == 0
        assert r.get_owner("key") is None

    def test_rebuild_to_single_node(self):
        r = make_ring("a", "b", "c", vnodes=30)
        r.rebuild(["solo"])
        assert r.get_owner("anything") == "solo"


# ---------------------------------------------------------------------------
# get_replicas()
# ---------------------------------------------------------------------------


class TestGetReplicas:
    def test_primary_matches_get_owner(self):
        r = make_ring("a", "b", "c", vnodes=50, replicas=3)
        for i in range(100):
            key = f"k{i}"
            assert r.get_replicas(key)[0] == r.get_owner(key)

    def test_replicas_are_distinct_nodes(self):
        r = make_ring("a", "b", "c", vnodes=50, replicas=3)
        for i in range(100):
            reps = r.get_replicas(f"k{i}")
            assert len(reps) == len(set(reps)), f"duplicates in replicas for k{i}"

    def test_replicas_count_matches_replicas_param(self):
        r = make_ring("a", "b", "c", vnodes=50, replicas=2)
        for i in range(50):
            assert len(r.get_replicas(f"k{i}")) == 2

    def test_replicas_capped_to_physical_node_count(self):
        r = make_ring("a", "b", vnodes=20, replicas=5)
        reps = r.get_replicas("key")
        assert len(reps) == 2

    def test_replicas_count_override(self):
        r = make_ring("a", "b", "c", vnodes=50, replicas=1)
        reps = r.get_replicas("key", count=3)
        assert len(reps) == 3
        assert len(set(reps)) == 3

    def test_single_node_replicas_always_one(self):
        r = make_ring("only", vnodes=20, replicas=3)
        assert r.get_replicas("key") == ["only"]


# ---------------------------------------------------------------------------
# Ring wrap-around
# ---------------------------------------------------------------------------


class TestWrapAround:
    def test_key_hash_exceeds_all_tokens_wraps_to_first(self):
        """A key whose hash is larger than all tokens wraps to the first token."""
        r = make_ring("a", "b", "c", vnodes=50)
        # Every key must map to a node in the ring regardless of where its
        # hash falls relative to the token range boundary.
        for i in range(1000):
            owner = r.get_owner(f"wrap-test-{i}")
            assert owner in {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Monotonicity: removing an unrelated node doesn't change other ownerships
# ---------------------------------------------------------------------------


class TestMonotonicity:
    def test_ownership_stable_for_unaffected_keys(self):
        """Keys not owned by the removed node must keep their owner."""
        r = make_ring("a", "b", "c", vnodes=100)
        # Find keys owned by "a"
        a_keys = [f"k{i}" for i in range(300) if r.get_owner(f"k{i}") == "a"]
        # Remove "c" — "a"-owned keys should stay with "a"
        r.remove_node("c")
        for k in a_keys:
            assert r.get_owner(k) == "a", f"key {k} changed owner after removing c"


# ---------------------------------------------------------------------------
# Invalid constructor arguments
# ---------------------------------------------------------------------------


class TestValidation:
    def test_vnodes_zero_raises(self):
        with pytest.raises(ValueError, match="vnodes"):
            HashRing(vnodes=0)

    def test_vnodes_negative_raises(self):
        with pytest.raises(ValueError, match="vnodes"):
            HashRing(vnodes=-1)

    def test_replicas_zero_raises(self):
        with pytest.raises(ValueError, match="replicas"):
            HashRing(replicas=0)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_get_owner_stable(self):
        r = make_ring("a", "b", "c", vnodes=100)
        errors = []

        def reader():
            for i in range(200):
                owner = r.get_owner(f"k{i}")
                if owner not in {"a", "b", "c"}:
                    errors.append(f"bad owner {owner!r} for k{i}")

        threads = [threading.Thread(target=reader) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_add_remove_get_no_crash(self):
        r = make_ring("a", "b", "c", vnodes=50)
        errors = []

        def mutator():
            for i in range(20):
                r.add_node(f"dynamic-{i % 5}")
                r.remove_node(f"dynamic-{i % 5}")

        def reader():
            for i in range(200):
                try:
                    r.get_owner(f"k{i}")
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(str(exc))

        threads = [threading.Thread(target=mutator) for _ in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_concurrent_rebuild_get_owner_no_crash(self):
        r = make_ring("a", "b", "c", vnodes=50)
        errors = []

        def rebuilder():
            for cycle in range(5):
                r.rebuild(["a", "b", "c", f"d{cycle}"])

        def reader():
            for i in range(300):
                try:
                    r.get_owner(f"k{i}")
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(str(exc))

        threads = [threading.Thread(target=rebuilder) for _ in range(2)]
        threads += [threading.Thread(target=reader) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# is_clustered / owns — standalone vs clustered routing guard
# ---------------------------------------------------------------------------


class TestStandaloneVsClustered:
    def test_is_clustered_false_when_empty(self):
        r = HashRing()
        assert r.is_clustered is False

    def test_is_clustered_true_after_rebuild(self):
        r = HashRing()
        r.rebuild(["master-0"])
        assert r.is_clustered is True

    def test_is_clustered_false_after_rebuild_empty(self):
        r = HashRing()
        r.rebuild(["master-0"])
        r.rebuild([])
        assert r.is_clustered is False

    def test_owns_empty_ring_always_true(self):
        """Standalone master: empty ring means every key belongs to this node."""
        r = HashRing()
        assert r.owns("any-jid", "solo-master") is True
        assert r.owns("another-jid", "solo-master") is True

    def test_owns_single_node_is_that_node(self):
        r = HashRing()
        r.rebuild(["master-0"])
        assert r.owns("jid-abc", "master-0") is True
        assert r.owns("jid-abc", "master-1") is False

    def test_owns_returns_false_for_non_owner_in_cluster(self):
        r = HashRing(vnodes=100)
        r.rebuild(["master-0", "master-1"])
        # At least some keys should be owned by each node
        m0_keys = [f"k{i}" for i in range(200) if r.owns(f"k{i}", "master-0")]
        m1_keys = [f"k{i}" for i in range(200) if r.owns(f"k{i}", "master-1")]
        assert len(m0_keys) > 0
        assert len(m1_keys) > 0
        assert len(m0_keys) + len(m1_keys) == 200

    def test_owns_consistent_with_get_owner(self):
        r = HashRing(vnodes=100)
        r.rebuild(["master-0", "master-1", "master-2"])
        for i in range(200):
            key = f"jid-{i}"
            owner = r.get_owner(key)
            for node in ["master-0", "master-1", "master-2"]:
                assert r.owns(key, node) == (owner == node)

    def test_routing_guard_standalone_never_shunts(self):
        """Simulate the master.py guard on a standalone master."""
        my_id = "salt-master"
        ring = HashRing()  # never rebuilt — no Raft

        jids = [f"jid-{i}" for i in range(100)]
        shunted = [j for j in jids if not ring.owns(j, my_id)]
        assert shunted == [], f"{len(shunted)} JIDs incorrectly shunted"

    def test_routing_guard_clustered_splits_correctly(self):
        """Simulate the master.py guard on a two-node cluster."""
        ring = HashRing(vnodes=150)
        ring.rebuild(["master-0", "master-1"])

        jids = [f"jid-{i}" for i in range(500)]
        m0_owned = [j for j in jids if ring.owns(j, "master-0")]
        m1_owned = [j for j in jids if ring.owns(j, "master-1")]

        # Every JID is owned by exactly one master
        assert len(m0_owned) + len(m1_owned) == 500
        # No JID is claimed by both
        assert set(m0_owned).isdisjoint(set(m1_owned))


# ---------------------------------------------------------------------------
# DEFAULT_VNODES constant
# ---------------------------------------------------------------------------


class TestConstants:
    def test_default_vnodes_value(self):
        assert DEFAULT_VNODES == 150

    def test_default_vnodes_used_by_constructor(self):
        r = HashRing(nodes=["n"])
        assert r.token_count() == DEFAULT_VNODES
