"""
Functional tests for salt.cluster.ring.HashRing.

These tests verify the full ring lifecycle as it will be used in production:
- Empty ring before any CONFIG entry
- Ring populated via rebuild() (the MembershipStateMachine.on_change hook)
- Single-node complete ownership
- Ownership stability when a node is added or removed
- Ring used as a routing gate (the Phase A master.py convergence point)
"""

import threading

from salt.cluster.ring import HashRing

# ---------------------------------------------------------------------------
# Lifecycle: empty → single node → multi-node
# ---------------------------------------------------------------------------


class TestRingLifecycle:
    def test_empty_ring_get_owner_returns_none(self):
        """Before CONFIG commit the ring must be empty and return None."""
        ring = HashRing()
        assert ring.get_owner("20240101120000000001") is None

    def test_empty_ring_get_replicas_returns_empty(self):
        ring = HashRing()
        assert ring.get_replicas("jid") == []

    def test_single_node_after_founding_config(self):
        """
        Simulate the founding CONFIG entry committed on the first heartbeat.
        The leader calls ring.rebuild([node_id]).
        """
        ring = HashRing()
        node_id = "10.0.0.1"

        # This is what MembershipStateMachine.on_change calls
        ring.rebuild([node_id])

        assert ring.node_count() == 1
        assert ring.get_owner("any-jid") == node_id

    def test_all_jids_map_to_sole_node(self):
        ring = HashRing()
        ring.rebuild(["salt-master-0"])

        jids = [f"2024010112000000000{i}" for i in range(100)]
        for jid in jids:
            assert ring.get_owner(jid) == "salt-master-0"

    def test_second_node_joins(self):
        """
        Simulate a second master joining: leader commits a new CONFIG entry
        with both nodes. ring.rebuild() is called with the updated voter set.
        """
        ring = HashRing()
        ring.rebuild(["master-0"])

        # All keys owned by master-0
        keys_before = {f"k{i}" for i in range(200)}
        assert all(ring.get_owner(k) == "master-0" for k in keys_before)

        # Second CONFIG entry: master-1 joins
        ring.rebuild(["master-0", "master-1"])

        assert ring.node_count() == 2
        owners = {ring.get_owner(k) for k in keys_before}
        assert "master-0" in owners
        assert "master-1" in owners

    def test_node_leaves_ownership_transferred(self):
        """
        Simulate a node leaving: leader commits CONFIG without it.
        Keys previously owned by the departed node transfer to the survivor.
        """
        ring = HashRing(vnodes=100)
        ring.rebuild(["master-0", "master-1"])

        m1_keys = [f"k{i}" for i in range(300) if ring.get_owner(f"k{i}") == "master-1"]

        ring.rebuild(["master-0"])

        for k in m1_keys:
            assert ring.get_owner(k) == "master-0"

    def test_rebuild_to_empty_all_keys_return_none(self):
        ring = HashRing()
        ring.rebuild(["master-0"])
        ring.rebuild([])
        assert ring.get_owner("any") is None


# ---------------------------------------------------------------------------
# Phase A convergence point simulation
# ---------------------------------------------------------------------------
# In master.py this becomes:
#   if ring.get_owner(load["jid"]) != self.opts["id"]:
#       # shunt to cluster bus
#       return


class TestRoutingGate:
    def test_single_node_owns_all_jids(self):
        my_id = "salt-master-0"
        ring = HashRing()
        ring.rebuild([my_id])

        jids = [f"2024010112000000000{i}" for i in range(50)]
        for jid in jids:
            assert ring.get_owner(jid) == my_id, f"jid {jid} not routed to self"

    def test_two_nodes_split_jids(self):
        """With two nodes each JID is owned by exactly one."""
        ring = HashRing(vnodes=150)
        ring.rebuild(["master-0", "master-1"])

        jids = [f"jid-{i:06d}" for i in range(1000)]
        m0 = [j for j in jids if ring.get_owner(j) == "master-0"]
        m1 = [j for j in jids if ring.get_owner(j) == "master-1"]

        assert len(m0) + len(m1) == 1000
        # With vnodes=150 the split should be roughly 50/50; allow wide margin
        assert len(m0) > 200
        assert len(m1) > 200

    def test_owner_is_deterministic_across_ring_instances(self):
        """Two ring instances built with the same nodes give the same owner."""
        nodes = ["master-0", "master-1", "master-2"]
        r1 = HashRing(nodes=nodes, vnodes=100)
        r2 = HashRing(nodes=nodes, vnodes=100)

        for i in range(200):
            jid = f"jid-{i}"
            assert r1.get_owner(jid) == r2.get_owner(jid)

    def test_routing_gate_before_config_commit_standalone(self):
        """
        A standalone master (no Raft, ring never rebuilt) must own all JIDs.
        ring.owns() returns True when the ring is empty.
        """
        my_id = "salt-master-0"
        ring = HashRing()

        jids = [f"2024010112000000000{i}" for i in range(20)]
        for jid in jids:
            assert ring.owns(jid, my_id), f"standalone master wrongly shunted {jid}"

    def test_routing_gate_clustered_before_config_commit(self):
        """
        A clustered master whose ring has not yet been populated (between
        process start and the first CONFIG commit) should not shunt — the
        is_clustered guard prevents premature shunting.
        """
        my_id = "salt-master-0"
        ring = HashRing()  # empty — CONFIG not yet committed

        jid = "20240101120000000001"
        # is_clustered is False → owns() returns True → no shunt
        assert not ring.is_clustered
        assert ring.owns(jid, my_id)


# ---------------------------------------------------------------------------
# Concurrent rebuild + routing (simulates Raft CONFIG commits while
# the master is actively routing job returns)
# ---------------------------------------------------------------------------


class TestConcurrentRebuildRouting:
    def test_routing_never_crashes_during_rebuild(self):
        """get_owner must not raise even when rebuild() runs concurrently."""
        ring = HashRing(vnodes=50)
        ring.rebuild(["master-0", "master-1"])

        errors = []

        def router():
            for i in range(500):
                try:
                    ring.get_owner(f"jid-{i}")
                except Exception as exc:  # pylint: disable=broad-except
                    errors.append(str(exc))

        def reconfigurator():
            configs = [
                ["master-0"],
                ["master-0", "master-1"],
                ["master-0", "master-1", "master-2"],
                ["master-0", "master-1"],
            ]
            for cfg in configs:
                ring.rebuild(cfg)

        threads = [threading.Thread(target=router) for _ in range(4)]
        threads.append(threading.Thread(target=reconfigurator))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_all_jids_always_have_an_owner_during_rebuild(self):
        """
        After any rebuild() with at least one node, no JID should return None.
        """
        ring = HashRing(vnodes=50)
        ring.rebuild(["master-0"])
        none_seen = []

        def router():
            for i in range(300):
                owner = ring.get_owner(f"jid-{i}")
                if owner is None:
                    none_seen.append(f"jid-{i}")

        def reconfigurator():
            for _ in range(10):
                ring.rebuild(["master-0", "master-1"])
                ring.rebuild(["master-0"])

        threads = [threading.Thread(target=router) for _ in range(4)]
        threads.append(threading.Thread(target=reconfigurator))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # None is acceptable only briefly between rebuild(["master-0"]) and
        # rebuild([...]) if the ring transitions through empty — but our
        # reconfigurator always keeps at least one node, so None should not occur.
        assert not none_seen, f"None owner seen for: {none_seen[:5]}"


# ---------------------------------------------------------------------------
# Replication set (N-replication foundation)
# ---------------------------------------------------------------------------


class TestReplicationSet:
    def test_single_node_replication_set(self):
        ring = HashRing(replicas=3)
        ring.rebuild(["master-0"])
        assert ring.get_replicas("key") == ["master-0"]

    def test_three_node_replication_set(self):
        ring = HashRing(vnodes=100, replicas=3)
        ring.rebuild(["master-0", "master-1", "master-2"])

        for i in range(100):
            reps = ring.get_replicas(f"jid-{i}")
            assert len(reps) == 3
            assert len(set(reps)) == 3  # all distinct
            assert reps[0] == ring.get_owner(f"jid-{i}")  # primary first

    def test_replication_set_capped_when_fewer_nodes(self):
        ring = HashRing(vnodes=50, replicas=3)
        ring.rebuild(["master-0", "master-1"])
        reps = ring.get_replicas("key")
        assert len(reps) == 2  # capped to available nodes
