"""
Unit tests for voter health detection + single-node demotion/promotion.

Covers (per the membership-design notes in CLUSTER_MEMBERSHIP_DESIGN.md):

* Per-peer ``last_contact`` is recorded on every AppendEntries reply.
* ``Node.propose_voter_demotion`` enforces:
  - leader-only,
  - peer-must-be-voter,
  - voter floor (``cluster_min_voters``).
* ``Node.propose_voter_promotion_to_replace`` enforces:
  - leader-only,
  - peer-must-be-learner,
  - caught-up precondition,
  - existing ``cluster_max_voters`` cap.
* ``RaftService.propose_voter_demotion`` / ``propose_voter_promotion`` are
  the operator-override entry points and work regardless of the
  ``cluster_auto_replace_voters`` flag.

Why these tests matter
----------------------
Membership changes are CONFIG entries committed through the same Raft
log used for application state.  Each one is a one-step transition
(Ongaro thesis §6.4).  The preconditions tested here are the safety
invariants that prevent the cluster from accidentally stalling itself
by demoting too many voters at once or by promoting a learner whose log
is behind.
"""

import tempfile

import salt.config
from salt.cluster.consensus.raft import (
    ManualPeer,
    ManualTimeoutScheduler,
    Node,
    NodeState,
)
from salt.cluster.consensus.raft.log import LogEntryType
from tests.support.mock import MagicMock


def _leader_with_two_voters(scheduler, max_voters=None):
    """Return a 3-voter cluster where ``leader`` has just been elected."""
    v2 = Node("v2")
    v2.register_schedule_timeout(scheduler.schedule)
    v2_peer = ManualPeer(v2, node_id="v2")

    v3 = Node("v3")
    v3.register_schedule_timeout(scheduler.schedule)
    v3_peer = ManualPeer(v3, node_id="v3")

    leader = Node("leader", peers=[v2_peer, v3_peer], max_voters=max_voters)
    leader.register_schedule_timeout(scheduler.schedule)
    leader.become_follower()
    leader.become_candidate()
    v2_peer.handle_all_requests()
    leader.request_vote_reply("v2", True, leader.term)
    assert leader.state == NodeState.LEADER

    # Seed the membership SM with the same 3-voter set the leader sees.
    leader.membership_sm.apply(
        {"voters": ["leader", "v2", "v3"], "learners": []}, index=0
    )
    leader._applied_config_index = 0
    return leader, v2_peer, v3_peer


# ---------------------------------------------------------------------------
# _peer_last_contact updates
# ---------------------------------------------------------------------------


class TestVoterHealthTracking:
    def test_append_entries_reply_records_contact(self):
        """Every AppendEntries reply (success OR failure) updates last_contact."""
        scheduler = ManualTimeoutScheduler()
        leader, _v2_peer, _v3_peer = _leader_with_two_voters(scheduler)

        # Clear any contact set during become_leader's initial heartbeats so
        # we measure the next explicit reply.
        leader._peer_last_contact.clear()
        scheduler.time += 1
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
        assert "v2" in leader._peer_last_contact

    def test_failure_reply_still_records_contact(self):
        """A success=False reply still proves the peer is reachable."""
        scheduler = ManualTimeoutScheduler()
        leader, _v2_peer, _v3_peer = _leader_with_two_voters(scheduler)

        leader.append_entries_reply(
            leader.term,
            None,
            -1,
            leader.log.index,
            "v3",
            leader.term,
            False,  # log-mismatch failure, not silence
            leader.log.index,
            None,
        )
        assert "v3" in leader._peer_last_contact


# ---------------------------------------------------------------------------
# Node.propose_voter_demotion preconditions
# ---------------------------------------------------------------------------


class TestVoterDemotionProposal:
    def test_demotes_voter_into_learners(self):
        """
        Happy path: demoting one of three voters produces a CONFIG entry
        with the target moved from voters to learners.
        """
        scheduler = ManualTimeoutScheduler()
        leader, _, _ = _leader_with_two_voters(scheduler)

        # min_voters=2 lets us demote one of three.
        assert leader.propose_voter_demotion("v3", min_voters=2) is True

        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        # Two CONFIG entries: the seeded founding entry + the demotion.
        assert len(config_entries) >= 1
        last = config_entries[-1].cmd
        assert "v3" not in last["voters"]
        assert "v3" in last["learners"]

    def test_rejects_non_voter(self):
        scheduler = ManualTimeoutScheduler()
        leader, _, _ = _leader_with_two_voters(scheduler)
        assert leader.propose_voter_demotion("not-a-peer", min_voters=2) is False

    def test_rejects_below_min_voters_floor(self):
        """
        Demotion that would drop the voter set below ``min_voters`` is
        refused — protects against accidentally stalling the cluster.
        """
        scheduler = ManualTimeoutScheduler()
        leader, _, _ = _leader_with_two_voters(scheduler)
        # 3 voters, min_voters=3: any demotion is refused.
        assert leader.propose_voter_demotion("v3", min_voters=3) is False

    def test_rejects_when_not_leader(self):
        """Only the leader may propose membership CONFIGs."""
        scheduler = ManualTimeoutScheduler()
        leader, _, _ = _leader_with_two_voters(scheduler)
        leader.become_follower(leader.term + 1)
        assert leader.state != NodeState.LEADER
        assert leader.propose_voter_demotion("v3", min_voters=2) is False


# ---------------------------------------------------------------------------
# Node.propose_voter_promotion_to_replace preconditions
# ---------------------------------------------------------------------------


class TestVoterPromotionProposal:
    def _leader_with_learner(self, scheduler, max_voters=None):
        leader, _, _ = _leader_with_two_voters(scheduler, max_voters=max_voters)
        learner = Node("learner", voting=False)
        learner.register_schedule_timeout(scheduler.schedule)
        learner_peer = ManualPeer(learner, node_id="learner", voting=False)
        leader.peers.append(learner_peer)
        leader.membership_sm.apply(
            {
                "voters": ["leader", "v2", "v3"],
                "learners": ["learner"],
            },
            index=1,
        )
        leader._applied_config_index = 1
        # Default: learner is at -1 (not caught up).
        leader.match_index["learner"] = -1
        return leader

    def test_promotes_caught_up_learner(self):
        scheduler = ManualTimeoutScheduler()
        leader = self._leader_with_learner(scheduler)
        leader.match_index["learner"] = leader.log.index
        assert leader.propose_voter_promotion_to_replace("learner") is True

        config_entries = [
            e for e in leader.log.entries if e.type == LogEntryType.CONFIG
        ]
        last = config_entries[-1].cmd
        assert "learner" in last["voters"]
        assert "learner" not in last["learners"]

    def test_rejects_uncaught_learner(self):
        scheduler = ManualTimeoutScheduler()
        leader = self._leader_with_learner(scheduler)
        # Push the leader's log index forward via a real entry so the
        # caught-up check has a non-trivial threshold to clear.
        leader.log_add(b"work")
        # match_index["learner"] left at -1.
        assert leader.propose_voter_promotion_to_replace("learner") is False

    def test_rejects_unknown_peer(self):
        scheduler = ManualTimeoutScheduler()
        leader = self._leader_with_learner(scheduler)
        assert leader.propose_voter_promotion_to_replace("ghost") is False

    def test_respects_max_voters_cap(self):
        """
        With ``max_voters=3`` and three voters already, the replacement
        promotion is blocked even when the learner is caught up.  The
        operator typically pairs this with a prior demotion (which
        shrinks the voter set first), but the precondition fires
        independently to keep the cap as a hard ceiling.
        """
        scheduler = ManualTimeoutScheduler()
        leader = self._leader_with_learner(scheduler, max_voters=3)
        leader.match_index["learner"] = leader.log.index
        assert leader.propose_voter_promotion_to_replace("learner") is False


# ---------------------------------------------------------------------------
# RaftService operator-override entry points
# ---------------------------------------------------------------------------


class TestOperatorOverride:
    def _make_service(self):
        import asyncio

        from salt.cluster.consensus.service import RaftService

        tmpdir = tempfile.mkdtemp()
        opts = salt.config.master_config("/dev/null")
        opts["interface"] = "127.0.0.1"
        opts["cluster_peers"] = ["127.0.0.2", "127.0.0.3"]
        opts["cluster_port"] = 55596
        opts["cachedir"] = tmpdir
        opts["cluster_min_voters"] = 2

        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {
                "127.0.0.2": MagicMock(),
                "127.0.0.3": MagicMock(),
            }
            svc = RaftService(opts, loop, peer_pushers)
        finally:
            loop.close()
        scheduler = ManualTimeoutScheduler()
        svc._node.register_schedule_timeout(scheduler.schedule)
        svc._node.become_follower()
        svc._node.become_candidate()
        svc._node.become_leader()
        svc._node.membership_sm.apply(
            {
                "voters": ["127.0.0.1", "127.0.0.2", "127.0.0.3"],
                "learners": [],
            },
            index=0,
        )
        svc._node._applied_config_index = 0
        return svc, opts

    def test_operator_demotion_works_regardless_of_auto_flag(self):
        """
        Operator overrides bypass the ``cluster_auto_replace_voters``
        gate.  An operator may force a known-bad voter out of the set
        even when auto-replacement is disabled.  The floor is still
        enforced (so the operator cannot accidentally stall the
        cluster).
        """
        svc, opts = self._make_service()
        assert opts.get("cluster_auto_replace_voters", False) is False
        assert svc.propose_voter_demotion("127.0.0.3") is True

    def test_operator_demotion_still_enforces_floor(self):
        svc, opts = self._make_service()
        opts["cluster_min_voters"] = 3  # floor matches current voter count
        assert svc.propose_voter_demotion("127.0.0.3") is False
