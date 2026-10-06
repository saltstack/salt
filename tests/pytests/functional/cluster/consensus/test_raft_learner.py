"""
Functional tests for Raft dynamic membership: learner join and promotion.

Scenario:
  1. Three-node cluster (master-1, master-2, master-3) elect a leader.
  2. A fourth node (learner) is introduced via ``notify_peer_joined`` on each
     existing member (simulating the ``cluster/peer/join-notify`` flow).
  3. The learner starts as non-voting and receives log entries from the leader.
  4. Once the learner's log matches the leader's, the leader proposes a CONFIG
     entry promoting the learner to voter.
  5. After the CONFIG entry commits the learner becomes a full voter.

All this happens in-process with FakePushers; no real TCP or Salt master.
"""

import asyncio

from salt.cluster.consensus.peer import SaltPeer
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.node import NodeState
from tests.pytests.functional.cluster.consensus.conftest import (
    ClusterNode,
    FakePusher,
    _build_cluster,
    _deliver_all,
    _flush_tasks,
)


def _run(coro):
    return asyncio.run(coro)


def _leaders(members):
    return [cn for cn in members.values() if str(cn.node.state) == NodeState.LEADER]


def _followers(members):
    return [cn for cn in members.values() if str(cn.node.state) == NodeState.FOLLOWER]


async def _elect(members, max_rounds=80):
    """Tick one node at a time until exactly one leader emerges."""
    member_list = list(members.values())
    for _ in range(max_rounds):
        for cn in member_list:
            cn.scheduler.advance_clock_to_next_timeout()
            cn.scheduler.process_timeouts()
            await _deliver_all(members, rounds=4)
            if len(_leaders(members)) == 1:
                return
    raise AssertionError(
        f"No leader after {max_rounds} rounds. States: "
        + str({nid: str(cn.node.state) for nid, cn in members.items()})
    )


def _add_learner_to_cluster(members, learner_id):
    """
    Add *learner_id* as a non-voting learner to an existing cluster.

    Mirrors what happens when:
      • The new master's ``RaftService`` starts and adds existing members as
        voting peers (it doesn't know it's a learner yet — the CONFIG entry
        will tell it).
      • Each existing master's ``RaftService.notify_peer_joined`` is called,
        adding the new master as a non-voting learner.

    Returns the updated *members* dict (includes the new learner entry).
    """
    # The learner gets its own ClusterNode with pushers pointing at all members.
    learner_peer_ids = list(members.keys())
    learner_cn = ClusterNode(learner_id, learner_peer_ids)
    # Learner starts as non-voting.
    learner_cn.node.voting = False
    # Learner knows existing members as voting peers.
    learner_peers = [
        SaltPeer(pid, learner_cn.pushers_out[pid], learner_id, voting=True)
        for pid in learner_peer_ids
    ]
    learner_cn.node.peers = learner_peers

    # Each existing member: add learner as a non-voting SaltPeer and wire a
    # pusher back to the learner's dispatcher.
    for nid, cn in members.items():
        pusher_to_learner = FakePusher()
        cn.pushers_out[learner_id] = pusher_to_learner
        cn.dispatcher._pushers[learner_id] = pusher_to_learner

        learner_salt_peer = SaltPeer(learner_id, pusher_to_learner, nid, voting=False)
        cn.node.peers.append(learner_salt_peer)

        # Also wire a pusher from the learner to this existing member back.
        # (learner_cn already has pushers_out[nid] from ClusterNode.__init__)
        # Make sure the existing member's dispatcher knows the learner's pusher.
        # The learner delivers RPCs into the existing dispatcher via members[nid].

    members[learner_id] = learner_cn
    return members


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLearnerJoinAndPromotion:
    def test_learner_does_not_become_leader_before_promotion(self):
        """
        A learner must never win an election while still non-voting.
        """

        async def _run_test():
            ids = ["m1", "m2", "m3"]
            members = _build_cluster(ids)
            for cn in members.values():
                cn.node.become_follower()
                cn.node.last_followed = cn.node.get_now() - 10

            await _elect(members)

            members = _add_learner_to_cluster(members, "learner")
            learner_cn = members["learner"]
            learner_cn.node.become_follower()

            # Tick the learner's clock well past its election timeout.
            learner_cn.scheduler.time += learner_cn.node._follower_max * 0.002
            learner_cn.scheduler.process_timeouts()
            await _flush_tasks()

            assert (
                str(learner_cn.node.state) == NodeState.FOLLOWER
            ), f"Learner must not start election; state={learner_cn.node.state}"

        _run(_run_test())

    def test_leader_sends_append_entries_to_learner(self):
        """
        After the learner is added the leader should replicate to it.
        """

        async def _run_test():
            ids = ["m1", "m2", "m3"]
            members = _build_cluster(ids)
            for cn in members.values():
                cn.node.become_follower()
                cn.node.last_followed = cn.node.get_now() - 10

            await _elect(members)
            leader = _leaders(members)[0]

            members = _add_learner_to_cluster(members, "learner")
            learner_cn = members["learner"]
            learner_cn.node.become_follower()

            # Give leader tracking state for the learner.
            leader.node.next_index["learner"] = leader.node.log.index + 1
            leader.node.match_index["learner"] = -1

            # Commit a command so there is something to replicate.
            leader.node.log_add("hello")

            # Deliver — learner should receive AppendEntries.
            await _deliver_all(members, rounds=12)

            assert (
                learner_cn.node.log.index >= 0
            ), "Learner must have received at least one log entry"

        _run(_run_test())

    def test_learner_promoted_after_log_catches_up(self):
        """
        Once the learner is caught up the leader proposes a CONFIG entry and
        the learner becomes a voter after it commits.
        """

        async def _run_test():
            ids = ["m1", "m2", "m3"]
            members = _build_cluster(ids)
            for cn in members.values():
                cn.node.become_follower()
                cn.node.last_followed = cn.node.get_now() - 10

            await _elect(members)
            leader = _leaders(members)[0]
            non_leaders = [cn for cn in members.values() if cn is not leader]

            members = _add_learner_to_cluster(members, "learner")
            learner_cn = members["learner"]
            learner_cn.node.become_follower()

            # Wire leader tracking.
            leader.node.next_index["learner"] = leader.node.log.index + 1
            leader.node.match_index["learner"] = -1

            # Commit a command.
            leader.node.log_add("membership-test")

            # Deliver generously so AppendEntries reaches the learner and the
            # reply reaches the leader, triggering the CONFIG proposal.
            for _ in range(20):
                await _deliver_all(members, rounds=8)

            config_entries = [
                e for e in leader.node.log.entries if e.type == LogEntryType.CONFIG
            ]
            assert config_entries, "Leader must have proposed a CONFIG entry"

            cmd = config_entries[0].cmd
            voters = cmd.get("voters", []) if isinstance(cmd, dict) else []
            assert "learner" in voters, f"Learner must be in CONFIG voters: {cmd}"

            # Deliver again so the CONFIG entry commits and is applied.
            for _ in range(20):
                for cn in list(members.values()):
                    cn.scheduler.advance_clock_to_next_timeout()
                    cn.scheduler.process_timeouts()
                await _deliver_all(members, rounds=8)

            # After the CONFIG entry commits the learner's own node should flip
            # to voting=True when it applies the entry.
            assert (
                learner_cn.node.voting is True
            ), "Learner must be voting=True after CONFIG entry applied"

        _run(_run_test())

    def test_quorum_excludes_learner_before_promotion(self):
        """
        A 3-voter cluster with a learner must still require only 2 voter acks
        (not 3) to commit an entry while the learner is pending promotion.
        """

        async def _run_test():
            ids = ["m1", "m2", "m3"]
            members = _build_cluster(ids)
            for cn in members.values():
                cn.node.become_follower()
                cn.node.last_followed = cn.node.get_now() - 10

            await _elect(members)
            leader = _leaders(members)[0]

            members = _add_learner_to_cluster(members, "learner")
            learner_cn = members["learner"]
            learner_cn.node.become_follower()

            # Intentionally do NOT let the learner receive anything — simulate
            # a slow/offline learner.
            leader.node.next_index["learner"] = leader.node.log.index + 1
            leader.node.match_index["learner"] = -1

            before_commit = leader.node.log.commit_index

            # Append a command and deliver only among voting members (skip learner).
            leader.node.log_add("quorum-test")
            voting_members = {k: v for k, v in members.items() if k != "learner"}
            await _deliver_all(voting_members, rounds=12)

            # The entry must have committed via 2/3 voter majority.
            assert (
                leader.node.log.commit_index > before_commit
            ), "Entry must commit without waiting for learner ack"

        _run(_run_test())
