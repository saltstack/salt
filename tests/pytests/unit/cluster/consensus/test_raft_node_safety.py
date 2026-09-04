"""Safety and edge-case tests for the Raft node to improve coverage."""

import json
import tempfile

import pytest

import salt.config
from salt.cluster.consensus.raft import (
    Candidacy,
    CandidacyError,
    LockingNode,
    ManualPeer,
    Node,
    NodeState,
    NoOpLock,
    NotLeader,
    Peer,
    Vote,
)
from salt.cluster.consensus.storage import SaltStorage


def _storage(path):
    """Return a SaltStorage backed by *path* as the cache directory."""
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = path
    return SaltStorage("test-node", opts)


def test_node_state_errors():
    state = NodeState()
    # become_candidate from START should fail
    with pytest.raises(RuntimeError, match="State must be follower first"):
        state.become_candidate()

    state.become_follower()
    state.become_candidate()
    # become_leader from CANDIDATE is OK, but let's test double become_candidate
    state.become_candidate()
    assert state == state.CANDIDATE


def test_candidacy_errors():
    c = Candidacy(1, ["peer1", "peer2"])
    # Reply from non-peer
    with pytest.raises(CandidacyError, match="is not a peer"):
        c.handle_reply("stranger", 1, True)

    # Reply with wrong term
    with pytest.raises(CandidacyError, match="Term 2 does not match ours 1"):
        c.handle_reply("peer1", 2, True)

    # Duplicate reply
    c.handle_reply("peer1", 1, True)
    with pytest.raises(CandidacyError, match="Already received a reply from this peer"):
        c.handle_reply("peer1", 1, True)


def test_noop_lock():
    lock = NoOpLock()
    lock.acquire()
    lock.release()
    with lock:
        pass


def test_node_repr_and_info():
    node = Node("address1")
    assert "address1" in repr(node)
    info = node.info()
    assert info["address"] == "address1"
    assert info["state"] == "start"


def test_on_config_change_no_factory():
    node = Node("1")
    # Should log warning and return
    node.on_config_change(["2"])
    assert len(node.peers) == 0


def test_node_become_follower_stale_term():
    node = Node("1")
    node.term = 10
    with pytest.raises(RuntimeError, match="Term lower than ours"):
        node.become_follower(term=5)


def test_request_votes_not_candidate():
    node = Node("1")
    with pytest.raises(RuntimeError, match="Not a candidate"):
        node.request_votes()


def test_request_vote_safety_checks():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()

    # Mock some log state via snapshot
    node.log.last_included_index = 10
    node.log.last_included_term = 2

    # Candidate with older term in snapshot
    granted, term, lc_addr = node.request_vote(
        "candidate", 3, last_term=1, last_index=10
    )
    assert not granted

    # Candidate with same term but older index than snapshot
    granted, term, lc_addr = node.request_vote(
        "candidate", 3, last_term=2, last_index=9
    )
    assert not granted


def test_request_vote_follower_logic():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.term = 1

    # Vote for someone
    node.request_vote("peer2", 1, last_term=0, last_index=-1)
    assert node.vote.node_id == "peer2"

    # Vote again for same person
    granted, term, lc_addr = node.request_vote("peer2", 1, last_term=0, last_index=-1)
    assert granted

    # Vote for someone else in same term
    granted, term, lc_addr = node.request_vote("peer3", 1, last_term=0, last_index=-1)
    assert not granted


def test_append_entries_stale_term():
    node = Node("1")
    node.term = 10
    success, term, _, _, lc_addr = node.append_entries("leader", 5, 0, -1, 0)
    assert not success
    assert term == 10


def test_prevote_phase():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    # 3 node cluster
    node.peers = [ManualPeer(Node("2")), ManualPeer(Node("3"))]
    node.become_follower()

    # Trigger pre-vote
    node.start_pre_vote()
    assert node.state == node.state.FOLLOWER
    assert node.term == 0  # Term should NOT increment during pre-vote
    assert hasattr(node, "_pre_candidacy") and node._pre_candidacy is not None

    # Grant one pre-vote
    node.pre_request_vote_reply("2", True, 0)

    # Should now have triggered real election
    assert node.state == node.state.CANDIDATE
    assert node.term == 1
    assert node.vote.node_id == "1"


def test_prevote_denied_by_lease():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()

    # We just heard from leader
    node.last_followed = node.get_now()

    # A disruptive node tries to start an election
    granted, term, lc_addr = node.pre_request_vote("disruptive", 10, 0, -1)
    # Should be denied because our leader lease is active
    assert not granted


def test_node_state_eq_garbage():
    state = NodeState()
    assert (state == object()) is False
    assert (state == 2.2) is False


def test_become_follower_already_follower():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    assert node.state == node.state.FOLLOWER
    assert isinstance(node.follower_timeout, float)
    # Second call still a follower; follower timeout is rescheduled (new jitter).
    node.become_follower()
    assert node.state == node.state.FOLLOWER
    assert isinstance(node.follower_timeout, float)


def test_become_follower_term_logic():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.term = 10
    # Higher term
    node.become_follower(term=15)
    assert node.term == 15
    # Stale term - should ideally raise or ignore based on code
    with pytest.raises(RuntimeError, match="Term lower than ours"):
        node.become_follower(term=5)


def test_request_vote_safety_checks_exhaustive():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.term = 5

    # Higher term should reset vote
    node.vote = Vote("2", 5, granted=True)
    granted, term, lc_addr = node.request_vote("3", 10, last_term=10, last_index=100)
    assert granted
    assert node.term == 10
    assert node.vote.node_id == "3"


def test_append_entries_reply_fail_backtracking():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    peer2_node = Node("2")
    peer2_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(peer2_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    node.next_index["2"] = 10
    # sent_term, sent_prev_term, sent_prev_index, sent_log_index, node_id, term, success, conflict_index, conflict_term
    node.append_entries_reply(1, 1, 9, 10, "2", 1, False, None, None)
    assert node.next_index["2"] == 9


def test_send_append_entries_no_entry():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    peer2_node = Node("2")
    peer2_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(peer2_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    # next_index points beyond log
    node.next_index["2"] = 100
    node.send_append_entries(node.peers[0])
    # Should handle missing entry gracefully (branch check)


def test_install_snapshot_reply_higher_term():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    # Receive snapshot reply with higher term
    node.install_snapshot_reply("2", 10)
    assert node.state == node.state.FOLLOWER
    assert node.term == 10


def test_leader_beacon_not_leader():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    # Manual call
    node.leader_beacon()
    # Should exit early (missed branch covered)


def test_request_vote_step_down():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.term = 1
    # Candidate with higher term
    granted, term, lc_addr = node.request_vote("peer2", 5, last_term=0, last_index=-1)
    assert granted
    assert node.term == 5
    assert node.state == node.state.FOLLOWER


def test_append_entries_higher_term_step_down():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.term = 1
    # Higher term from leader
    success, term, _, _, lc_addr = node.append_entries("leader", 5, 5, 0, 0)
    assert node.term == 5
    assert node.state == node.state.FOLLOWER


def test_append_entries_reply_higher_term_step_down():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    peer2_node = Node("2")
    peer2_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(peer2_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()
    node.term = 1
    # Receive reply with higher term
    node.append_entries_reply(1, 0, -1, 0, "2", 5, False)
    assert node.term == 5
    assert node.state == node.state.FOLLOWER


def test_install_snapshot_safety():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.term = 5
    # Stale term in snapshot
    term, lc_addr = node.install_snapshot("leader", 1, 10, 1, b"data")
    assert term == 5

    # Snapshot for already committed data
    node.commit_index = 20
    term, lc_addr = node.install_snapshot("leader", 5, 10, 1, b"data")
    assert term == 5


def test_install_snapshot_no_overlap():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = _storage(tmpdir)
        node = Node("1", storage=storage)
        node.register_schedule_timeout(lambda t, c: None)
        node.log.add(1, "cmd0")

        # Snapshot has NO overlap with current log (last index is 100)
        node.install_snapshot("leader", 1, 100, 1, b"data")
        assert node.log.last_included_index == 100
        assert len(node.log.entries) == 0


def test_candidacy_timeout_callback_edge_cases():
    node = Node("1")
    node.peers = [ManualPeer(Node("2"))]
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    node.become_candidate()
    c = node.candidacy

    # Term advanced in between
    node.term = 10
    node.candidacy_timeout_callback(c)
    assert node.candidacy is None


def test_peer_methods():
    from tests.support.mock import MagicMock

    peer_node = MagicMock(spec=Node)
    peer_node.address = "remote_node"
    peer = Peer(peer_node)

    callback = MagicMock()

    # request_vote
    peer_node.request_vote.return_value = (True, 1, None)
    peer.request_vote(callback, "node1", 1, 0, -1)
    callback.assert_called_once_with("remote_node", True, 1)

    # append_entries
    callback.reset_mock()
    peer_node.append_entries.return_value = (True, 1, None, None, None)
    peer.append_entries(
        callback,
        "node1",
        1,
        0,
        -1,
        0,
        {"term": 1, "cmd": "noop", "node_id": "1"},
    )
    callback.assert_called_once()

    # install_snapshot
    callback.reset_mock()
    peer_node.install_snapshot.return_value = (1, None)
    peer.install_snapshot(callback, "node1", 1, 10, 1, b"data")
    callback.assert_called_once_with("remote_node", 1)


def test_append_entries_reply_success_logic():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    peer2_node = Node("2")
    peer2_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(peer2_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    # Success with entries
    # sent_term, sent_prev_term, sent_prev_index, sent_log_index,
    # node_id, term, success, conflict_idx, conflict_term, *entries
    node.log_add("cmd0")
    node.append_entries_reply(
        1,
        None,
        -1,
        0,
        "2",
        1,
        True,
        None,
        None,
        {"index": 0, "term": 1},
    )
    assert node.match_index["2"] == 0
    assert node.next_index["2"] == 1

    # Success with beacon (no entries)
    node.append_entries_reply(1, 1, 0, 0, "2", 1, True, None, None)
    assert node.match_index["2"] == 0


def test_advance_commit_index_quorum():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    # 3 node cluster: 1 (self), 2, 3. Majority is 2.
    p2_node = Node("2")
    p2_node.register_schedule_timeout(lambda t, c: None)
    p3_node = Node("3")
    p3_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(p2_node), Peer(p3_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    node.log_add("cmd0")  # index 0

    # Replicated to 2
    node.match_index["2"] = 0
    node.advance_commit_index()
    assert node.commit_index == 0


def test_request_votes_empty_log_with_snapshot():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()

    # Empty log but has a snapshot at index 50
    node.log.last_included_index = 50
    node.log.last_included_term = 3

    # Force candidacy
    node.state.become_candidate()
    node.candidacy = Candidacy(4, ["2"])

    # This should trigger request_votes using snapshot metadata
    node.request_votes()


def test_send_append_entries_missing_prev_entry():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    peer2_node = Node("2")
    peer2_node.register_schedule_timeout(lambda t, c: None)
    node.peers = [Peer(peer2_node)]
    node.become_follower()
    node.become_candidate()
    if node.state != node.state.LEADER:
        node.become_leader()

    # next_index points to an entry that doesn't exist and isn't the snapshot index
    node.next_index["2"] = 10
    node.send_append_entries(node.peers[0])


def test_install_snapshot_with_overlap():
    from salt.cluster.consensus.raft import CounterStateMachine

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = _storage(tmpdir)
        sm = CounterStateMachine()
        node = Node("a", storage=storage, state_machine=sm)
        node.register_schedule_timeout(lambda t, c: None)

        # Log has entries 0, 1, 2
        node.log.add(1, "cmd0")
        node.log.add(1, "cmd1")
        node.log.add(1, "cmd2")

        # Leader sends snapshot up to index 1
        snapshot_data = json.dumps({"count": 2}).encode("utf-8")
        node.install_snapshot("leader", 1, 1, 1, snapshot_data)

        # Index 0 and 1 should be gone, index 2 should remain
        assert node.log.last_included_index == 1
        assert len(node.log.entries) == 1
        assert node.log.entries[0].cmd == "cmd2"
        assert sm.count == 2


def test_log_add_raises_not_leader():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()
    with pytest.raises(NotLeader):
        node.log_add("cmd")


def test_locking_node_uses_thread_lock():
    node = LockingNode("1", [])
    assert hasattr(node._lock, "acquire")


def test_vote_info_and_node_id_alias():
    v = Vote("peer", 3, granted=True)
    assert v.node_id == "peer"
    assert v.info() == {"voter_id": "peer", "term": 3, "granted": True}


def test_manual_peer_install_snapshot_request_shape():
    inner = Node("b")
    mp = ManualPeer(inner, node_id="peerb")
    mp.install_snapshot(None, "L", 1, 0, 0, b"blob")
    assert mp.requests[-1][0] == "is"
    mp.drop_requests()
    assert mp.requests == []
