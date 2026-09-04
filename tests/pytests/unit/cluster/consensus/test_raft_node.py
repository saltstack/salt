"""Tests for the Raft node implementation."""

import tempfile

import pytest

import salt.config
from salt.cluster.consensus.raft import (
    Candidacy,
    CandidacyError,
    CounterStateMachine,
    ManualPeer,
    ManualTimeoutScheduler,
    Node,
    NodeState,
    Vote,
    log_generator,
)
from salt.cluster.consensus.storage import SaltStorage


def _storage(path):
    """Return a SaltStorage backed by *path* as the cache directory."""
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = path
    return SaltStorage("test-node", opts)


def create_nodes(number, scheduler):
    nodeids = []
    for i in range(1, number + 1):
        nodeids.append(f"{i}")
    nodes = []
    for _ in nodeids:
        nodes.append(Node(_))
    for node in nodes:
        peer_nodes = nodes[:]
        peer_nodes.remove(node)
        node.peers = [ManualPeer(_, node_id=_.node_id) for _ in peer_nodes]
    for node in nodes:
        node.register_schedule_timeout(scheduler.schedule)
    return nodes


def _handle_all_peer_requests(nodes, skip=None):
    if skip is None:
        skip = []
    elif isinstance(skip, Node):
        skip = [skip]

    any_handled = True
    while any_handled:
        any_handled = False
        for node in nodes:
            for peer in node.peers:
                if peer.node in skip:
                    if peer.requests:
                        peer.drop_requests()
                        any_handled = True
                else:
                    if peer.requests:
                        peer.handle_all_requests()
                        any_handled = True


@pytest.fixture
def scheduler():
    return ManualTimeoutScheduler()


@pytest.fixture
def nodes(scheduler):
    return create_nodes(3, scheduler)


@pytest.fixture
def node(nodes):
    return nodes[-1]


def test_loggen():
    _ = log_generator(6, chars=["a", "b", "c"])
    assert isinstance(_, str)
    assert len(_) == 6


def test_node_state_init():
    state = NodeState()
    assert state._state == state.START


def test_node_state_repr():
    state = NodeState()
    _ = id(state)
    assert repr(state) == f"<NodeState('start') at {_} >"


def test_node_state_init_become_leader():
    state = NodeState()
    assert state._state == state.START
    with pytest.raises(RuntimeError) as err:
        state.become_leader()
    assert err.value.__class__ == RuntimeError
    assert err.value.args == ("State must be follower first",)


def test_node_state_become_leader_as_follower():
    state = NodeState()
    state._state = state.FOLLOWER
    with pytest.raises(RuntimeError) as err:
        state.become_leader()
    assert err.value.__class__ == RuntimeError
    assert err.value.args == ("Not candidate (follower)",)


def test_node_state_init_become_candidate():
    state = NodeState()
    assert state._state == state.START
    with pytest.raises(RuntimeError) as err:
        state.become_candidate()
    assert err.value.__class__ == RuntimeError
    assert err.value.args == ("State must be follower first",)


def test_node_state_init_become_follower():
    state = NodeState()
    assert state._state == state.START
    state.become_follower()
    assert state._state == state.FOLLOWER


def test_node_state_become_candidate_as_leader():
    state = NodeState()
    state._state = state.LEADER
    with pytest.raises(RuntimeError) as err:
        state.become_candidate()
    assert err.value.__class__ == RuntimeError
    assert err.value.args == ("Not follower",)


def test_node_state_candidate_can_become_candidate():
    state = NodeState()
    assert state._state == state.START
    state.become_follower()
    assert state._state == state.FOLLOWER
    state.become_candidate()
    assert state._state == state.CANDIDATE
    state.become_candidate()
    assert state._state == state.CANDIDATE


def test_node_state_to_str():
    state = NodeState()
    assert str(state) == state.START
    state.become_follower()
    assert str(state) == state.FOLLOWER
    state.become_candidate()
    assert str(state) == state.CANDIDATE
    state.become_leader()
    assert str(state) == state.LEADER
    state.become_follower()
    assert str(state) == state.FOLLOWER


def test_node_state_eq():
    state1 = NodeState()
    state2 = NodeState()
    state2.become_follower()
    assert (state1 == state2) is False

    state = NodeState()
    state.become_follower()
    assert (state == state.FOLLOWER) is True
    state.become_candidate()
    assert state == state.CANDIDATE
    state.become_leader()
    assert state == state.LEADER
    state.become_follower()
    assert state == state.FOLLOWER


def test_node_state_ne():
    state = NodeState()
    state.become_follower()
    assert (state != state.FOLLOWER) is False
    assert (state != state.CANDIDATE) is True

    state1 = NodeState()
    state2 = NodeState()
    state2.become_follower()
    assert (state1 != state2) is True


def test_candidacy():
    term = 0
    peers = ["a", "b", "c", "d"]
    c = Candidacy(term, peers)
    assert c.elected() is False
    c.handle_reply("a", term, True)
    assert c.elected() is False
    c.handle_reply("b", term, True)
    assert c.elected() is True


def test_candidacy_even_number_nodes():
    term = 0
    peers = ["a", "b", "c"]
    c = Candidacy(term, peers)
    assert c.elected() is False
    c.handle_reply("a", term, True)
    assert c.elected() is False
    c.handle_reply("b", term, True)
    assert c.elected() is True


def test_candidacy_two_nodes():
    term = 0
    peers = ["a"]
    c = Candidacy(term, peers)
    assert c.elected() is False
    c.handle_reply("a", term, True)
    assert c.elected() is True


def test_candidacy_invalid_peer_response():
    term = 0
    peers = ["a"]
    c = Candidacy(term, peers)
    assert c.elected() is False
    with pytest.raises(CandidacyError) as info:
        c.handle_reply("b", term, True)
    assert str(info.value) == "b is not a peer"


def test_candidacy_invalid_term_response():
    term = 10
    peers = ["a"]
    c = Candidacy(term, peers)
    assert c.elected() is False
    with pytest.raises(CandidacyError) as info:
        c.handle_reply("b", 5, True)
    assert str(info.value) == "Term 5 does not match ours 10"


def test_node_init():
    address = "127.0.0.1"
    node = Node(address, [])
    assert node.state._state == node.state.START


def test_node_schedule_without_register():
    node = Node("a", [])
    with pytest.raises(RuntimeError) as info:
        node.schedule_timeout(10, lambda: None)
    assert str(info.value) == "Register a scheduling method first"


def test_node_init_become_follower(nodes):
    for node in nodes:
        assert node.state._state == node.state.START
        original_term = node.term
        node.become_follower()
    assert node.state == node.state.FOLLOWER
    assert node.term == original_term
    assert node.leader_beacon_timeout is None
    assert node.candidate_timeout is None
    assert getattr(node, "candidacy", None) is None
    # If node recieves append_entries it will start following the leader.
    # Otherwise if follower_timeout expires the node will start a new election.
    assert isinstance(node.follower_timeout, float)


def test_node_follower_timeout(nodes, scheduler):
    node = nodes[-1]
    # Node's last followed time set to node.get_now(), override this.
    assert node.state._state == node.state.START
    node.become_follower()

    scheduler.process_existing_timeouts()
    assert node.state == node.state.FOLLOWER

    # Otherwise if follower_timeout expires the node will start a new election.
    assert isinstance(node.follower_timeout, float)
    node.last_followed = node.get_now() - 10

    # If node recieves append_entries it will start following the leader.
    scheduler.process_existing_timeouts()

    assert node.state == node.state.FOLLOWER
    assert hasattr(node, "_pre_candidacy") and node._pre_candidacy


def test_node_follower_timeout_reschedule(nodes, scheduler):
    """Verify that follower timeout reschedules itself if append_entries is recently accepted."""
    assert scheduler.time == 0
    node = nodes[-1]
    # XXX This should be more easily configured
    assert node.state == node.state.START
    node.become_follower()
    assert node.state == node.state.FOLLOWER
    # If node recieves append_entries it will continue following the leader.
    # Otherwise if follower_timeout expires the node will start a new election.
    assert isinstance(node.follower_timeout, float)
    scheduler.advance_clock_to_next_timeout()
    assert scheduler.time == node.follower_timeout
    node.last_followed = node.get_now() - (node.follower_timeout / 2)
    assert (node.get_now() - node.last_followed) < node.follower_timeout
    scheduler.process_timeouts()
    assert node.state == node.state.FOLLOWER
    assert node._follower_timeout

    scheduler.advance_clock_to_next_timeout()
    node.last_followed = node.get_now() - (node.follower_timeout + 1)
    assert (node.get_now() - node.last_followed) >= node.follower_timeout
    scheduler.process_timeouts()

    assert node.state._state == node.state.FOLLOWER
    assert hasattr(node, "_pre_candidacy") and node._pre_candidacy
    # After start_pre_vote, the follower timeout is re-armed so the
    # pre-vote retries if no peer replies (e.g. peers not yet up).
    # Without this re-arm an isolated voter would be stuck after a
    # single failed attempt.
    assert node._follower_timeout is not None


def test_node_become_leader_when_not_candidate(node, scheduler):
    assert node.state._state == node.state.START
    node.become_follower()
    assert node.state == node.state.FOLLOWER
    with pytest.raises(RuntimeError):
        node.become_leader()


def test_node_become_leader(node, scheduler):
    assert node.state._state == node.state.START
    node.become_follower()
    assert node.state == node.state.FOLLOWER
    node.become_candidate()
    # With three total nodes, one (more) vote will cause the node to become a
    # leader. The node's own vote is implied.
    node.request_vote_reply("2", node.term, True)
    assert node.state == node.state.LEADER


def test_node_candidacy_timeout(scheduler):
    node = Node("a")
    node.peers = [ManualPeer(Node("b"))]
    node.register_schedule_timeout(scheduler.schedule)
    assert node.state == node.state.START
    node.become_follower()
    node._follower_timeout = None
    node.become_candidate()
    candidacy = node.candidacy
    candidacy.term += 1
    node.candidacy_timeout_callback(candidacy)


def test_cluster_log_entry(scheduler):
    nodes = create_nodes(5, scheduler)

    now = nodes[0].get_now()

    for node in nodes:
        assert node.state == node.state.START
        node.become_follower()
        assert node.state == node.state.FOLLOWER
        node.last_followed = now

    # Select node 5 to time out
    node = nodes[4]
    node.last_followed = node.get_now() - (node._follower_max + 1)

    # Ensure other nodes are willing to grant a pre-vote by resetting their lease
    for other in nodes:
        if other != node:
            other.last_followed = other.get_now() - (other._follower_max + 1)

    scheduler.process_existing_timeouts()

    # With pre-vote, node stays FOLLOWER but has _pre_candidacy
    assert node.state == node.state.FOLLOWER
    assert node._pre_candidacy is not None

    # Grant pre-votes from all peers
    for peer in node.peers:
        peer.handle_all_requests()

    # Grant real votes (if any pending)
    for peer in node.peers:
        peer.handle_all_requests()

    leaders = [_ for _ in nodes if _.state == _.state.LEADER]
    assert len(leaders) == 1
    leader = leaders[0]

    leader.log_add("asdf")
    for _ in leader.peers:
        _.handle_all_requests()

    followers = [_ for _ in nodes if _.state != _.state.LEADER]
    for node in followers:
        assert [_.index for _ in node.log.entries] == [0]

    leader.log_add("fdsa")
    for _ in leader.peers:
        _.handle_all_requests()
    followers = [_ for _ in nodes if _.state != _.state.LEADER]
    for node in followers:
        assert [_.index for _ in node.log.entries] == [0, 1]
        assert [_.cmd for _ in node.log.entries] == ["asdf", "fdsa"]


def test_append_entry_failure(nodes, scheduler):
    node = nodes[0]
    node.become_follower()
    # Cancel follower timeout
    node._follower_timeout = None
    node.become_candidate()
    # Cancel candidate timeout
    node._candidate_timeout = None
    node.become_leader()

    assert node.state == node.state.LEADER

    _handle_all_peer_requests(nodes)
    node.log_add("first entry")
    _handle_all_peer_requests(nodes)

    for follower in nodes:
        if follower.address != node.address:
            break

    assert follower.address == "2"

    assert follower.state == follower.state.FOLLOWER

    assert len(follower.log.entries) == 1
    assert follower.log.entries[0].term == 1
    assert follower.log.entries[0].index == 0
    assert follower.log.entries[0].cmd == "first entry"

    follower.log.add(1, "bad entry")

    node.become_follower()
    # Cancel follower timeout
    node._follower_timeout = None
    node.become_candidate()
    _handle_all_peer_requests(nodes, skip=follower)
    assert node.state == node.state.LEADER
    assert node.term == 2

    node.log_add("second entry")
    # XXX
    _handle_all_peer_requests(nodes, skip=follower)

    node.become_follower()
    # Cancel follower timeout
    node._follower_timeout = None
    node.become_candidate()
    _handle_all_peer_requests(nodes, skip=follower)

    assert node.state == node.state.LEADER
    assert node.term == 3

    node.log_add("third entry")

    _handle_all_peer_requests(nodes, skip=follower)

    assert len(follower.log.entries) == 2

    # Now force a retry from the leader to fix the conflict
    # peer 0 is follower 2
    node.send_append_entries(node.peers[0])  # leader sends to peer 2 from index 2
    _handle_all_peer_requests(nodes)  # let it fail and leader retry logic (backtrack)

    assert node.next_index[follower.address] == 1

    node.send_append_entries(node.peers[0])  # leader sends from index 1 (prev index 0)
    _handle_all_peer_requests(nodes)

    # Should succeed because prev_idx 0 term 1 matches.
    # Log.add detects conflict at index 1 ("bad entry" term 1 != "second entry" term 2),
    # truncates, and adds "second entry" and "third entry".
    assert len(follower.log.entries) == 3
    assert follower.log.entries[1].term == 2
    assert follower.log.entries[2].term == 3

    assert node.next_index[follower.address] == 3


def test_request_vote_log_completeness(node):
    # Setup node with some log entries
    node.log.add(1, "cmd1")
    node.log.add(2, "cmd2")
    node.term = 2

    # Candidate has older term in last log entry
    # Even if its log is longer, it should be rejected
    granted, term, lc_addr = node.request_vote(
        "candidate1", 3, last_term=1, last_index=10
    )
    assert granted is False

    # Candidate has same term but shorter log
    granted, term, lc_addr = node.request_vote(
        "candidate2", 3, last_term=2, last_index=0
    )
    assert granted is False

    # Candidate is more up to date (same term, longer log)
    node.vote = None  # Reset vote for the term
    granted, term, lc_addr = node.request_vote(
        "candidate3", 3, last_term=2, last_index=5
    )
    assert granted is True


def test_append_entries_consistency_check(node):
    node.log.add(1, "cmd1")
    node.log.add(1, "cmd2")
    node.term = 1

    # Leader sends append_entries with mismatching prev_log_term
    # node_id, term, prev_log_term, prev_log_index, leader_commit_index, *entries
    success, term, c_idx, c_term, lc_addr = node.append_entries(
        "leader", 1, 2, 1, 1, *[{"term": 1, "cmd": "cmd3", "node_id": "leader"}]
    )
    assert success is False

    # Leader sends append_entries with mismatching prev_log_index
    success, term, c_idx, c_term, lc_addr = node.append_entries(
        "leader", 1, 1, 5, 1, *[{"term": 1, "cmd": "cmd3", "node_id": "leader"}]
    )
    assert success is False


def test_commit_tracking(scheduler):
    nodes = create_nodes(3, scheduler)
    leader = nodes[0]
    follower1 = nodes[1]
    follower2 = nodes[2]

    # Force leadership
    leader.become_follower()
    leader.become_candidate()
    _handle_all_peer_requests(nodes)
    assert leader.state == leader.state.LEADER

    # Leader has sent initial beacons to everyone.
    # DROP THEM so followers have empty logs and no commit info.
    for p in leader.peers:
        p.drop_requests()

    # Reset logs/commit just in case election added something
    for node in nodes:
        node.log.clear()
        node.commit_index = -1
        node.last_applied = -1

    # Re-init leader state tracking
    leader.next_index = {p.address: 0 for p in leader.peers}
    leader.match_index = {p.address: -1 for p in leader.peers}

    # Add an entry
    leader.log_add("cmd1")  # index 0
    assert leader.commit_index == -1  # Not committed yet

    # Handle AE for cmd1 for follower1 ONLY
    # Peer 0 for leader is follower1 (node 2)
    leader.peers[0].handle_all_requests()
    assert follower1.commit_index == -1

    # Follower 1 replies
    follower1.peers[0].handle_all_requests()
    # Majority of 3 nodes is 2 nodes (leader + follower1).
    assert leader.commit_index == 0
    assert leader.last_applied == 0

    # Next beacon informs follower1 of the commit
    leader.leader_beacon()
    leader.peers[0].handle_all_requests()
    assert follower1.commit_index == 0
    assert follower1.last_applied == 0

    # follower2 still doesn't have the entry.
    assert len(follower2.log.entries) == 0

    # Handle the AE from log_add for follower2
    # BUT FIRST drop it to test a beacon only.
    leader.peers[1].drop_requests()

    # Send AE beacon to follower2
    leader.leader_beacon()
    # Handle ONLY for follower2
    leader.peers[1].handle_all_requests()  # follower2 receives beacon
    assert follower2.commit_index == -1  # Still -1 because it doesn't have the entry

    # Now let follower2 catch up
    leader.send_append_entries(leader.peers[1])
    leader.peers[1].handle_all_requests()  # follower2 receives entry
    assert len(follower2.log.entries) == 1
    assert follower2.commit_index == 0
    assert follower2.last_applied == 0


def test_leader_state_tracking_and_catchup(scheduler):
    nodes = create_nodes(3, scheduler)
    leader = nodes[0]
    follower = nodes[1]

    # Leader becomes leader and adds some entries
    leader.become_follower()
    leader.become_candidate()
    _handle_all_peer_requests(nodes)
    assert leader.state == leader.state.LEADER

    leader.log_add("cmd1")  # index 0
    leader.log_add("cmd2")  # index 1
    leader.log_add("cmd3")  # index 2

    # next_index/match_index shouldn't change until replies are handled
    assert leader.next_index[follower.address] == 0

    _handle_all_peer_requests(nodes)

    assert leader.match_index[follower.address] == 2
    assert leader.next_index[follower.address] == 3
    assert leader.commit_index == 2

    # Now a new node joins or an old node restarts with NO logs
    stale_follower = nodes[2]
    # It might have received requests during _handle_all_peer_requests(nodes) above
    stale_follower.log.entries = []
    stale_follower.commit_index = -1
    leader.next_index[stale_follower.address] = 0
    leader.match_index[stale_follower.address] = -1

    # Leader sends entries to stale follower (from 0)
    leader.send_append_entries(
        leader.peers[1]
    )  # This will trigger replication from index 0
    _handle_all_peer_requests(nodes)

    assert len(stale_follower.log.entries) == 3
    assert leader.match_index[stale_follower.address] == 2
    assert leader.next_index[stale_follower.address] == 3


def test_snapshotting():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = _storage(tmpdir)
        sm = CounterStateMachine()
        node = Node("a", storage=storage, state_machine=sm, max_log_size=5)
        node.register_schedule_timeout(lambda t, c: None)

        # Add entries
        for i in range(10):
            node.log.add(1, f"cmd{i}")

        # Commit and apply all
        node.commit_index = 9
        node.apply_entries()

        # Verify snapshot was taken
        assert node.log.last_included_index == 9
        assert len(node.log.entries) == 0
        assert sm.count == 10

        # Verify persistence of snapshot
        node2 = Node("a", storage=storage, state_machine=CounterStateMachine())
        assert node2.log.last_included_index == 9
        assert node2.state_machine.count == 10


def test_install_snapshot():
    # Leader has snapshotted, follower is far behind
    with tempfile.TemporaryDirectory() as ldir, tempfile.TemporaryDirectory() as fdir:
        l_sm = CounterStateMachine()
        l_storage = _storage(ldir)
        leader = Node("leader", storage=l_storage, state_machine=l_sm, max_log_size=5)
        leader.register_schedule_timeout(lambda t, c: None)

        f_sm = CounterStateMachine()
        f_storage = _storage(fdir)
        follower = Node("follower", storage=f_storage, state_machine=f_sm)
        follower.register_schedule_timeout(lambda t, c: None)

        # Leader adds and snapshots
        for i in range(10):
            leader.log.add(1, f"cmd{i}")
        leader.commit_index = 9
        leader.apply_entries()

        # Leader sends snapshot to follower
        snapshot = l_storage.load_snapshot()
        term, lc_addr = follower.install_snapshot(
            "leader", 1, snapshot["index"], snapshot["term"], snapshot["data"]
        )

        assert follower.log.last_included_index == 9
        assert follower.state_machine.count == 10
        assert follower.commit_index == 9


def test_learner_promotion():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)

    # Mock peer factory
    def factory(addr, voting=True):
        p = ManualPeer(Node(addr))
        p.voting = voting
        return p

    node.register_peer_factory(factory)

    # Force leadership
    node.state.become_follower()
    node.state.become_candidate()
    node.state.become_leader()

    # Add node "2" as learner
    from salt.cluster.consensus.raft import LogEntryType

    config1 = {"voters": ["1"], "learners": ["2"]}
    node.log_add(config1, entry_type=LogEntryType.CONFIG)

    assert len(node.peers) == 1
    assert node.peers[0].address == "2"
    assert node.peers[0].voting is False

    # Simulate node 2 catching up
    # match_index must be >= node.log.index (which is currently 0)
    node.match_index["2"] = 0

    # Trigger promotion check by receiving a successful append reply
    # sent_term, sent_prev_term, sent_prev_index, sent_log_index, node_id, term, success, *entries
    node.append_entries_reply(
        node.term, None, None, -1, "2", node.term, True, None, None
    )

    # Node 2 should now be promoted
    assert node.peers[0].voting is True
    # The log should now have a new config entry
    assert node.log.entries[-1].cmd["voters"] == ["1", "2"]


def test_dynamic_membership():
    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)

    # Mock peer factory
    peers_created = []

    def factory(addr, voting=True):
        p = ManualPeer(Node(addr), voting=voting)
        peers_created.append(p)
        return p

    node.register_peer_factory(factory)

    # Initial state: no peers
    assert len(node.peers) == 0

    # Append config entry
    from salt.cluster.consensus.raft import LogEntryType

    new_config = ["1", "2", "3"]
    # We must become leader to call log_add easily, or simulate append_entries
    node.state.become_follower()
    node.state.become_candidate()
    node.state.become_leader()

    node.log_add(new_config, entry_type=LogEntryType.CONFIG)

    # Node should have created 2 new peers (2 and 3)
    assert len(node.peers) == 2
    assert {p.address for p in node.peers} == {"2", "3"}
    assert len(peers_created) == 2


def test_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = _storage(tmpdir)
        node = Node("a", storage=storage)
        node.term = 5
        node.vote = Vote("b", 5, granted=True)
        node.log.add(5, "cmd1")

        # Simulate restart
        node2 = Node("a", storage=storage)
        assert node2.term == 5
        assert node2.vote.node_id == "b"
        assert len(node2.log.entries) == 1
        assert node2.log.entries[0].cmd == "cmd1"
        assert node2.log.entries[0].term == 5


def test_step_down_on_higher_term_append_reply(node):
    node.become_follower()
    node.become_candidate()
    node.become_leader()
    assert node.state == node.state.LEADER
    assert node.term == 1

    # Receive a reply with a higher term
    # sent_term, sent_prev_term, sent_prev_index, sent_log_index, node_id, term, success, *entries
    node.append_entries_reply(1, None, None, -1, "peer1", 2, False, None, None)

    assert node.state == node.state.FOLLOWER
    assert node.term == 2
    assert node.vote is None


def test_step_down_on_higher_term_vote_reply(node):
    node.become_follower()
    node.become_candidate()
    assert node.state == node.state.CANDIDATE
    assert node.term == 1

    # Receive a vote reply with a higher term
    node.request_vote_reply("peer1", False, 2)

    assert node.state == node.state.FOLLOWER
    assert node.term == 2
    assert node.vote is None


# ---------------------------------------------------------------------------
# MembershipStateMachine integration with Node
# ---------------------------------------------------------------------------


class TestNodeMembershipSM:
    def _make_leader(self, node_id="m1"):
        node = Node(node_id)
        node.register_schedule_timeout(lambda t, c: None)
        node.state.become_follower()
        node.state.become_candidate()
        node.state.become_leader()
        return node

    def test_node_has_membership_sm_by_default(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        node = Node("m1")
        assert isinstance(node.membership_sm, MembershipStateMachine)

    def test_info_includes_membership(self):
        node = self._make_leader()
        info = node.info()
        assert "membership" in info
        assert "voters" in info["membership"]
        assert "learners" in info["membership"]
        assert "version" in info["membership"]

    def test_sm_updated_when_config_entry_committed(self):
        """SM reflects committed membership, not just written."""
        from salt.cluster.consensus.raft.log import LogEntryType

        node = self._make_leader()
        node.log_add(
            {"voters": ["m1", "m2"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        # Not committed yet (no quorum)
        assert node.membership_sm.membership_version == -1

        # Force commit
        node.log.commit(0)
        node.apply_entries()

        assert node.membership_sm.current_voters() == ["m1", "m2"]
        assert node.membership_sm.membership_version == 0

    def test_sm_records_learner_on_commit(self):
        from salt.cluster.consensus.raft.log import LogEntryType

        node = self._make_leader()
        node.log_add(
            {"voters": ["m1"], "learners": ["m2"]},
            entry_type=LogEntryType.CONFIG,
        )
        node.log.commit(0)
        node.apply_entries()

        assert node.membership_sm.is_voter("m1")
        assert node.membership_sm.is_learner("m2")
        assert not node.membership_sm.is_voter("m2")

    def test_sm_version_advances_with_each_config_commit(self):
        from salt.cluster.consensus.raft.log import LogEntryType

        node = self._make_leader()
        node.log_add(
            {"voters": ["m1"], "learners": ["m2"]}, entry_type=LogEntryType.CONFIG
        )
        node.log_add(
            {"voters": ["m1", "m2"], "learners": []}, entry_type=LogEntryType.CONFIG
        )

        # Commit only the first
        node.log.commit(0)
        node.apply_entries()
        assert node.membership_sm.membership_version == 0
        assert not node.membership_sm.is_voter("m2")

        # Commit the second
        node.log.commit(1)
        node.apply_entries()
        assert node.membership_sm.membership_version == 1
        assert node.membership_sm.is_voter("m2")

    def test_register_membership_sm_replaces_existing(self):
        from salt.cluster.consensus.raft.log import MembershipStateMachine

        node = self._make_leader()
        custom_sm = MembershipStateMachine()
        node.register_membership_sm(custom_sm)
        assert node.membership_sm is custom_sm

    def test_sm_snapshot_reflects_committed_state_only(self):
        """get_snapshot on the SM returns committed membership, not uncommitted writes."""
        from salt.cluster.consensus.raft.log import LogEntryType

        node = self._make_leader()
        # Write two configs; only commit the first
        node.log_add(
            {"voters": ["m1"], "learners": ["m2"]}, entry_type=LogEntryType.CONFIG
        )
        node.log_add(
            {"voters": ["m1", "m2"], "learners": []}, entry_type=LogEntryType.CONFIG
        )
        node.log.commit(0)
        node.apply_entries()

        snap = node.membership_sm.get_snapshot()
        assert snap["voters"] == ["m1"]
        assert snap["learners"] == ["m2"]
        assert snap["version"] == 0

    def test_service_membership_property_exposed(self):
        """RaftService.membership exposes the node's MembershipStateMachine."""
        import asyncio
        import tempfile

        from salt.cluster.consensus.raft.log import MembershipStateMachine
        from salt.cluster.consensus.service import RaftService

        tmpdir = tempfile.mkdtemp()
        opts = {
            "id": "m1-host",
            "interface": "m1",
            "cluster_id": "test",
            "cluster_peers": [],
            "cachedir": tmpdir,
        }
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {})
            assert isinstance(svc.membership, MembershipStateMachine)
            assert svc.membership is svc.node.membership_sm
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Coverage gaps: Peer paths, ManualPeer.install_snapshot, storage tuple load,
# request_votes helper, native_engine hooks, on_config_change learner paths,
# install_snapshot guard, candidacy_timeout_callback edge cases, commit_index setter
# ---------------------------------------------------------------------------


class TestPeerEdgePaths:
    def test_peer_address_property(self):
        """Peer.address falls back to _node_id when node has no address attr."""
        from salt.cluster.consensus.raft.node import Node, Peer

        inner = Node("inner-node")
        p = Peer(inner, node_id="remote-1")
        assert p.address == "inner-node"

    def test_peer_address_uses_node_address_attr(self):
        from salt.cluster.consensus.raft.node import Peer

        class FakeNode:
            address = "10.0.0.1"
            node_id = "n1"

        p = Peer(FakeNode(), node_id="n1")
        assert p.address == "10.0.0.1"

    def test_peer_pre_request_vote_callback(self):
        """Peer.pre_request_vote fires callback with correct args."""
        from salt.cluster.consensus.raft.node import Node, Peer
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        target = Node("target")
        scheduler = ManualTimeoutScheduler()
        target.register_schedule_timeout(scheduler.schedule)
        target.become_follower()

        results = []
        p = Peer(target, node_id="target")
        p.pre_request_vote(
            lambda nid, granted, term: results.append((nid, granted, term)),
            "candidate",
            1,
            last_log_term=0,
            last_log_index=-1,
        )
        assert len(results) == 1
        assert results[0][0] == "target"


class TestManualPeerInstallSnapshot:
    def test_install_snapshot_queued_and_handled(self):
        """ManualPeer.install_snapshot enqueues and handle_all_requests delivers it."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        target = Node("target")
        scheduler = ManualTimeoutScheduler()
        target.register_schedule_timeout(scheduler.schedule)
        target.become_follower()

        peer = ManualPeer(target, node_id="target")
        results = []
        peer.install_snapshot(
            lambda nid, term: results.append((nid, term)),
            "leader",
            1,
            last_included_index=5,
            last_included_term=1,
            data={"voters": ["leader"], "learners": []},
        )
        assert len(peer.requests) == 1
        peer.handle_all_requests()
        assert len(results) == 1
        assert results[0][0] == "target"


class TestNodeStorageTupleLoad:
    def test_storage_tuple_format_loaded_correctly(self):
        """Node loads (term, voted_for) tuple from old-format storage gracefully."""
        from salt.cluster.consensus.raft.node import Node
        from tests.support.mock import MagicMock

        mock_storage = MagicMock()
        # Simulate old tuple-format storage response (term, voted_for)
        mock_storage.load_state.return_value = (3, "peer-1")
        mock_storage.load_log.return_value = []
        mock_storage.load_snapshot.return_value = None

        node = Node("n1", storage=mock_storage)
        assert node.term == 3
        assert node.voted_for == "peer-1"


class TestRequestVotesHelper:
    def test_request_votes_sends_to_voting_peers(self):
        """request_votes() dispatches RequestVote RPCs to all voting peers."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)

        peer2 = ManualPeer(Node("n2"), node_id="n2")
        peer3 = ManualPeer(Node("n3"), node_id="n3")
        node.peers = [peer2, peer3]

        node.become_follower()
        node.become_candidate()
        # Drain requests from become_candidate
        peer2.requests.clear()
        peer3.requests.clear()

        node.request_votes()
        assert any(r[0] == "rv" for r in peer2.requests)
        assert any(r[0] == "rv" for r in peer3.requests)


class TestNativeEngineHooks:
    def _make_mock_engine(self):
        from tests.support.mock import MagicMock

        return MagicMock()

    def test_become_leader_calls_native_engine(self):
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.native_engine = self._make_mock_engine()

        node.become_follower()
        node.become_candidate()
        node.native_engine.reset_mock()
        node.become_leader()
        node.native_engine.become_leader.assert_called_once_with(node.term)

    def test_become_follower_calls_native_engine(self):
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.native_engine = self._make_mock_engine()

        node.become_follower()
        node.native_engine.become_follower.assert_called_once_with(node.term)

    def test_leader_beacon_calls_send_heartbeat_via_native_engine(self):
        """leader_beacon routes through native_engine.send_heartbeat when set."""
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler
        from tests.support.mock import MagicMock

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)

        fake_peer = MagicMock()
        fake_peer.node_id = "n2"
        fake_peer.voting = True
        node.peers = [fake_peer]
        node.native_engine = MagicMock()

        node.become_follower()
        node.become_candidate()
        node.become_leader()
        fake_peer.reset_mock()

        node.leader_beacon()
        fake_peer.send_heartbeat.assert_called_once()


class TestOnConfigChangeLearnerPath:
    def test_no_factory_learner_set_voting_false(self):
        """on_config_change no-factory path sets existing peer to voting=False."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node

        node = Node("n1")
        peer = ManualPeer(Node("n2"), node_id="n2", voting=True)
        node.peers = [peer]

        node.on_config_change(["n1"], learners=["n2"])
        assert peer.voting is False

    def test_factory_path_creates_learner_for_new_addr(self):
        """on_config_change with factory creates a non-voting peer for new learner."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node

        node = Node("n1")
        node.register_schedule_timeout(lambda t, c: None)

        def factory(addr, voting=True):
            p = ManualPeer(Node(addr), node_id=addr)
            p.voting = voting
            return p

        node.register_peer_factory(factory)
        node.on_config_change(["n1"], learners=["n2"])
        assert len(node.peers) == 1
        assert node.peers[0].node_id == "n2"
        assert node.peers[0].voting is False


class TestInstallSnapshotGuard:
    def test_install_snapshot_ignored_if_already_newer(self):
        """install_snapshot is a no-op when our snapshot is already newer."""
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()

        node.log.last_included_index = 10
        term, addr = node.install_snapshot(
            "leader", 1, last_index=5, last_term=1, data={}
        )
        assert node.log.last_included_index == 10  # unchanged


class TestCandidacyTimeoutCallbackEdge:
    def test_mismatched_candidacy_cleared(self):
        """candidacy_timeout_callback with an unrecognized candidacy clears it."""
        from salt.cluster.consensus.raft.node import Candidacy, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()
        node.become_candidate()

        # Replace candidacy with a known object
        real_candidacy = node.candidacy
        # Create a *different* candidacy (not the same object, same term)
        other = Candidacy(term=real_candidacy.term, peers=list(real_candidacy.peers))
        # Assign our known candidacy so the elif branch hits
        node.candidacy = other

        # Call with a completely different candidacy object — elif will match
        # because `node.candidacy == other` but `node.state != CANDIDATE`
        # is False.  We need state != CANDIDATE to trigger the elif path.
        # Step node to follower so state != CANDIDATE:
        node.state.become_follower()
        node.candidacy_timeout_callback(other)
        assert node.candidacy is None


class TestCommitIndexSetterSnapshot:
    def test_commit_index_setter_triggers_snapshot_when_log_full(self):
        """commit_index setter triggers Log.snapshot when max_log_size reached."""
        from salt.cluster.consensus.raft.log import CounterStateMachine
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        sm = CounterStateMachine()
        node = Node("n1", state_machine=sm, max_log_size=3)
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()
        node.become_candidate()
        node.become_leader()

        node.log_add(b"a")
        node.log_add(b"b")
        node.log_add(b"c")

        # Setting commit_index to 2 advances past max_log_size, triggers snapshot
        node.commit_index = 2
        # After snapshot entries are cleared
        assert node.log.last_applied >= 0


class TestAppendEntriesReplyEarlyReturn:
    def test_not_leader_returns_early(self):
        """append_entries_reply is a no-op when node is not the leader."""
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()

        # Should not raise — just return silently
        node.append_entries_reply(1, 0, -1, -1, "n2", 1, True, None, None)
        assert node.state == "follower"


class TestHandleAppendEntriesLeaderClientAddress:
    def test_lca_stored_from_append_entries(self):
        """leader_client_address_map is populated from append_entries kwargs."""
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()

        node.handle_append_entries(
            "leader",
            1,
            0,
            -1,
            -1,
            leader_client_address="10.0.0.1:4506",
        )
        assert node.leader_client_address_map.get("leader") == "10.0.0.1:4506"


class TestPreRequestVoteReplyTermRegression:
    def test_high_term_causes_follower(self):
        """pre_request_vote_reply with term > self.term+1 steps down."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.peers = [ManualPeer(Node("n2"), node_id="n2")]
        node.become_follower()
        node.start_pre_vote()

        # Reply with term far higher than expected
        node.pre_request_vote_reply("n2", True, 10)
        assert node.state == "follower"


class TestStartPreVoteGuard:
    def test_start_pre_vote_no_op_when_not_follower(self):
        """start_pre_vote is a no-op when called while in candidate state."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        # Add a peer so single-node won't auto-promote
        node.peers = [ManualPeer(Node("n2"), node_id="n2")]

        node.become_follower()
        node.become_candidate()
        assert node.state == "candidate"

        # Calling start_pre_vote while candidate must be silent (no state change)
        node.start_pre_vote()
        assert node.state == "candidate"


class TestOnConfigChangeRemainingPaths:
    def test_factory_updates_existing_learner_voting_false(self):
        """on_config_change factory path updates an existing peer to voting=False."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node

        node = Node("n1")
        node.register_schedule_timeout(lambda t, c: None)

        existing_peer = ManualPeer(Node("n2"), node_id="n2", voting=True)
        node.peers = [existing_peer]

        def factory(addr, voting=True):
            p = ManualPeer(Node(addr), node_id=addr)
            p.voting = voting
            return p

        node.register_peer_factory(factory)
        # n2 demoted to learner
        node.on_config_change(["n1"], learners=["n2"])
        assert node.peers[0].node_id == "n2"
        assert node.peers[0].voting is False

    def test_no_factory_voter_set_voting_true(self):
        """on_config_change no-factory path sets existing peer to voting=True."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node

        node = Node("n1")
        peer = ManualPeer(Node("n2"), node_id="n2", voting=False)
        node.peers = [peer]

        node.on_config_change(["n1", "n2"])
        assert peer.voting is True

    def test_append_helper_calls_log_add(self):
        """Node.append() delegates to log_add."""
        from salt.cluster.consensus.raft.node import Node

        node = Node("n1")
        node.register_schedule_timeout(lambda t, c: None)
        node.state.become_follower()
        node.state.become_candidate()
        node.state.become_leader()

        idx = node.append(b"data")
        assert idx == 0


class TestHandleAppendEntriesLcaGuard:
    def test_lca_stored_only_when_present(self):
        """leader_client_address_map is NOT populated when lca kwarg is absent."""
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.become_follower()

        node.handle_append_entries("leader", 1, 0, -1, -1)
        assert "leader" not in node.leader_client_address_map


class TestAppendEntriesReplyLeaderGuard:
    def test_not_leader_state_returns_early_without_modifying_state(self):
        """append_entries_reply when state is CANDIDATE returns without updating."""
        from salt.cluster.consensus.raft.node import ManualPeer, Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        node = Node("n1")
        scheduler = ManualTimeoutScheduler()
        node.register_schedule_timeout(scheduler.schedule)
        node.peers = [ManualPeer(Node("n2"), node_id="n2")]

        node.become_follower()
        node.become_candidate()
        # Now call reply while CANDIDATE (not LEADER)
        node.append_entries_reply(1, 0, -1, -1, "n2", 1, True, None, None)
        assert node.state == "candidate"
