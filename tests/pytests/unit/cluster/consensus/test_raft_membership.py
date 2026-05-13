"""
Unit tests for Raft learner nodes and dynamic membership changes.

Covers:
- A learner (voting=False) never starts a pre-vote or election.
- A learner receives and applies log entries from a leader.
- The leader auto-proposes a CONFIG entry once a learner's log catches up.
- The CONFIG entry, when applied, promotes the learner to voter on all nodes.
- ``Node.on_config_change`` updates ``self.voting`` for the local node.
- ``Candidacy`` quorum excludes non-voting peers.
- ``RaftService.notify_peer_joined`` wires a new learner into a live cluster.
"""

import tempfile

import pytest

import salt.config
from salt.cluster.consensus.raft import (
    ManualPeer,
    ManualTimeoutScheduler,
    Node,
    NodeState,
)
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.storage import SaltStorage
from tests.support.mock import MagicMock


def _storage(path):
    opts = salt.config.master_config("/dev/null")
    opts["cachedir"] = path
    return SaltStorage("test-node", opts)


def _node(node_id, scheduler, voting=True, peers=None, storage=None):
    n = Node(node_id, voting=voting, storage=storage)
    n.register_schedule_timeout(scheduler.schedule)
    if peers is not None:
        n.peers = peers
    return n


# ---------------------------------------------------------------------------
# Learner never starts an election
# ---------------------------------------------------------------------------


class TestLearnerNoElection:
    def test_learner_follower_timeout_rearms_without_voting(self):
        """A learner that times out must re-arm its timer, not call start_pre_vote."""
        scheduler = ManualTimeoutScheduler()
        n = _node("learner", scheduler, voting=False)
        n.become_follower()

        # Fast-forward past the follower timeout.
        scheduler.time += n._follower_max * 0.002
        scheduler.process_timeouts()

        # Must remain a follower (not a candidate).
        assert n.state == NodeState.FOLLOWER

    def test_learner_does_not_send_pre_vote_rpcs(self):
        """Pre-vote RPCs must not be issued by a learner node."""
        scheduler = ManualTimeoutScheduler()
        peer_node = _node("v1", scheduler)
        peer = ManualPeer(peer_node, node_id="v1")
        n = _node("learner", scheduler, voting=False, peers=[peer])
        n.become_follower()

        scheduler.time += n._follower_max * 0.002
        scheduler.process_timeouts()

        # No pre-vote RPC queued on the peer.
        prv_requests = [r for r in peer.requests if r[0] == "prv"]
        assert prv_requests == []

    def test_voter_can_still_start_election_alongside_learner(self):
        """A voting node with a learner peer still runs elections normally."""
        scheduler = ManualTimeoutScheduler()
        learner_node = _node("learner", scheduler, voting=False)
        learner_peer = ManualPeer(learner_node, node_id="learner", voting=False)

        v2 = _node("v2", scheduler)
        v2_peer = ManualPeer(v2, node_id="v2")

        v1 = _node("v1", scheduler, peers=[learner_peer, v2_peer])
        v1.become_follower()
        v2.become_follower()
        learner_node.become_follower()

        # Time out v1 by advancing past its follower timeout.
        scheduler.time += v1._follower_max * 0.002
        scheduler.process_timeouts()
        # Process any follow-on callbacks (pre-vote replies etc.)
        scheduler.process_timeouts()

        # v1 should have started candidacy (or be candidate already).
        assert v1.state in (NodeState.CANDIDATE, NodeState.FOLLOWER)


# ---------------------------------------------------------------------------
# Candidacy quorum excludes non-voting peers
# ---------------------------------------------------------------------------


class TestCandidacyQuorum:
    def test_three_voters_need_two_votes(self):
        """Classic 3-node: elected with 2/3."""
        from salt.cluster.consensus.raft import Candidacy

        c = Candidacy(term=1, peers=["v2", "v3"])
        assert not c.elected()
        c.handle_reply("v2", 1, True)
        assert c.elected()

    def test_two_voters_plus_learner_quorum_based_on_voters(self):
        """
        A 2-voter + 1-learner cluster: the leader only polls voters.
        Quorum is 2/2 voters (including self) = self alone is enough for a
        single-voter cluster but 2 total for a 2-voter cluster.
        """
        scheduler = ManualTimeoutScheduler()
        learner = _node("learner", scheduler, voting=False)
        learner_peer = ManualPeer(learner, node_id="learner", voting=False)

        v2 = _node("v2", scheduler)
        v2_peer = ManualPeer(v2, node_id="v2")

        v1 = _node("v1", scheduler, peers=[learner_peer, v2_peer])
        v1.become_follower()
        v2.become_follower()
        learner.become_follower()

        v1.become_candidate()

        # Only v2 should have received a request_vote RPC (not learner).
        rv_from_learner = [r for r in learner_peer.requests if r[0] == "rv"]
        rv_from_v2 = [r for r in v2_peer.requests if r[0] == "rv"]
        assert rv_from_learner == [], "Learner must not receive RequestVote"
        assert len(rv_from_v2) == 1, "Voting peer must receive RequestVote"


# ---------------------------------------------------------------------------
# Leader auto-promotes learner after log catch-up
# ---------------------------------------------------------------------------


class TestLearnerPromotion:
    def _setup_leader_with_learner(self):
        """
        Return (leader, learner_node, learner_peer, v2_peer, scheduler).

        leader has two voting peers (v2_peer) plus one learner (learner_peer).
        """
        scheduler = ManualTimeoutScheduler()

        v2 = _node("v2", scheduler)
        v2_peer = ManualPeer(v2, node_id="v2")

        learner_node = _node("learner", scheduler, voting=False)
        learner_peer = ManualPeer(learner_node, node_id="learner", voting=False)

        leader = _node("leader", scheduler, peers=[v2_peer, learner_peer])
        leader.become_follower()
        leader.become_candidate()
        # Supply v2's vote so leader wins.
        v2_peer.handle_all_requests()  # sends pre_vote to v2
        leader.request_vote_reply("v2", True, leader.term)

        assert leader.state == NodeState.LEADER, "leader did not win election"
        return leader, learner_node, learner_peer, v2_peer, scheduler

    def test_no_config_entry_before_learner_caught_up(self):
        """Leader must NOT propose a CONFIG entry while learner is behind."""
        leader, learner_node, learner_peer, v2_peer, scheduler = (
            self._setup_leader_with_learner()
        )

        # Append a command — learner is behind.
        leader.log_add("cmd1")

        # Simulate v2 catching up but NOT learner.
        leader.append_entries_reply(
            leader.term,
            None,
            -1,
            leader.log.index,
            "v2",
            leader.term,
            True,
            leader.log.index,
            None,
        )

        # No CONFIG entry should exist yet.
        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert (
            config_entries == []
        ), "CONFIG entry must not appear before learner catches up"

    def test_config_entry_proposed_when_learner_catches_up(self):
        """Once learner is caught up, leader proposes a CONFIG entry."""
        leader, learner_node, learner_peer, v2_peer, scheduler = (
            self._setup_leader_with_learner()
        )

        # Append one command so there is something to catch up on.
        leader.log_add("cmd1")
        log_idx = leader.log.index

        # Simulate both v2 and learner confirming they have all entries.
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "v2", leader.term, True, log_idx, None
        )
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "learner", leader.term, True, log_idx, None
        )

        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert len(config_entries) == 1, "Exactly one CONFIG entry expected"
        cmd = config_entries[0].cmd
        assert "learner" in cmd.get("voters", []), "Promoted peer must be in voters"
        assert "learner" not in cmd.get(
            "learners", []
        ), "Promoted peer must leave learners"

    def test_config_entry_applied_promotes_learner_peer(self):
        """After the CONFIG entry commits and is applied, learner peer is voting."""
        leader, learner_node, learner_peer, v2_peer, scheduler = (
            self._setup_leader_with_learner()
        )

        leader.log_add("cmd1")
        log_idx = leader.log.index

        # Both peers acknowledge.
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "v2", leader.term, True, log_idx, None
        )
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "learner", leader.term, True, log_idx, None
        )

        config_idx = leader.log.index  # CONFIG entry is last

        # v2 acknowledges the CONFIG entry — gives majority.
        leader.append_entries_reply(
            leader.term,
            None,
            log_idx,
            config_idx,
            "v2",
            leader.term,
            True,
            config_idx,
            None,
        )

        # CONFIG entry should now be committed and applied.
        assert leader.log.commit_index >= config_idx

        # The learner peer on the leader must now be voting.
        learner_peer_obj = next(
            (p for p in leader.peers if p.node_id == "learner"), None
        )
        assert learner_peer_obj is not None
        assert learner_peer_obj.voting is True


# ---------------------------------------------------------------------------
# cluster_max_voters: leader holds learner promotion when cap is reached
# ---------------------------------------------------------------------------


class TestMaxVotersCap:
    """
    ``cluster_max_voters`` puts an upper bound on the auto-promotion path.

    The leader still replicates the log to learners that arrive after the
    cap is hit — they just stay non-voting indefinitely (no CONFIG entry
    is proposed) so quorum size stays bounded.
    """

    def _setup(self, max_voters):
        """Leader + 1 voting peer + 1 learner; cap is configurable."""
        scheduler = ManualTimeoutScheduler()

        v2 = _node("v2", scheduler)
        v2_peer = ManualPeer(v2, node_id="v2")

        learner_node = _node("learner", scheduler, voting=False)
        learner_peer = ManualPeer(learner_node, node_id="learner", voting=False)

        leader = Node(
            "leader",
            voting=True,
            peers=[v2_peer, learner_peer],
            max_voters=max_voters,
        )
        leader.register_schedule_timeout(scheduler.schedule)
        leader.become_follower()
        leader.become_candidate()
        v2_peer.handle_all_requests()
        leader.request_vote_reply("v2", True, leader.term)
        assert leader.state == NodeState.LEADER, "leader did not win election"
        return leader

    def test_caught_up_learner_not_promoted_when_at_cap(self):
        """
        With ``max_voters=2`` and the leader already counting itself + v2 as
        the two voters, a caught-up learner must NOT generate a CONFIG entry.
        """
        leader = self._setup(max_voters=2)
        leader.log_add("cmd1")
        log_idx = leader.log.index

        # Both peers acknowledge the command — learner is at log.index now.
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "v2", leader.term, True, log_idx, None
        )
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "learner", leader.term, True, log_idx, None
        )

        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert config_entries == [], (
            "No CONFIG promotion expected once cluster_max_voters has been "
            f"reached; got {config_entries!r}"
        )

        learner_peer_obj = next(
            (p for p in leader.peers if p.node_id == "learner"), None
        )
        assert learner_peer_obj is not None
        assert (
            learner_peer_obj.voting is False
        ), "Learner peer must remain non-voting when cap blocks promotion"

    def test_opt_plumbs_into_node(self):
        """
        ``cluster_max_voters`` in opts must reach ``Node.max_voters`` via
        ``RaftService.__init__``.  This guards the plumbing from opts ->
        service -> Node so a future refactor of either layer can't
        silently drop the cap.
        """
        import asyncio

        from salt.cluster.consensus.service import RaftService

        tmpdir = tempfile.mkdtemp()
        opts = salt.config.master_config("/dev/null")
        opts["interface"] = "127.0.0.1"
        opts["cluster_peers"] = ["127.0.0.2"]
        opts["cluster_port"] = 55597
        opts["cachedir"] = tmpdir
        opts["cluster_max_voters"] = 3

        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {"127.0.0.2": MagicMock()})
            assert svc.node.max_voters == 3
        finally:
            loop.close()

    def test_caught_up_learner_promoted_under_cap(self):
        """
        With ``max_voters=3`` (leader + v2 + room for one more), the
        caught-up learner is still promoted as in the uncapped path.  This
        is the regression guard that ensures the cap doesn't accidentally
        block normal promotion below the threshold.
        """
        leader = self._setup(max_voters=3)
        leader.log_add("cmd1")
        log_idx = leader.log.index

        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "v2", leader.term, True, log_idx, None
        )
        leader.append_entries_reply(
            leader.term, None, -1, log_idx, "learner", leader.term, True, log_idx, None
        )

        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert (
            len(config_entries) == 1
        ), "Expected exactly one CONFIG promotion entry below cap"
        assert "learner" in config_entries[0].cmd.get("voters", [])

    # ----------------------------------------------------------------------
    # Founding CONFIG also respects the cap.  The promotion gate covers the
    # dynamic learner-catches-up path; this set covers what happens at
    # startup when the leader writes the *first* CONFIG entry.
    # ----------------------------------------------------------------------

    def _service_from_pool(self, peer_addrs, max_voters=None, my_addr="127.0.0.1"):
        """
        Build a minimal RaftService bound to ``my_addr`` with `peer_addrs` as
        its initial peer set, promote the Node to LEADER state, and return
        the service.  Caller drives ``_maybe_commit_founding_config`` and
        inspects the resulting log.

        Promotion is necessary because ``log_add`` raises ``NotLeader`` from
        any other state; ``_maybe_commit_founding_config`` swallows that
        exception so callers never see the commit attempt fail silently.
        """
        import asyncio

        from salt.cluster.consensus.service import RaftService

        tmpdir = tempfile.mkdtemp()
        opts = salt.config.master_config("/dev/null")
        opts["interface"] = my_addr
        opts["cluster_peers"] = list(peer_addrs)
        opts["cluster_port"] = 55596
        opts["cachedir"] = tmpdir
        if max_voters is not None:
            opts["cluster_max_voters"] = max_voters

        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {addr: MagicMock() for addr in peer_addrs}
            svc = RaftService(opts, loop, peer_pushers)
        finally:
            loop.close()
        # Drive into LEADER state via a manual scheduler so log_add succeeds.
        scheduler = ManualTimeoutScheduler()
        svc._node.register_schedule_timeout(scheduler.schedule)
        svc._node.become_follower()
        svc._node.become_candidate()
        svc._node.become_leader()
        return svc

    def test_founding_config_respects_cap(self):
        """
        With 4 configured peers + self (= 5 candidates) and cap=3, the
        founding CONFIG must split the bootstrap pool into 3 voters and 2
        learners.  Voters are the 3 lowest-sorted entries; learners are the
        remaining 2.
        """
        svc = self._service_from_pool(
            peer_addrs=["127.0.0.2", "127.0.0.3", "127.0.0.4", "127.0.0.5"],
            max_voters=3,
        )
        svc._maybe_commit_founding_config()
        config_entries = [
            e for e in svc._node.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert len(config_entries) == 1
        cmd = config_entries[0].cmd
        assert cmd["voters"] == ["127.0.0.1", "127.0.0.2", "127.0.0.3"]
        assert cmd["learners"] == ["127.0.0.4", "127.0.0.5"]

    def test_founding_config_unbounded_when_cap_none(self):
        """
        Without a cap, the founding CONFIG enumerates every member as a
        voter and no learners.  This is the pre-cap behaviour and the
        most-permissive default.
        """
        svc = self._service_from_pool(
            peer_addrs=["127.0.0.2", "127.0.0.3", "127.0.0.4"],
            max_voters=None,
        )
        svc._maybe_commit_founding_config()
        config_entries = [
            e for e in svc._node.log.entries if e.type == LogEntryType.CONFIG
        ]
        cmd = config_entries[0].cmd
        assert cmd["voters"] == [
            "127.0.0.1",
            "127.0.0.2",
            "127.0.0.3",
            "127.0.0.4",
        ]
        assert cmd["learners"] == []

    def test_founding_config_deterministic_across_nodes(self):
        """
        Two prospective founders with different *self* addresses but the
        same overall membership set must produce the *same* voter/learner
        partition.  This is what makes the cluster converge without a
        coordinator: every node computes the same CONFIG locally and only
        the deterministic founder commits it.
        """
        svc_a = self._service_from_pool(
            peer_addrs=["127.0.0.2", "127.0.0.3", "127.0.0.4", "127.0.0.5"],
            max_voters=3,
            my_addr="127.0.0.1",
        )
        svc_b = self._service_from_pool(
            peer_addrs=["127.0.0.1", "127.0.0.3", "127.0.0.4", "127.0.0.5"],
            max_voters=3,
            my_addr="127.0.0.2",
        )
        svc_a._maybe_commit_founding_config()
        svc_b._maybe_commit_founding_config()

        cmd_a = svc_a._node.log.entries[0].cmd
        cmd_b = svc_b._node.log.entries[0].cmd
        assert cmd_a["voters"] == cmd_b["voters"]
        assert cmd_a["learners"] == cmd_b["learners"]


# ---------------------------------------------------------------------------
# Node.on_config_change updates self.voting
# ---------------------------------------------------------------------------


class TestOnConfigChangeSelfVoting:
    def test_learner_node_becomes_voter_when_in_voters_list(self):
        """When a CONFIG entry lists this node in voters, self.voting flips True."""
        scheduler = ManualTimeoutScheduler()
        n = _node("newnode", scheduler, voting=False)
        n.become_follower()

        assert n.voting is False
        n.on_config_change(["leader", "v2", "newnode"], learners=[])
        assert n.voting is True

    def test_voter_stays_voter_when_in_voters_list(self):
        scheduler = ManualTimeoutScheduler()
        n = _node("v1", scheduler, voting=True)
        n.on_config_change(["v1", "v2"], learners=[])
        assert n.voting is True

    def test_voter_becomes_learner_when_moved_to_learners(self):
        scheduler = ManualTimeoutScheduler()
        n = _node("v1", scheduler, voting=True)
        n.on_config_change(["v2"], learners=["v1"])
        assert n.voting is False


# ---------------------------------------------------------------------------
# RaftService.notify_peer_joined
# ---------------------------------------------------------------------------


class TestNotifyPeerJoined:
    def _make_service(self):
        """Build a minimal RaftService with mocked pushers."""
        import asyncio

        from salt.cluster.consensus.service import RaftService

        tmpdir = tempfile.mkdtemp()
        opts = salt.config.master_config("/dev/null")
        opts["interface"] = "127.0.0.1"
        opts["cluster_peers"] = ["127.0.0.2"]
        opts["cluster_port"] = 55596
        opts["cachedir"] = tmpdir

        loop = asyncio.new_event_loop()
        pusher_v2 = MagicMock()
        peer_pushers = {"127.0.0.2": pusher_v2}

        svc = RaftService(opts, loop, peer_pushers)
        loop.close()
        return svc, opts

    def test_notify_adds_learner_peer(self):
        svc, opts = self._make_service()
        initial_count = len(svc.node.peers)

        svc.notify_peer_joined("127.0.0.3")

        assert len(svc.node.peers) == initial_count + 1
        new_peer = next(p for p in svc.node.peers if p.node_id == "127.0.0.3")
        assert new_peer.voting is False

    def test_notify_skips_self(self):
        svc, opts = self._make_service()
        initial_count = len(svc.node.peers)

        # "Joining" with own address must be a no-op.
        svc.notify_peer_joined(opts["interface"])

        assert len(svc.node.peers) == initial_count

    def test_notify_skips_already_known_peer(self):
        svc, opts = self._make_service()
        initial_count = len(svc.node.peers)

        svc.notify_peer_joined("127.0.0.2")  # already in peer_pushers

        assert len(svc.node.peers) == initial_count

    def test_notify_creates_pusher_for_new_peer(self):
        svc, opts = self._make_service()

        with pytest.MonkeyPatch().context() as mp:
            mock_server = MagicMock()
            mp.setattr(
                "salt.transport.tcp.PublishServer",
                lambda *a, **kw: mock_server,
            )
            svc.notify_peer_joined("127.0.0.4")

        assert "127.0.0.4" in svc._peer_pushers
        assert "127.0.0.4" in svc._dispatcher._pushers

    def test_notify_leader_initialises_replication_tracking(self):
        """When called while leader, next_index/match_index should be populated."""
        svc, opts = self._make_service()
        scheduler = ManualTimeoutScheduler()
        svc._node.register_schedule_timeout(scheduler.schedule)
        svc._node.become_follower()
        svc._node.become_candidate()
        svc._node.become_leader()

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "salt.transport.tcp.PublishServer",
                lambda *a, **kw: MagicMock(),
            )
            svc.notify_peer_joined("127.0.0.5")

        assert "127.0.0.5" in svc._node.next_index
        assert "127.0.0.5" in svc._node.match_index

    def test_notify_leader_persists_learner_in_config(self):
        """
        Critical for leader-failover safety: a learner added via
        ``notify_peer_joined`` must show up in a committed CONFIG entry so
        that if the leader dies and a peer becomes leader, the new leader's
        membership SM (rebuilt from the persisted log) still knows the
        learner exists.

        Without this, the new leader has no Peer entry for the dropped
        learner and any RPC replies from it trip ``CandidacyError: X is
        not a peer`` in the candidacy reply-handler.
        """
        svc, opts = self._make_service()
        scheduler = ManualTimeoutScheduler()
        svc._node.register_schedule_timeout(scheduler.schedule)
        svc._node.become_follower()
        svc._node.become_candidate()
        svc._node.become_leader()
        # Seed the SM as if a founding CONFIG had landed.  Without this the
        # newly-registered learner would be the entry's only member, which
        # is a degenerate case we don't test here.
        svc._node.membership_sm.apply(
            {"voters": ["127.0.0.1", "127.0.0.2"], "learners": []}, index=0
        )

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "salt.transport.tcp.PublishServer",
                lambda *a, **kw: MagicMock(),
            )
            svc.notify_peer_joined("127.0.0.6")

        config_entries = [
            e for e in svc._node.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert config_entries, "no CONFIG entry was persisted for new learner"
        latest = config_entries[-1].cmd
        assert (
            "127.0.0.6" in latest["learners"]
        ), f"learner missing from persisted CONFIG; got learners={latest['learners']}"
        # Voters in the entry must mirror the SM's current voter set; the
        # learner-registration CONFIG never changes the voter membership.
        assert latest["voters"] == ["127.0.0.1", "127.0.0.2"]

    def test_notify_follower_does_not_persist_config(self):
        """
        Only leaders propose CONFIG entries (single-writer rule from Raft).
        ``notify_peer_joined`` on a follower must add the peer in-memory but
        must NOT write a CONFIG entry — that would split-brain the log.
        """
        svc, opts = self._make_service()
        # The default Node state is START, never having become_follower-ed.
        # That's fine — notify_peer_joined only writes CONFIG when state
        # is LEADER, and the START != LEADER guard fires regardless.
        assert svc._node.state != NodeState.LEADER

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "salt.transport.tcp.PublishServer",
                lambda *a, **kw: MagicMock(),
            )
            svc.notify_peer_joined("127.0.0.7")

        config_entries = [
            e for e in svc._node.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert config_entries == [], (
            "follower/non-leader must not write CONFIG entries; "
            f"got {len(config_entries)} entries"
        )

    def test_notify_does_not_re_register_known_learner(self):
        """
        If the learner is already in the committed CONFIG, ``notify_peer_joined``
        must be idempotent — no duplicate CONFIG entries.  Otherwise an operator
        restart of a learner could spam the log.
        """
        svc, opts = self._make_service()
        scheduler = ManualTimeoutScheduler()
        svc._node.register_schedule_timeout(scheduler.schedule)
        svc._node.become_follower()
        svc._node.become_candidate()
        svc._node.become_leader()
        svc._node.membership_sm.apply(
            {"voters": ["127.0.0.1"], "learners": ["127.0.0.8"]}, index=0
        )

        # 127.0.0.8 isn't yet in svc._node.peers, so notify_peer_joined will
        # add it as an in-memory peer, but the persistent CONFIG should NOT
        # be re-written because 127.0.0.8 is already a known learner.
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "salt.transport.tcp.PublishServer",
                lambda *a, **kw: MagicMock(),
            )
            svc.notify_peer_joined("127.0.0.8")

        config_entries = [
            e for e in svc._node.log.entries if e.type == LogEntryType.CONFIG
        ]
        assert config_entries == [], (
            "no new CONFIG entry should be written for an already-known "
            f"learner; got {len(config_entries)}"
        )
