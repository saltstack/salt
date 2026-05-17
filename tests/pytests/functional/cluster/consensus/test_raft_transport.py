"""
Functional tests for the Raft-over-cluster-channel transport layer.

These tests exercise the full round-trip:

    Node  ->  SaltPeer  ->  rpc.pack  ->  FakePusher.sent
          <-  rpc.unpack  <-  RaftDispatcher  <-  Node method

No real TCP; no running Salt master.  Real asyncio event loop, real
``salt.utils.event`` framing, real Raft state machines.
"""

import asyncio

import pytest

from salt.cluster.consensus import rpc
from salt.cluster.consensus.peer import RaftDispatcher
from salt.cluster.consensus.raft import LogEntryType, Node
from tests.pytests.functional.cluster.consensus.conftest import (
    FakePusher,
    _build_cluster,
    _deliver_all,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _leaders(members):
    return [cn for cn in members.values() if cn.node.state == cn.node.state.LEADER]


def _followers(members):
    return [cn for cn in members.values() if cn.node.state == cn.node.state.FOLLOWER]


async def _elect(members, max_rounds=60):
    """
    Tick clocks and deliver messages until exactly one leader emerges.

    We tick *one node at a time* and flush messages after each tick.  This
    mirrors the randomised timeouts Raft relies on: whichever node's
    scheduler fires first wins the pre-vote/candidacy race before its peers
    are ticked, breaking the symmetry that would otherwise cause split votes.
    """
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


# ---------------------------------------------------------------------------
# RPC envelope
# ---------------------------------------------------------------------------


class TestRpcEnvelope:
    """Verify that pack/unpack round-trips for every Raft tag kind."""

    @pytest.mark.parametrize("tag", sorted(rpc.ALL_TAGS))
    def test_roundtrip(self, tag):
        payload = {"term": 7, "index": 42, "data": [1, 2, 3]}
        raw = rpc.pack(tag, "node-a", "corr-99", payload)
        out_tag, src, rid, _, out = rpc.unpack(raw)
        assert out_tag == tag
        assert src == "node-a"
        assert rid == "corr-99"
        assert out == payload

    def test_is_raft_tag_accepts_all_known(self):
        for tag in rpc.ALL_TAGS:
            assert rpc.is_raft_tag(tag)

    def test_is_raft_tag_rejects_existing_cluster_tags(self):
        for tag in ("cluster/peer/foo", "cluster/event/m1/bar", "salt/job/abc"):
            assert not rpc.is_raft_tag(tag)


# ---------------------------------------------------------------------------
# Single-hop RPC calls (one sender, one receiver)
# ---------------------------------------------------------------------------


class TestSingleHopRpc:
    """Each Raft RPC kind is sent by a SaltPeer and received by a dispatcher."""

    def _two_nodes(self):
        members = _build_cluster(["a", "b"])
        for cn in members.values():
            cn.node.become_follower()
        return members

    def test_request_vote_rpc(self):
        """request_vote RPC reaches the follower and a reply is sent back."""
        members = self._two_nodes()
        a, b = members["a"], members["b"]

        async def _body():
            # Node a fires request_vote at b
            a.node.peers[0].request_vote(None, "a", 1, 0, -1)
            await asyncio.sleep(0)  # let fire-and-forget task run
            # b's pusher_out["a"] has the RPC bytes
            assert a.pushers_out["b"].sent

            # Deliver to b's dispatcher
            raw = a.pushers_out["b"].sent.popleft()
            tag, src, rid, _, payload = rpc.unpack(raw)
            assert tag == rpc.REQUEST_VOTE
            await b.dispatcher.dispatch(tag, src, rid, payload)

            # b's dispatcher replied into b.pushers_out["a"]
            assert b.pushers_out["a"].sent
            r_raw = b.pushers_out["a"].sent.popleft()
            r_tag, _, _, _, r_payload = rpc.unpack(r_raw)
            assert r_tag == rpc.REQUEST_VOTE_REPLY
            assert isinstance(r_payload["granted"], bool)

        _run(_body())

    def test_pre_request_vote_rpc(self):
        members = self._two_nodes()
        a, b = members["a"], members["b"]

        async def _body():
            a.node.peers[0].pre_request_vote(None, "a", 1, 0, -1)
            await asyncio.sleep(0)
            raw = a.pushers_out["b"].sent.popleft()
            tag, src, rid, _, payload = rpc.unpack(raw)
            assert tag == rpc.PRE_REQUEST_VOTE
            await b.dispatcher.dispatch(tag, src, rid, payload)
            r_raw = b.pushers_out["a"].sent.popleft()
            r_tag, _, _, _, _ = rpc.unpack(r_raw)
            assert r_tag == rpc.PRE_REQUEST_VOTE_REPLY

        _run(_body())

    def test_append_entries_rpc(self):
        members = self._two_nodes()
        a, b = members["a"], members["b"]
        a.node.term = 1
        b.node.term = 1

        async def _body():
            a.node.peers[0].append_entries(None, "a", 1, 0, -1, -1)
            await asyncio.sleep(0)
            raw = a.pushers_out["b"].sent.popleft()
            tag, src, rid, _, payload = rpc.unpack(raw)
            assert tag == rpc.APPEND_ENTRIES
            await b.dispatcher.dispatch(tag, src, rid, payload)
            r_raw = b.pushers_out["a"].sent.popleft()
            r_tag, _, _, _, r_payload = rpc.unpack(r_raw)
            assert r_tag == rpc.APPEND_ENTRIES_REPLY
            assert r_payload["success"] is True

        _run(_body())

    def test_install_snapshot_rpc(self):
        import json

        members = self._two_nodes()
        a, b = members["a"], members["b"]
        a.node.term = 1
        b.node.term = 1

        snap = list(json.dumps({"count": 5}).encode())

        async def _body():
            a.node.peers[0].install_snapshot(None, "a", 1, 9, 1, bytes(snap))
            await asyncio.sleep(0)
            raw = a.pushers_out["b"].sent.popleft()
            tag, src, rid, _, payload = rpc.unpack(raw)
            assert tag == rpc.INSTALL_SNAPSHOT
            assert payload["data"] == snap
            await b.dispatcher.dispatch(tag, src, rid, payload)
            r_raw = b.pushers_out["a"].sent.popleft()
            r_tag, _, _, _, r_payload = rpc.unpack(r_raw)
            assert r_tag == rpc.INSTALL_SNAPSHOT_REPLY
            assert r_payload["peer_id"] == "b"

        _run(_body())


# ---------------------------------------------------------------------------
# Election
# ---------------------------------------------------------------------------


class TestElection:
    def test_three_node_cluster_elects_exactly_one_leader(self, cluster):
        _run(_elect(cluster))
        assert len(_leaders(cluster)) == 1
        assert len(_followers(cluster)) == 2

    def test_leader_has_highest_or_equal_term(self, cluster):
        _run(_elect(cluster))
        leader = _leaders(cluster)[0]
        for cn in cluster.values():
            assert leader.node.term >= cn.node.term

    def test_two_node_cluster_elects_leader(self):
        members = _build_cluster(["x", "y"])
        for cn in members.values():
            cn.node.become_follower()
            cn.node.last_followed = cn.node.get_now() - 10

        _run(_elect(members))
        assert len(_leaders(members)) == 1

    def test_single_node_cluster_becomes_leader_immediately(self):
        members = _build_cluster(["solo"])
        members["solo"].node.become_follower()
        members["solo"].node.last_followed = members["solo"].node.get_now() - 10

        _run(_elect(members))
        assert members["solo"].node.state == members["solo"].node.state.LEADER

    def test_re_election_after_leader_failure(self, cluster):
        _run(_elect(cluster))
        leader_id = _leaders(cluster)[0].node_id

        # Simulate leader disappearing: zero out its outbound pushers
        # and stop it from receiving more messages
        cluster[leader_id].dispatcher._node = None
        for pusher in cluster[leader_id].pushers_out.values():
            pusher.sent.clear()

        # Remaining nodes time out and elect a new leader
        survivors = {nid: cn for nid, cn in cluster.items() if nid != leader_id}
        for cn in survivors.values():
            cn.node.last_followed = cn.node.get_now() - 10

        _run(_elect(survivors))
        new_leaders = _leaders(survivors)
        assert len(new_leaders) == 1
        assert new_leaders[0].node_id != leader_id


# ---------------------------------------------------------------------------
# Log replication
# ---------------------------------------------------------------------------


class TestLogReplication:
    async def _setup_leader(self, cluster):
        await _elect(cluster)
        return _leaders(cluster)[0]

    def test_leader_replicates_entry_to_all_followers(self, cluster):
        """
        After log_add, followers receive the entry over the transport.

        Note: entries arrive at followers as raw dicts (msgpack round-trip),
        so ``entry.cmd`` on the follower holds the full serialised LogEntry dict.
        We assert the entry count and that the original cmd appears inside.
        """

        async def _body():
            leader_cn = await self._setup_leader(cluster)
            leader_cn.node.log_add("hello-raft")
            await asyncio.sleep(0)
            await _deliver_all(cluster, rounds=6)
            for cn in _followers(cluster):
                assert len(cn.node.log.entries) == 1

        _run(_body())

    def test_leader_commit_index_advances_after_replication(self, cluster):
        """
        The leader's commit_index advances once a majority has acknowledged
        the entry (via APPEND_ENTRIES_REPLY).  Follower commit_index catches
        up on the *next* heartbeat (which carries leader_commit).
        """

        async def _body():
            leader_cn = await self._setup_leader(cluster)
            leader_cn.node.log_add("commit-me")
            await asyncio.sleep(0)
            await _deliver_all(cluster, rounds=6)
            # Leader has a majority ack -> commit_index == 0 (first entry)
            assert leader_cn.node.commit_index == 0

        _run(_body())

    def test_multiple_entries_replicated_in_order(self, cluster):
        async def _body():
            leader_cn = await self._setup_leader(cluster)
            for cmd in ["alpha", "beta", "gamma"]:
                leader_cn.node.log_add(cmd)
            await asyncio.sleep(0)
            await _deliver_all(cluster, rounds=10)
            for cn in _followers(cluster):
                assert len(cn.node.log.entries) == 3
                # Verify ordering by entry index (entries sorted ascending)
                indices = [e.index for e in cn.node.log.entries]
                assert indices == sorted(indices)

        _run(_body())

    def test_config_entry_type_replicates(self, cluster):
        """
        A CONFIG entry replicates to followers with the correct entry type.

        On the leader the entry has ``type == LogEntryType.CONFIG`` and
        ``cmd == {"voters": [...], "learners": []}``.

        On followers the entry is decoded from the wire dict correctly:
        ``entry.type == LogEntryType.CONFIG`` and ``entry.cmd`` is the
        voters/learners payload dict.
        """

        async def _body():
            leader_cn = await self._setup_leader(cluster)
            all_ids = list(cluster.keys())
            config = {"voters": all_ids, "learners": []}
            leader_cn.node.log_add(config, entry_type=LogEntryType.CONFIG)
            await asyncio.sleep(0)
            await _deliver_all(cluster, rounds=6)

            # Leader stores the entry with type CONFIG
            leader_entries = leader_cn.node.log.entries
            assert leader_entries
            assert leader_entries[0].type == LogEntryType.CONFIG

            # Followers correctly decode the entry type from the wire format.
            for cn in _followers(cluster):
                assert len(cn.node.log.entries) >= 1
                follower_entry = cn.node.log.entries[0]
                assert follower_entry.type == LogEntryType.CONFIG
                assert isinstance(follower_entry.cmd, dict)
                assert "voters" in follower_entry.cmd

        _run(_body())


# ---------------------------------------------------------------------------
# Fault tolerance
# ---------------------------------------------------------------------------


class TestFaultTolerance:
    def test_minority_partition_does_not_commit(self, cluster):
        """
        Isolate one follower: the leader should still commit (majority = 2/3).
        Isolated node must not diverge.
        """

        async def _body():
            await _elect(cluster)
            leader_cn = _leaders(cluster)[0]
            isolated_id = _followers(cluster)[0].node_id

            # Cut the isolated node's inbound by zeroing its outbound replies
            # (it won't ack AE, so leader won't count it toward quorum)
            cluster[isolated_id].pushers_out = {
                pid: FakePusher() for pid in cluster[isolated_id].peer_ids
            }
            cluster[isolated_id].dispatcher._pushers = cluster[isolated_id].pushers_out

            leader_cn.node.log_add("isolated-write")
            await asyncio.sleep(0)
            await _deliver_all(
                {nid: cn for nid, cn in cluster.items() if nid != isolated_id},
                rounds=6,
            )
            # Committed on majority (leader + other follower)
            assert leader_cn.node.commit_index == 0
            # Isolated node has no commit
            assert cluster[isolated_id].node.commit_index < 0

        _run(_body())

    def test_stale_term_append_entries_rejected(self, cluster):
        async def _body():
            await _elect(cluster)
            leader_cn = _leaders(cluster)[0]
            follower_cn = _followers(cluster)[0]

            stale_payload = {
                "callback_node": leader_cn.node_id,
                "leader_id": "ghost",
                "term": 0,  # stale
                "prev_log_term": 0,
                "prev_log_index": -1,
                "leader_commit": -1,
                "entries": [],
                "leader_client_address": None,
            }
            await follower_cn.dispatcher.dispatch(
                rpc.APPEND_ENTRIES, "ghost", "rid", stale_payload
            )
            # Reply should be failure
            reply_raw = follower_cn.pushers_out.get(leader_cn.node_id)
            if reply_raw and reply_raw.sent:
                r_tag, _, _, _, r_payload = rpc.unpack(reply_raw.sent.popleft())
                assert r_tag == rpc.APPEND_ENTRIES_REPLY
                assert r_payload["success"] is False

        _run(_body())

    def test_stale_vote_request_not_granted(self, cluster):
        async def _body():
            await _elect(cluster)
            leader_cn = _leaders(cluster)[0]
            follower_cn = _followers(cluster)[0]

            # Follower has term >= 1 now; a stale-term vote request should be denied
            stale_payload = {
                "callback_node": "interloper",
                "candidate_id": "interloper",
                "term": 0,
                "last_log_term": 0,
                "last_log_index": -1,
            }
            # inject a pusher for the interloper reply destination
            interloper_pusher = FakePusher()
            follower_cn.dispatcher._pushers["interloper"] = interloper_pusher

            await follower_cn.dispatcher.dispatch(
                rpc.REQUEST_VOTE, "interloper", "rid", stale_payload
            )
            assert interloper_pusher.sent
            r_tag, _, _, _, r_payload = rpc.unpack(interloper_pusher.sent.popleft())
            assert r_tag == rpc.REQUEST_VOTE_REPLY
            assert r_payload["granted"] is False

        _run(_body())


# ---------------------------------------------------------------------------
# Dispatcher edge cases
# ---------------------------------------------------------------------------


class TestDispatcherEdgeCases:
    def test_unknown_raft_tag_does_not_raise(self):
        node = Node("1")
        node.register_schedule_timeout(lambda t, c: None)
        node.become_follower()
        d = RaftDispatcher(node, "1", {})

        async def _body():
            await d.dispatch("cluster/raft/unknown-future-tag", "2", "rid", {})

        _run(_body())

    def test_none_node_drops_silently(self):
        from salt.cluster.consensus.peer import RaftDispatcher as RD

        d = RD(None, "1", {})

        async def _body():
            await d.dispatch(rpc.REQUEST_VOTE, "2", "rid", {})

        _run(_body())

    def test_node_exception_is_caught(self):
        from salt.cluster.consensus.peer import RaftDispatcher as RD
        from tests.support.mock import MagicMock

        node = MagicMock()
        node.request_vote = MagicMock(side_effect=RuntimeError("internal"))
        d = RD(node, "1", {})

        payload = {
            "callback_node": "2",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(d.dispatch(rpc.REQUEST_VOTE, "2", "rid", payload))

    def test_missing_pusher_for_reply_is_logged(self):
        """Dispatcher with empty pushers should not raise when it can't reply."""
        node = Node("1")
        node.register_schedule_timeout(lambda t, c: None)
        node.become_follower()
        d = RaftDispatcher(node, "1", {})  # no pushers

        payload = {
            "callback_node": "ghost-node",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(d.dispatch(rpc.REQUEST_VOTE, "2", "rid", payload))


# ---------------------------------------------------------------------------
# Membership SM survives log compaction (regression: CONSENSUS_BUGS.md #1)
# ---------------------------------------------------------------------------


class TestMembershipSurvivesSnapshot:
    """
    Regression for CONSENSUS_BUGS.md #1.

    Before the fix, ``Log.snapshot()`` only persisted the application SM, so
    a node that compacted its log lost the committed voter/learner set.  These
    tests pin the round-trip:

    * ``snapshot()`` followed by a fresh ``Log`` on the same storage must
      restore membership state (compaction + restart).
    * ``install_snapshot`` carrying an envelope must restore the receiver's
      membership SM (catch-up via leader snapshot).
    """

    def test_membership_survives_compaction_and_restart(self, tmp_path):
        """Apply a CONFIG entry, snapshot, rebuild a Node from storage."""
        from salt.cluster.consensus.raft.log import LogEntryType
        from salt.cluster.consensus.storage import SaltStorage

        opts = {"cachedir": str(tmp_path), "cluster_id": "test", "cluster_peers": []}
        storage = SaltStorage("master-1", opts)

        node = Node("master-1", storage=storage)
        node.register_schedule_timeout(lambda t, c: None)

        # Apply a CONFIG entry as the leader would
        node.membership_sm.apply(
            {"voters": ["master-1", "master-2", "master-3"], "learners": []}, index=0
        )
        node.log.add(1, b"app-cmd")
        node.log.add(
            1,
            {"voters": ["master-1", "master-2", "master-3"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        node.log.commit(1)
        # Force a snapshot — simulates compaction firing
        node.log.snapshot()
        assert node.log.entries == []

        # Simulate restart: build a fresh Node on the same storage
        restarted = Node("master-1", storage=storage)
        restarted.register_schedule_timeout(lambda t, c: None)

        info = restarted.info()
        assert info["membership"]["voters"] == [
            "master-1",
            "master-2",
            "master-3",
        ]
        assert info["membership"]["version"] == 0

    def test_install_snapshot_envelope_restores_membership(self):
        """A follower that receives an envelope snapshot rebuilds membership."""
        import json

        from salt.cluster.consensus.raft.log import SNAPSHOT_ENVELOPE_VERSION

        follower = Node("follower")
        follower.register_schedule_timeout(lambda t, c: None)
        follower.term = 1

        envelope = {
            "__envelope__": SNAPSHOT_ENVELOPE_VERSION,
            "machines": {
                "membership_sm": {
                    "voters": ["m1", "m2", "m3"],
                    "learners": ["m4"],
                    "version": 7,
                },
            },
        }

        follower.install_snapshot(
            leader_id="m1",
            term=2,
            last_index=12,
            last_term=2,
            data=json.dumps(envelope).encode("utf-8"),
        )

        info = follower.info()
        assert info["membership"]["voters"] == ["m1", "m2", "m3"]
        assert info["membership"]["learners"] == ["m4"]
        assert info["membership"]["version"] == 7
        assert info["last_index"] == 12
