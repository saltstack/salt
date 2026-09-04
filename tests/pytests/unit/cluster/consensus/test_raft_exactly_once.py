"""Exactly-once client session shape on :class:`CounterStateMachine` (Raft P1+)."""

import pytest

from salt.cluster.consensus.raft import (
    CounterStateMachine,
    ManualTimeoutScheduler,
    Node,
    NodeState,
)


@pytest.fixture
def eo_node():
    sm = CounterStateMachine()
    scheduler = ManualTimeoutScheduler()
    node = Node(
        node_id="node1",
        address="127.0.0.1:1000",
        peers=[],
        state_machine=sm,
    )
    node.register_schedule_timeout(scheduler.schedule)
    node.become_follower()
    node.term = 1
    node.state = NodeState()
    node.state.become_follower()
    node.state.become_candidate()
    node.state.become_leader()
    node.leader = node.node_id
    return node, sm


def test_duplicate_commands(eo_node):
    """Duplicate client_id + sequence_num must not advance the counter twice."""
    node, sm = eo_node
    client_id = "client1"

    node.log_add(b"cmd1", client_id=client_id, sequence_num=1)
    assert node.log.index == 0

    node.commit_index = 0
    node.apply_entries()
    assert sm.count == 1
    assert sm.sessions[client_id] == 1

    node.log_add(b"cmd1-dup", client_id=client_id, sequence_num=1)
    assert node.log.index == 1

    node.commit_index = 1
    node.apply_entries()
    assert sm.count == 1

    node.log_add(b"cmd2", client_id=client_id, sequence_num=2)
    assert node.log.index == 2
    node.commit_index = 2
    node.apply_entries()
    assert sm.count == 2
    assert sm.sessions[client_id] == 2


def test_session_persistence_in_snapshot(eo_node):
    """Sessions survive snapshot round-trip on a fresh state machine."""
    node, sm = eo_node
    client_id = "client1"
    node.log_add(b"cmd1", client_id=client_id, sequence_num=1)
    node.commit_index = 0
    node.apply_entries()

    snapshot_data = sm.get_snapshot()
    new_sm = CounterStateMachine()
    new_sm.restore_snapshot(snapshot_data)

    assert new_sm.count == 1
    assert new_sm.sessions[client_id] == 1

    res = new_sm.apply(b"cmd1-dup", client_id=client_id, sequence_num=1)
    assert res == 1
    assert new_sm.count == 1
