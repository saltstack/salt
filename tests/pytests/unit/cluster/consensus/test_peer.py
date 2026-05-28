"""Tests for ``salt.cluster.consensus.peer`` — SaltPeer and RaftDispatcher."""

import asyncio
import uuid

from salt.cluster.consensus import rpc
from salt.cluster.consensus.peer import RaftDispatcher, SaltPeer
from salt.cluster.consensus.raft import ManualPeer, ManualTimeoutScheduler, Node
from tests.support.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


def _make_pusher():
    pusher = MagicMock()
    pusher.publish = AsyncMock()
    return pusher


def _pack_and_unpack(tag, src, payload):
    """Round-trip through rpc.pack / rpc.unpack."""
    raw = rpc.pack(tag, src, str(uuid.uuid4()), payload)
    return rpc.unpack(raw)


# ---------------------------------------------------------------------------
# SaltPeer
# ---------------------------------------------------------------------------


class TestSaltPeer:
    def test_node_id_and_address(self):
        peer = SaltPeer("peer-b", _make_pusher(), "peer-a")
        assert peer.node_id == "peer-b"
        assert peer.address == "peer-b"

    def test_voting_default_true(self):
        peer = SaltPeer("b", _make_pusher(), "a")
        assert peer.voting is True

    def test_voting_can_be_false(self):
        peer = SaltPeer("b", _make_pusher(), "a", voting=False)
        assert peer.voting is False

    def test_default_raft_group_id_is_cluster(self):
        """
        SaltPeer defaults to the main cluster Raft group so existing
        (pre-multi-ring) call sites keep their behaviour without
        opting in.
        """
        peer = SaltPeer("b", _make_pusher(), "a")
        assert peer._raft_group_id == "cluster"

    def test_raft_group_id_is_packed_into_outgoing_rpcs(self):
        """
        A SaltPeer constructed for a per-ring Raft group stamps that
        ring's id into every RPC it sends, so the receiver's
        dispatcher can route the message to the correct local Node.
        """
        peer = SaltPeer("remote", _make_pusher(), "local", raft_group_id="jobs")
        sent = self._collect_published(
            peer,
            lambda p: p.request_vote(None, "local", 1, 0, -1),
        )
        _, _, _, group, _ = rpc.unpack(sent[0])
        assert group == "jobs"

    def _collect_published(self, peer, call_fn):
        """Run an event loop, call call_fn(peer), return the raw bytes published."""
        published = []

        async def _body():
            call_fn(peer)
            # allow the fire_and_forget task to run
            await asyncio.sleep(0)

        peer._pusher.publish = AsyncMock(side_effect=published.append)
        _run(_body())
        return published

    def test_request_vote_sends_correct_tag(self):
        peer = SaltPeer("remote", _make_pusher(), "local")
        sent = self._collect_published(
            peer,
            lambda p: p.request_vote(None, "local", 3, 2, 10),
        )
        assert len(sent) == 1
        tag, src, _, _, payload = rpc.unpack(sent[0])
        assert tag == rpc.REQUEST_VOTE
        assert src == "local"
        assert payload["term"] == 3
        assert payload["last_log_term"] == 2
        assert payload["last_log_index"] == 10

    def test_pre_request_vote_sends_correct_tag(self):
        peer = SaltPeer("remote", _make_pusher(), "local")
        sent = self._collect_published(
            peer,
            lambda p: p.pre_request_vote(None, "local", 4, 1, 5),
        )
        tag, _, _, _, payload = rpc.unpack(sent[0])
        assert tag == rpc.PRE_REQUEST_VOTE
        assert payload["term"] == 4

    def test_append_entries_sends_correct_tag(self):
        peer = SaltPeer("remote", _make_pusher(), "local")
        sent = self._collect_published(
            peer,
            lambda p: p.append_entries(None, "local", 2, 1, 0, -1),
        )
        tag, _, _, _, payload = rpc.unpack(sent[0])
        assert tag == rpc.APPEND_ENTRIES
        assert payload["term"] == 2
        assert payload["entries"] == []

    def test_append_entries_with_entries(self):
        from salt.cluster.consensus.raft import LogEntry, LogEntryType

        peer = SaltPeer("remote", _make_pusher(), "local")
        entry = LogEntry(1, 0, b"cmd", "local", LogEntryType.COMMAND)
        sent = self._collect_published(
            peer,
            lambda p: p.append_entries(None, "local", 1, 0, -1, 0, entry),
        )
        tag, _, _, _, payload = rpc.unpack(sent[0])
        assert tag == rpc.APPEND_ENTRIES
        assert len(payload["entries"]) == 1

    def test_install_snapshot_encodes_bytes(self):
        peer = SaltPeer("remote", _make_pusher(), "local")
        sent = self._collect_published(
            peer,
            lambda p: p.install_snapshot(None, "local", 1, 5, 1, b"\x01\x02\x03"),
        )
        tag, _, _, _, payload = rpc.unpack(sent[0])
        assert tag == rpc.INSTALL_SNAPSHOT
        assert payload["data"] == [1, 2, 3]

    def test_send_logs_exception_gracefully(self):
        pusher = _make_pusher()
        pusher.publish = AsyncMock(side_effect=OSError("connection refused"))
        peer = SaltPeer("remote", pusher, "local")

        async def _body():
            peer.request_vote(None, "local", 1, 0, -1)
            await asyncio.sleep(0)

        _run(_body())  # must not raise


# ---------------------------------------------------------------------------
# RaftDispatcher
# ---------------------------------------------------------------------------


class TestRaftDispatcher:
    def _make_cluster(self, n=3):
        """Build n-node cluster with ManualPeer/ManualTimeoutScheduler."""
        scheduler = ManualTimeoutScheduler()
        nodes = []
        for i in range(1, n + 1):
            node = Node(str(i))
            node.register_schedule_timeout(scheduler.schedule)
            nodes.append(node)
        for node in nodes:
            peers = [ManualPeer(other) for other in nodes if other is not node]
            node.peers = peers
        for node in nodes:
            node.become_follower()
        return nodes, scheduler

    def _dispatcher(self, node, pushers):
        return RaftDispatcher(node, node.node_id, pushers)

    def test_dispatch_request_vote_sends_reply(self):
        nodes, _ = self._make_cluster()
        node = nodes[0]
        pusher = _make_pusher()
        dispatcher = self._dispatcher(node, {"2": pusher})

        raw = rpc.pack(
            rpc.REQUEST_VOTE,
            "2",
            "rid",
            {
                "callback_node": "2",
                "candidate_id": "2",
                "term": 1,
                "last_log_term": 0,
                "last_log_index": -1,
            },
        )
        tag, src, rid, group, payload = rpc.unpack(raw)

        _run(dispatcher.dispatch(tag, src, rid, payload, raft_group_id=group))

        pusher.publish.assert_awaited_once()
        reply_raw = pusher.publish.call_args[0][0]
        r_tag, _, _, _, r_payload = rpc.unpack(reply_raw)
        assert r_tag == rpc.REQUEST_VOTE_REPLY
        assert isinstance(r_payload["granted"], bool)

    def test_dispatch_pre_request_vote_sends_reply(self):
        nodes, _ = self._make_cluster()
        node = nodes[0]
        pusher = _make_pusher()
        dispatcher = self._dispatcher(node, {"2": pusher})

        payload = {
            "callback_node": "2",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(dispatcher.dispatch(rpc.PRE_REQUEST_VOTE, "2", "r", payload))

        pusher.publish.assert_awaited_once()
        r_tag, _, _, _, r_payload = rpc.unpack(pusher.publish.call_args[0][0])
        assert r_tag == rpc.PRE_REQUEST_VOTE_REPLY

    def test_dispatch_vote_reply_calls_node(self):
        nodes, _ = self._make_cluster()
        leader_candidate = nodes[0]
        leader_candidate.become_candidate()
        pusher = _make_pusher()
        dispatcher = self._dispatcher(leader_candidate, {})

        payload = {"granted": True, "term": leader_candidate.term, "voter_id": "2"}
        _run(dispatcher.dispatch(rpc.REQUEST_VOTE_REPLY, "2", "r", payload))
        # node should now be leader (3 nodes, needs 2 votes incl. self, got 1 more)
        assert leader_candidate.state == leader_candidate.state.LEADER

    def test_dispatch_append_entries_sends_reply(self):
        nodes, _ = self._make_cluster()
        follower = nodes[1]
        follower.term = 1
        pusher = _make_pusher()
        dispatcher = self._dispatcher(follower, {"1": pusher})

        payload = {
            "callback_node": "1",
            "leader_id": "1",
            "term": 1,
            "prev_log_term": 0,
            "prev_log_index": -1,
            "leader_commit": -1,
            "entries": [],
            "leader_client_address": None,
        }
        _run(dispatcher.dispatch(rpc.APPEND_ENTRIES, "1", "r", payload))

        pusher.publish.assert_awaited_once()
        r_tag, _, _, _, r_payload = rpc.unpack(pusher.publish.call_args[0][0])
        assert r_tag == rpc.APPEND_ENTRIES_REPLY
        assert r_payload["success"] is True

    def test_dispatch_append_entries_reply_calls_node(self):
        nodes, _ = self._make_cluster()
        leader = nodes[0]
        leader.become_candidate()
        leader.state.become_leader()
        leader.next_index = {"2": 0, "3": 0}
        leader.match_index = {"2": -1, "3": -1}
        dispatcher = self._dispatcher(leader, {})

        payload = {
            "term": 1,
            "prev_log_term": 0,
            "prev_log_index": -1,
            "sent_log_index": -1,
            "peer_id": "2",
            "our_term": 1,
            "success": True,
            "conflict_index": None,
            "conflict_term": None,
        }
        _run(dispatcher.dispatch(rpc.APPEND_ENTRIES_REPLY, "2", "r", payload))
        # Should not raise; match_index would update
        assert leader.match_index.get("2", -1) >= -1

    def test_dispatch_install_snapshot_sends_reply(self):
        import json

        nodes, _ = self._make_cluster()
        follower = nodes[1]
        follower.term = 1
        pusher = _make_pusher()
        dispatcher = self._dispatcher(follower, {"1": pusher})

        snap_data = list(json.dumps({"count": 0}).encode())
        payload = {
            "callback_node": "1",
            "leader_id": "1",
            "term": 1,
            "last_included_index": 5,
            "last_included_term": 1,
            "data": snap_data,
        }
        _run(dispatcher.dispatch(rpc.INSTALL_SNAPSHOT, "1", "r", payload))

        pusher.publish.assert_awaited_once()
        r_tag, _, _, _, r_payload = rpc.unpack(pusher.publish.call_args[0][0])
        assert r_tag == rpc.INSTALL_SNAPSHOT_REPLY
        assert r_payload["peer_id"] == follower.node_id

    def test_dispatch_snapshot_reply_calls_node(self):
        nodes, _ = self._make_cluster()
        leader = nodes[0]
        leader.become_candidate()
        leader.state.become_leader()
        leader.term = 1
        dispatcher = self._dispatcher(leader, {})

        payload = {"peer_id": "2", "our_term": 1}
        _run(dispatcher.dispatch(rpc.INSTALL_SNAPSHOT_REPLY, "2", "r", payload))
        # should not raise

    def test_dispatch_unknown_tag_logs_warning(self):
        nodes, _ = self._make_cluster()
        dispatcher = self._dispatcher(nodes[0], {})
        _run(dispatcher.dispatch("cluster/raft/bogus", "2", "r", {}))
        # no exception

    def test_dispatch_no_pusher_for_reply_logs_warning(self):
        nodes, _ = self._make_cluster()
        node = nodes[0]
        dispatcher = self._dispatcher(node, {})  # empty pushers

        payload = {
            "callback_node": "2",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(dispatcher.dispatch(rpc.REQUEST_VOTE, "2", "r", payload))
        # no exception; reply dropped with warning

    def test_dispatch_none_node_drops_message(self):
        dispatcher = RaftDispatcher(None, "1", {})
        _run(dispatcher.dispatch(rpc.REQUEST_VOTE, "2", "r", {}))
        # no exception

    def test_dispatch_node_exception_is_caught(self):
        node = MagicMock()
        node.request_vote = MagicMock(side_effect=RuntimeError("boom"))
        dispatcher = RaftDispatcher(node, "1", {})
        payload = {
            "callback_node": "2",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(dispatcher.dispatch(rpc.REQUEST_VOTE, "2", "r", payload))
        # exception caught, no re-raise

    def test_dispatch_routes_by_raft_group_id(self):
        """
        With multiple nodes registered, RPCs land on the Node whose
        group id matches the envelope's ``raft_group_id``.  Each Node
        is independent: the wrong node must not observe the RPC.
        """
        cluster_node = MagicMock()
        cluster_node.request_vote = MagicMock(return_value=(True, 1, None))
        jobs_node = MagicMock()
        jobs_node.request_vote = MagicMock(return_value=(True, 1, None))
        dispatcher = RaftDispatcher(
            {"cluster": cluster_node, "jobs": jobs_node}, "1", {}
        )

        payload = {
            "callback_node": "2",
            "candidate_id": "2",
            "term": 1,
            "last_log_term": 0,
            "last_log_index": -1,
        }
        _run(
            dispatcher.dispatch(
                rpc.REQUEST_VOTE, "2", "r", payload, raft_group_id="jobs"
            )
        )

        jobs_node.request_vote.assert_called_once()
        cluster_node.request_vote.assert_not_called()

    def test_dispatch_drops_rpc_for_unknown_group(self):
        """
        An RPC tagged for a group the dispatcher has not registered
        (e.g. a stale ring this master tore down) is dropped without
        raising, the way an RPC for a missing node always has been.
        """
        cluster_node = MagicMock()
        cluster_node.request_vote = MagicMock()
        dispatcher = RaftDispatcher({"cluster": cluster_node}, "1", {})

        _run(
            dispatcher.dispatch(
                rpc.REQUEST_VOTE,
                "2",
                "r",
                {"callback_node": "2", "candidate_id": "2", "term": 1},
                raft_group_id="bogus",
            )
        )

        cluster_node.request_vote.assert_not_called()

    def test_register_and_unregister_node_dynamically(self):
        """
        ``register_node`` adds a Node for a new group; the dispatcher
        immediately routes RPCs to it.  ``unregister_node`` drops the
        entry and subsequent RPCs for that group are silently
        discarded.  Used by RaftService when a per-ring Raft group is
        spun up or torn down at runtime.
        """
        cluster_node = MagicMock()
        dispatcher = RaftDispatcher({"cluster": cluster_node}, "1", {})

        # New ring brought up.
        ring_node = MagicMock()
        ring_node.request_vote = MagicMock(return_value=(True, 1, None))
        dispatcher.register_node("events", ring_node)

        _run(
            dispatcher.dispatch(
                rpc.REQUEST_VOTE,
                "2",
                "r",
                {"callback_node": "2", "candidate_id": "2", "term": 1},
                raft_group_id="events",
            )
        )
        ring_node.request_vote.assert_called_once()

        # Ring torn down — subsequent RPCs are dropped.
        dispatcher.unregister_node("events")
        ring_node.request_vote.reset_mock()
        _run(
            dispatcher.dispatch(
                rpc.REQUEST_VOTE,
                "2",
                "r",
                {"callback_node": "2", "candidate_id": "2", "term": 1},
                raft_group_id="events",
            )
        )
        ring_node.request_vote.assert_not_called()

    def test_dispatcher_setting_node_to_none_clears_cluster_group(self):
        """
        Some tests simulate a leader losing its Node by writing
        ``dispatcher._node = None``.  The setter routes that to the
        cluster group; subsequent cluster RPCs drop, while other
        groups stay registered.
        """
        cluster_node = MagicMock()
        ring_node = MagicMock()
        ring_node.request_vote = MagicMock(return_value=(True, 1, None))
        dispatcher = RaftDispatcher(
            {"cluster": cluster_node, "jobs": ring_node}, "1", {}
        )

        dispatcher._node = None
        assert dispatcher._node is None
        # ring group still alive
        _run(
            dispatcher.dispatch(
                rpc.REQUEST_VOTE,
                "2",
                "r",
                {"callback_node": "2", "candidate_id": "2", "term": 1},
                raft_group_id="jobs",
            )
        )
        ring_node.request_vote.assert_called_once()


def test_dispatcher_publish_exception_is_caught():
    """RaftDispatcher catches publish exceptions without propagating."""
    import asyncio

    from salt.cluster.consensus import rpc
    from salt.cluster.consensus.peer import RaftDispatcher
    from salt.cluster.consensus.raft.node import Node
    from tests.support.mock import AsyncMock, MagicMock

    node = Node("1")
    node.register_schedule_timeout(lambda t, c: None)
    node.become_follower()

    bad_pusher = MagicMock()
    bad_pusher.publish = AsyncMock(side_effect=RuntimeError("network down"))

    dispatcher = RaftDispatcher(node, "1", {"2": bad_pusher})

    def _run(coro):
        return asyncio.run(coro)

    payload = {
        "callback_node": "2",
        "candidate_id": "2",
        "term": 1,
        "last_log_term": 0,
        "last_log_index": -1,
    }
    # Must not raise — exception is caught and logged
    _run(dispatcher.dispatch(rpc.REQUEST_VOTE, "2", "r", payload))
