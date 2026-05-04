"""Tests for the Chaos Monkey fault injection."""

import time

from salt.cluster.consensus.raft import ManualPeer, ManualTimeoutScheduler, Node
from tests.support.raft_chaos import ChaosController, ChaosPeer


def _handle_all(nodes):
    """Process all pending requests for all nodes in the cluster."""
    any_handled = True
    while any_handled:
        any_handled = False
        for node in nodes:
            for peer in node.peers:
                if peer.requests:
                    peer.handle_all_requests()
                    any_handled = True


def test_chaos_controller_heal_all_and_drop_rate_zero():
    c = ChaosController()
    c.partition("x", "y")
    assert c.should_drop("x", "y") is True
    c.heal_all()
    assert c.should_drop("x", "y") is False
    c.drop_rate = 0.0
    assert c.get_latency() == 0


def test_chaos_partition():
    """Test that ChaosController correctly blocks communication between two nodes."""
    controller = ChaosController()
    node_a = Node("A")
    node_b = Node("B")

    real_peer_b = ManualPeer(node_b)
    chaos_peer_b = ChaosPeer(real_peer_b, controller, node_a.address)

    chaos_peer_b.request_vote(lambda addr, granted, term: None, "A", 1, 0, -1)
    assert len(real_peer_b.requests) == 1
    real_peer_b.drop_requests()

    controller.partition("A", "B")
    chaos_peer_b.request_vote(lambda addr, granted, term: None, "A", 1, 0, -1)
    assert len(real_peer_b.requests) == 0

    controller.heal("A", "B")
    chaos_peer_b.request_vote(lambda addr, granted, term: None, "A", 1, 0, -1)
    assert len(real_peer_b.requests) == 1


def test_chaos_drop_rate():
    """Verify that random packet drop rate is applied correctly."""
    controller = ChaosController()
    controller.drop_rate = 1.0  # Drop everything

    node_a = Node("A")
    node_b = Node("B")
    real_peer_b = ManualPeer(node_b)
    chaos_peer_b = ChaosPeer(real_peer_b, controller, node_a.address)

    chaos_peer_b.append_entries(lambda *args: None, "A", 1, 0, -1, 0)
    assert len(real_peer_b.requests) == 0


def test_chaos_latency():
    """Verify that injected latency delays the execution of RPCs."""
    controller = ChaosController()
    controller.latency_min = 100
    controller.latency_max = 100

    node_a = Node("A")
    node_b = Node("B")
    real_peer_b = ManualPeer(node_b)
    chaos_peer_b = ChaosPeer(real_peer_b, controller, node_a.address)

    start = time.time()
    chaos_peer_b.pre_request_vote(lambda *args: None, "A", 1, 0, -1)
    end = time.time()

    assert (end - start) >= 0.1


def test_chaos_cluster_partition():
    """Verify that a majority partition can elect a leader while isolated."""
    scheduler = ManualTimeoutScheduler()
    controller = ChaosController()

    nodes = [Node(str(i)) for i in range(1, 4)]
    for node in nodes:
        node.register_schedule_timeout(scheduler.schedule)
        node.peers = [
            ChaosPeer(ManualPeer(_), controller, node.address)
            for _ in nodes
            if _ != node
        ]
        node.become_follower()
        node.last_followed = node.get_now() - 10

    scheduler.process_existing_timeouts()
    _handle_all(nodes)  # pre-vote
    _handle_all(nodes)  # vote

    leaders = [n for n in nodes if n.state == n.state.LEADER]
    assert len(leaders) == 1
    leader = leaders[0]

    # Partition leader from others
    other_addrs = [n.address for n in nodes if n != leader]
    for other in other_addrs:
        controller.partition(leader.address, other)

    # Leader fails heartbeat
    leader.leader_beacon()
    for p in leader.peers:
        assert len(p.real_peer.requests) == 0

    # Others time out and elect new leader
    for n in nodes:
        if n != leader:
            n.last_followed = n.get_now() - 10
    scheduler.process_existing_timeouts()
    _handle_all(nodes)  # pre-vote
    _handle_all(nodes)  # vote

    new_leaders = [n for n in nodes if n.state == n.state.LEADER and n != leader]
    assert len(new_leaders) == 1
    assert new_leaders[0].term > leader.term


def test_chaos_partition_and_heal():
    """Verify that an isolated node catch up correctly after partition heals."""
    scheduler = ManualTimeoutScheduler()
    controller = ChaosController()

    nodes = [Node(str(i)) for i in range(1, 4)]
    for node in nodes:
        node.register_schedule_timeout(scheduler.schedule)
        node.peers = [
            ChaosPeer(ManualPeer(_), controller, node.address)
            for _ in nodes
            if _ != node
        ]
        node.become_follower()
        node.last_followed = node.get_now() - 10

    # Initial election
    scheduler.process_existing_timeouts()
    _handle_all(nodes)  # pre-vote
    _handle_all(nodes)  # vote
    assert nodes[0].state == nodes[0].state.LEADER

    # PARTITION
    controller.partition("1", "2")
    controller.partition("1", "3")

    # Nodes 2/3 elect new leader (node 2)
    nodes[1].last_followed = nodes[1].get_now() - 10
    nodes[2].last_followed = nodes[2].get_now() - 10
    scheduler.process_existing_timeouts()
    _handle_all(nodes)

    leaders = [n for n in nodes if n.state == n.state.LEADER]
    assert len(leaders) == 2  # 1 is still leader in its partition, 2/3 have a new one
    new_leader = [n for n in leaders if n.address != "1"][0]

    # Append data to new leader
    new_leader.log_add("replicated_data")
    _handle_all(nodes)

    # Verify node 1 DOES NOT have the data
    assert len(nodes[0].log.entries) == 0

    # HEAL
    controller.heal_all()

    # Force synchronization
    for p in new_leader.peers:
        new_leader.send_append_entries(p)
    _handle_all(nodes)

    # Verify node 1 caught up and stepped down
    assert len(nodes[0].log.entries) == 1
    assert nodes[0].log.entries[0].cmd == "replicated_data"
    assert nodes[0].state == nodes[0].state.FOLLOWER
    assert nodes[0].term == new_leader.term


def test_chaos_install_snapshot_wrapped():
    """ChaosPeer.install_snapshot delegates to real peer via _wrap_rpc."""
    from tests.support.mock import MagicMock
    from tests.support.raft_chaos import ChaosController, ChaosPeer

    real_peer = MagicMock()
    real_peer.node_id = "n2"
    real_peer.address = "n2"
    real_peer.voting = True
    real_peer.install_snapshot.return_value = None

    controller = ChaosController()
    chaos_peer = ChaosPeer(real_peer, controller, "n1")

    chaos_peer.install_snapshot(
        lambda nid, term: None,
        "leader",
        1,
        last_included_index=5,
        last_included_term=1,
        data=b"snap",
    )
    real_peer.install_snapshot.assert_called_once()
