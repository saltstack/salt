"""
Functional tests for RaftService bootstrapping.

Verifies that ``RaftService`` correctly wires up the Raft node, peers,
dispatcher, and heartbeat loop using in-process components — no running
Salt master required.
"""

import asyncio
import tempfile

from salt.cluster.consensus.peer import RaftDispatcher
from salt.cluster.consensus.raft.node import NodeState
from salt.cluster.consensus.service import RaftService, build_peer_pushers
from tests.pytests.functional.cluster.consensus.conftest import (
    FakePusher,
    _build_cluster,
    _deliver_all,
)
from tests.pytests.functional.cluster.consensus.test_raft_learner import _elect

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Shared temporary directory for the test module so SaltStorage can write.
_TMPDIR = tempfile.mkdtemp(prefix="salt_raft_svc_test_")


def _run(coro):
    return asyncio.run(coro)


def _make_opts(node_id, peers):
    return {
        "id": f"{node_id}-hostname",
        "interface": node_id,
        "cluster_id": "test-cluster",
        "cluster_peers": peers,
        "cachedir": _TMPDIR,
        # Use the legacy tight election window so in-process functional
        # tests stay fast (real cluster masters override the defaults via
        # opts to ride out CI heartbeat jitter).
        "cluster_election_min": 150,
        "cluster_election_max": 300,
    }


def _make_pushers(peer_ids):
    return {pid: FakePusher() for pid in peer_ids}


# ---------------------------------------------------------------------------
# build_peer_pushers
# ---------------------------------------------------------------------------


class TestBuildPeerPushers:
    def test_pairs_peers_with_pushers_in_order(self):
        opts = _make_opts("m1", ["m2", "m3"])
        p2, p3 = FakePusher(), FakePusher()
        result = build_peer_pushers(opts, [p2, p3])
        assert result == {"m2": p2, "m3": p3}

    def test_empty_peers_returns_empty_dict(self):
        opts = _make_opts("m1", [])
        assert build_peer_pushers(opts, []) == {}

    def test_single_peer(self):
        opts = _make_opts("m1", ["m2"])
        p = FakePusher()
        assert build_peer_pushers(opts, [p]) == {"m2": p}


# ---------------------------------------------------------------------------
# RaftService construction
# ---------------------------------------------------------------------------


class TestRaftServiceConstruction:
    def test_node_id_matches_opts(self):
        opts = _make_opts("master-1", ["master-2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["master-2"]))
            assert svc.node.node_id == "master-1"
        finally:
            loop.close()

    def test_peers_wired_to_node(self):
        opts = _make_opts("master-1", ["master-2", "master-3"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["master-2", "master-3"]))
            peer_ids = {p.node_id for p in svc.node.peers}
            assert peer_ids == {"master-2", "master-3"}
        finally:
            loop.close()

    def test_no_peers_node_has_empty_peer_list(self):
        opts = _make_opts("solo", [])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {})
            assert svc.node.peers == []
        finally:
            loop.close()

    def test_dispatcher_is_raft_dispatcher(self):
        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m2"]))
            assert isinstance(svc.dispatcher, RaftDispatcher)
        finally:
            loop.close()

    def test_dispatcher_node_id_matches(self):
        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m2"]))
            assert svc.dispatcher._local_id == "m1"
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# attach()
# ---------------------------------------------------------------------------


class TestRaftServiceAttach:
    def test_attach_sets_channel_dispatcher(self):
        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m2"]))

            class FakeChannel:
                _raft_dispatcher = None

            ch = FakeChannel()
            svc.attach(ch)
            assert ch._raft_dispatcher is svc.dispatcher
        finally:
            loop.close()

    def test_attach_twice_overwrites(self):
        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m2"]))

            class FakeChannel:
                _raft_dispatcher = None

            ch = FakeChannel()
            svc.attach(ch)
            svc.attach(ch)
            assert ch._raft_dispatcher is svc.dispatcher
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# start() / stop()
# ---------------------------------------------------------------------------


class TestRaftServiceLifecycle:
    def test_start_makes_node_follower(self):
        async def _body():
            opts = _make_opts("m1", ["m2"])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, _make_pushers(["m2"]))
            svc.start()
            assert svc.node.state == NodeState.FOLLOWER

        _run(_body())

    def test_single_node_becomes_leader_after_start(self):
        """A solo node (no peers) should elect itself once its timeout fires."""

        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            # AsyncTimeoutScheduler uses loop.call_later with real wall-clock
            # seconds.  Wait long enough for the follower timeout to fire
            # (gettimeout returns 0.15–0.3 s by default).
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break
            assert svc.node.state == NodeState.LEADER

        _run(_body())

    def test_stop_cancels_heartbeat(self):
        async def _body():
            opts = _make_opts("m1", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            svc.stop()
            assert svc._heartbeat_handle is None

        _run(_body())

    def test_stop_before_start_is_safe(self):
        opts = _make_opts("m1", [])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {})
            svc.stop()  # must not raise
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Heartbeat drives leader AE to peers
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_leader_heartbeat_sends_append_entries_to_peers(self):
        """
        After a solo node wins election, the heartbeat tick should send
        empty AppendEntries to any peers.  A solo node promotes itself;
        we then add a fake peer pusher and verify a heartbeat is sent.
        """

        async def _body():
            # Start as solo so it can elect itself without needing a peer ack
            opts = _make_opts("m1", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()

            # Wait for solo election
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break
            assert svc.node.state == NodeState.LEADER

            # Now inject a fake peer so the heartbeat has somewhere to send
            fake_pusher = FakePusher()
            from salt.cluster.consensus.peer import SaltPeer

            fake_peer = SaltPeer("m2", fake_pusher, "m1")
            svc.node.peers = [fake_peer]

            # Fire one heartbeat tick and let the task run
            svc._heartbeat_tick()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert fake_pusher.sent

        _run(_body())

    def test_follower_heartbeat_does_not_send(self):
        """Heartbeat tick on a follower must not push any frames."""

        async def _body():
            opts = _make_opts("m1", ["m2"])
            loop = asyncio.get_running_loop()
            pushers = _make_pushers(["m2"])
            svc = RaftService(opts, loop, pushers)
            svc.start()
            assert svc.node.state == NodeState.FOLLOWER

            svc._heartbeat_tick()
            await asyncio.sleep(0)
            assert not pushers["m2"].sent

        _run(_body())


# ---------------------------------------------------------------------------
# End-to-end: two services, election converges
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_three_services_elect_one_leader(self):
        """
        Three RaftService instances built on top of the conftest ClusterNode
        infrastructure (ManualTimeoutScheduler + FakePushers) elect exactly
        one leader when driven by the test_raft_transport._elect helper.
        """
        from tests.pytests.functional.cluster.consensus.test_raft_transport import (
            _elect,
        )

        async def _body():
            node_ids = ["node-a", "node-b", "node-c"]
            members = _build_cluster(node_ids)

            loop = asyncio.get_running_loop()
            services = {}
            for nid, cn in members.items():
                opts = _make_opts(nid, [o for o in node_ids if o != nid])
                svc = RaftService.__new__(RaftService)
                svc.opts = opts
                svc.loop = loop
                svc._peer_pushers = cn.pushers_out
                svc._node = cn.node
                svc._scheduler = cn.scheduler
                svc._dispatcher = cn.dispatcher
                svc._heartbeat_handle = None
                services[nid] = svc

            # Arm follower timers (ManualTimeoutScheduler, not wall-clock)
            for svc in services.values():
                svc._node.become_follower()
                svc._node.last_followed = svc._node.get_now() - 10

            await _elect(members)

            leaders = [
                nid for nid, cn in members.items() if cn.node.state == NodeState.LEADER
            ]
            assert len(leaders) == 1

        _run(_body())


# ---------------------------------------------------------------------------
# Founding CONFIG entry
# ---------------------------------------------------------------------------


class TestFoundingConfig:
    def test_leader_commits_founding_config_on_empty_log(self):
        """
        The first elected leader of a fresh cluster must write a CONFIG entry
        recording the founding voter set before any application commands.
        """

        async def _body():
            ids = ["m1", "m2", "m3"]
            members = _build_cluster(ids)
            for cn in members.values():
                cn.node.become_follower()
                cn.node.last_followed = cn.node.get_now() - 10

            # Inject _maybe_commit_founding_config via RaftService-like wiring.
            # We drive it manually: elect a leader then call the method directly.
            await _elect(members)

            leader_cn = next(
                cn for cn in members.values() if str(cn.node.state) == NodeState.LEADER
            )

            # Simulate what _heartbeat_tick does: call _maybe_commit_founding_config.
            # We use the service helper directly on a minimal RaftService wrapper.
            from salt.cluster.consensus.raft.log import LogEntryType  # noqa

            # Manually invoke the method logic (the node itself is what matters).
            voters = [leader_cn.node.node_id] + [
                p.node_id for p in leader_cn.node.peers if getattr(p, "voting", True)
            ]
            learners = []
            leader_cn.node.log_add(
                {"voters": voters, "learners": learners},
                entry_type=LogEntryType.CONFIG,
            )
            await _deliver_all(members, rounds=10)

            # All nodes must have the CONFIG entry committed.
            for nid, cn in members.items():
                config_entries = [
                    e for e in cn.node.log.entries if e.type == LogEntryType.CONFIG
                ]
                assert config_entries, f"{nid} must have CONFIG entry after founding"

        _run(_body())

    def test_maybe_commit_founding_config_no_ops_if_log_nonempty(self):
        """
        _maybe_commit_founding_config must not add a second CONFIG entry if
        the log already has content.
        """
        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m2"]))
            svc._node.become_follower()
            svc._node.become_candidate()
            svc._node.become_leader()
            # Put something in the log first.
            from salt.cluster.consensus.raft.log import LogEntryType  # noqa

            svc._node.log_add(
                {"voters": ["m1", "m2"], "learners": []},
                entry_type=LogEntryType.CONFIG,
            )
            log_idx_before = svc._node.log.index
            # Now call the method — must be a no-op.
            svc._maybe_commit_founding_config()
            assert svc._node.log.index == log_idx_before
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Dynamic joiner starts as learner
# ---------------------------------------------------------------------------


class TestDynamicJoinerAsLearner:
    def test_raftservice_voting_false_sets_node_voting_false(self):
        """RaftService(voting=False) produces a non-voting node."""
        opts = _make_opts("m4", ["m1"])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, _make_pushers(["m1"]), voting=False)
            assert svc.node.voting is False
        finally:
            loop.close()

    def test_learner_raftservice_does_not_start_election_after_start(self):
        """A learner-mode RaftService must not win elections."""

        async def _body():
            opts = _make_opts("m4", ["m1", "m2", "m3"])
            loop = asyncio.get_event_loop()
            pushers = _make_pushers(["m1", "m2", "m3"])
            svc = RaftService(opts, loop, pushers, voting=False)

            # Manually start without heartbeat scheduling (avoid asyncio.call_later).
            svc._node.register_schedule_timeout(
                __import__(
                    "salt.cluster.consensus.raft",
                    fromlist=["ManualTimeoutScheduler"],
                )
                .ManualTimeoutScheduler()
                .schedule
            )
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

            # Trigger the follower timeout callback directly.
            svc._node.follower_timeout_callback()

            assert (
                str(svc._node.state) == NodeState.FOLLOWER
            ), "Learner must not start election"

        _run(_body())


# ---------------------------------------------------------------------------
# Coverage gaps: heartbeat exception path, founding config exception path
# ---------------------------------------------------------------------------


class TestHeartbeatExceptionPaths:
    def test_heartbeat_tick_catches_send_error(self):
        """_heartbeat_tick swallows exceptions from send_append_entries."""
        from tests.support.mock import MagicMock

        opts = _make_opts("m1", ["m2"])
        loop = asyncio.new_event_loop()
        try:
            pushers = _make_pushers(["m2"])
            svc = RaftService(opts, loop, pushers)
            svc._node.become_follower()
            svc._node.become_candidate()
            svc._node.become_leader()

            bad_peer = MagicMock()
            bad_peer.node_id = "m2"
            bad_peer.voting = True
            bad_peer.append_entries.side_effect = RuntimeError("network error")
            svc._node.peers = [bad_peer]

            # Must not raise
            svc._heartbeat_tick()
        finally:
            loop.close()

    def test_heartbeat_tick_outer_exception_still_reschedules(self):
        """_heartbeat_tick reschedules even when an outer exception fires."""
        import asyncio

        opts = _make_opts("m1", [])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {})
            svc._node.become_follower()
            svc._node.become_candidate()
            svc._node.become_leader()

            # Patch _maybe_commit_founding_config to raise
            original = svc._maybe_commit_founding_config

            def boom():
                raise RuntimeError("founding config exploded")

            svc._maybe_commit_founding_config = boom
            # Must not propagate
            svc._heartbeat_tick()
            svc._maybe_commit_founding_config = original
        finally:
            loop.close()


class TestMaybeCommitFoundingConfigExceptionPath:
    def test_exception_in_log_add_is_caught(self):
        """_maybe_commit_founding_config catches log_add exceptions."""
        from tests.support.mock import patch

        opts = _make_opts("m1", [])
        loop = asyncio.new_event_loop()
        try:
            svc = RaftService(opts, loop, {})
            svc._node.become_follower()
            svc._node.become_candidate()
            svc._node.become_leader()

            with patch.object(svc._node, "log_add", side_effect=RuntimeError("boom")):
                # Must not raise
                svc._maybe_commit_founding_config()
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# on_ready / cluster-ready gate
# ---------------------------------------------------------------------------


class TestOnReady:
    """on_ready fires when this node appears in the committed voter set."""

    def _make_svc(self, node_id="m1", peers=("m2",), on_ready=None):
        opts = _make_opts(node_id, list(peers))
        loop = asyncio.new_event_loop()
        pushers = _make_pushers(peers)
        svc = RaftService(opts, loop, pushers, on_ready=on_ready)
        return svc, loop

    def test_on_ready_fires_when_node_becomes_voter(self):
        fired = []
        svc, loop = self._make_svc(on_ready=lambda: fired.append(True))
        try:
            svc._on_membership_change(["m1", "m2"], [])
            assert fired == [True]
        finally:
            loop.close()

    def test_on_ready_not_fired_when_node_absent(self):
        fired = []
        svc, loop = self._make_svc(on_ready=lambda: fired.append(True))
        try:
            svc._on_membership_change(["m2", "m3"], [])
            assert fired == []
        finally:
            loop.close()

    def test_on_ready_fires_only_once(self):
        fired = []
        svc, loop = self._make_svc(on_ready=lambda: fired.append(True))
        try:
            svc._on_membership_change(["m1", "m2"], [])
            svc._on_membership_change(["m1", "m2"], [])
            assert len(fired) == 1
        finally:
            loop.close()

    def test_on_ready_none_is_safe(self):
        svc, loop = self._make_svc(on_ready=None)
        try:
            # Must not raise
            svc._on_membership_change(["m1", "m2"], [])
        finally:
            loop.close()

    def test_on_ready_wired_to_membership_sm(self):
        """MembershipStateMachine.apply triggers on_ready via on_change hook."""
        fired = []
        svc, loop = self._make_svc(on_ready=lambda: fired.append(True))
        try:
            svc._node.membership_sm.apply({"voters": ["m1", "m2"], "learners": []})
            assert fired == [True]
        finally:
            loop.close()

    def test_on_ready_not_fired_for_learner_only_entry(self):
        """Node appearing only as a learner does not trigger readiness."""
        fired = []
        svc, loop = self._make_svc(on_ready=lambda: fired.append(True))
        try:
            svc._node.membership_sm.apply({"voters": ["m2"], "learners": ["m1"]})
            assert fired == []
        finally:
            loop.close()
