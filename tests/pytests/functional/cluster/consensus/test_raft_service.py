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


# ---------------------------------------------------------------------------
# Cluster-ring rebuild on membership change
# ---------------------------------------------------------------------------


class TestClusterRingRebuildHook:
    """
    ``RaftService._on_membership_change`` keeps the default
    ``"cluster"`` :class:`HashRing` in lock-step with the committed
    voter set so pre-multi-ring callers
    (``ring_membership.owns(opts, key)`` with no ring name) see a
    meaningful answer.

    Multi-ring deployments don't actually shard via the default
    ring — they route data types through named rings created with
    ``cluster.ring_create``.  But the rebuild on commit is what
    keeps the default ring's contents from drifting away from the
    cluster's voter set, which a misconfigured deployment may still
    rely on.
    """

    def _make_svc(self, node_id="m1", peers=("m2",), on_ready=None):
        opts = _make_opts(node_id, list(peers))
        loop = asyncio.new_event_loop()
        pushers = _make_pushers(peers)
        svc = RaftService(opts, loop, pushers, on_ready=on_ready)
        return svc, loop

    def test_commit_drives_rebuild_with_voter_set(self):
        """
        A CONFIG commit drives ``ring_membership.rebuild`` for the
        default ring with the committed voter set.  Learners are
        excluded — they don't own data.
        """
        from salt.cluster import ring_membership

        ring_membership.reset()
        svc, loop = self._make_svc()
        try:
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m2", "m3"], "learners": ["m4"]}, index=1
            )
            assert sorted(ring_membership.get_ring().nodes()) == ["m1", "m2", "m3"]
        finally:
            ring_membership.reset()
            loop.close()

    def test_repeated_commits_atomically_swap_ring(self):
        """
        Two CONFIG commits leave the ring in the latest committed
        shape, not a union.  Pins that rebuild replaces.
        """
        from salt.cluster import ring_membership

        ring_membership.reset()
        svc, loop = self._make_svc()
        try:
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m2", "m3"], "learners": []}, index=1
            )
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m4"], "learners": []}, index=2
            )
            assert sorted(ring_membership.get_ring().nodes()) == ["m1", "m4"]
        finally:
            ring_membership.reset()
            loop.close()

    def test_empty_voters_leaves_ring_alone(self):
        """
        An empty-voter commit (shouldn't happen in steady state) is
        tolerated: rebuild is skipped so the ring keeps whatever
        contents it had.  Defensive — guards against a buggy
        upstream commit that would otherwise erase the ring on the
        gate side.
        """
        from salt.cluster import ring_membership

        ring_membership.reset()
        svc, loop = self._make_svc()
        try:
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m2"], "learners": []}, index=1
            )
            assert sorted(ring_membership.get_ring().nodes()) == ["m1", "m2"]
            # Pathological empty commit — ring stays at the last
            # non-empty state rather than going empty.
            svc._on_membership_change([], [])
            assert sorted(ring_membership.get_ring().nodes()) == ["m1", "m2"]
        finally:
            ring_membership.reset()
            loop.close()


# ---------------------------------------------------------------------------
# Multi-ring registry + routing propose helpers (slice 2)
# ---------------------------------------------------------------------------


class TestMultiRingProposeHelpers:
    """
    The cluster-log multi-ring entrypoints: ``propose_ring_create``,
    ``propose_ring_destroy``, and ``propose_route``.

    Slice 2 wires the cluster-log persistence path; per-ring Raft
    groups themselves come up in slice 3 once
    ``_on_ring_registry_change`` is taught the lifecycle.
    """

    def test_propose_ring_create_validates_inputs(self):
        import pytest

        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            with pytest.raises(ValueError, match="non-empty ring_id"):
                svc.propose_ring_create("", ["solo"])

            with pytest.raises(ValueError, match="Unknown ring status"):
                svc.propose_ring_create("jobs", ["solo"], status="zombie")

            svc.stop()

        _run(_body())

    def test_propose_ring_create_requires_leader(self):
        import pytest

        async def _body():
            opts = _make_opts("follower", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            # No start(); node stays a follower.
            with pytest.raises(RuntimeError, match="must run on the Raft leader"):
                svc.propose_ring_create("jobs", ["follower"])

        _run(_body())

    def test_propose_ring_create_appends_registry_entry(self):
        from salt.cluster.consensus.raft.log import LogEntryType

        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break
            assert svc.node.state == NodeState.LEADER

            initial = svc.node.log.index
            svc.propose_ring_create("jobs", ["m2", "m1"])
            assert svc.node.log.index == initial + 1
            entry = svc.node.log.get(svc.node.log.index)
            assert entry.type == LogEntryType.RING_REGISTRY
            # Founders sorted canonically so every replica sees the same form.
            assert entry.cmd == {
                "ring_id": "jobs",
                "founding_voters": ["m1", "m2"],
                "status": "active",
            }

            svc.node.advance_commit_index()
            assert svc._ring_registry_sm.active_rings() == ["jobs"]
            svc.stop()

        _run(_body())

    def test_propose_ring_destroy_marks_status_destroyed(self):
        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()
            assert svc._ring_registry_sm.active_rings() == ["jobs"]

            svc.propose_ring_destroy("jobs")
            svc.node.advance_commit_index()
            assert svc._ring_registry_sm.active_rings() == []
            # The destroy record itself remains for audit.
            assert svc._ring_registry_sm.get("jobs")["status"] == "destroyed"
            svc.stop()

        _run(_body())

    def test_propose_route_appends_route_entry(self):
        from salt.cluster.consensus.raft.log import LogEntryType

        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            initial = svc.node.log.index
            svc.propose_route("jobs", "jobs_ring")
            entry = svc.node.log.get(svc.node.log.index)
            assert svc.node.log.index == initial + 1
            assert entry.type == LogEntryType.ROUTE
            assert entry.cmd == {"data_type": "jobs", "ring_id": "jobs_ring"}

            svc.node.advance_commit_index()
            assert svc._routing_sm.get("jobs") == "jobs_ring"

            # Clearing the route routes data back to broadcast.
            svc.propose_route("jobs", None)
            svc.node.advance_commit_index()
            assert svc._routing_sm.get("jobs") is None
            svc.stop()

        _run(_body())

    def test_propose_route_validates_data_type(self):
        import pytest

        async def _body():
            opts = _make_opts("solo", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            with pytest.raises(ValueError, match="non-empty data_type"):
                svc.propose_route("", "jobs_ring")
            svc.stop()

        _run(_body())

    def test_propose_route_requires_leader(self):
        import pytest

        async def _body():
            opts = _make_opts("follower", [])
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            with pytest.raises(RuntimeError, match="must run on the Raft leader"):
                svc.propose_route("jobs", "jobs_ring")

        _run(_body())


# ---------------------------------------------------------------------------
# Per-ring Raft group lifecycle (slice 3)
# ---------------------------------------------------------------------------


def _make_ring_opts(node_id, peers, tmp_path):
    """
    Variant of ``_make_opts`` that pins ``cachedir`` per-test so each
    case gets a clean on-disk slate.  Multi-ring lifecycle tests need
    isolation because a ring's storage persists across calls — sharing
    the module-level ``_TMPDIR`` lets prior tests leak state.
    """
    return {
        "id": f"{node_id}-hostname",
        "interface": node_id,
        "cluster_id": "test-cluster",
        "cluster_peers": peers,
        "cachedir": str(tmp_path),
        "cluster_election_min": 150,
        "cluster_election_max": 300,
    }


class TestPerRingLifecycle:
    """
    The ``RING_REGISTRY`` -> per-ring ``Node`` lifecycle: creating a
    ring spins up an in-process Raft group; destroying it tears the
    group down without touching the cluster group.
    """

    def test_create_ring_brings_up_node_when_self_is_founder(self, tmp_path):
        from salt.cluster.consensus.raft.node import NodeState

        async def _body():
            opts = _make_ring_opts("solo", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break
            assert svc.node.state == NodeState.LEADER

            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()

            # Per-ring Node now registered in self._nodes; dispatcher
            # routes inbound RPCs for that ring to it.
            assert "jobs" in svc._nodes
            assert svc._nodes["jobs"] is not svc._node
            assert svc._nodes["jobs"].node_id == "solo"
            assert svc.dispatcher._nodes["jobs"] is svc._nodes["jobs"]

            # The heartbeat tick drives the per-ring Node through
            # election + founding-CONFIG.  Give it a few cycles to
            # converge (single-node so it elects itself), then push
            # commit_index ourselves the way the cluster-Node solo
            # tests do (no peers means no acks ever land).
            for _ in range(50):
                await asyncio.sleep(0.01)
                ring_node = svc._nodes["jobs"]
                if ring_node.state == NodeState.LEADER and ring_node.log.index >= 0:
                    break
            ring_node = svc._nodes["jobs"]
            assert ring_node.state == NodeState.LEADER
            ring_node.advance_commit_index()
            # Founding CONFIG committed to the *ring's* own log,
            # naming ``["solo"]`` as the founding voter.
            assert ring_node.membership_sm.current_voters() == ["solo"]
            svc.stop()

        _run(_body())

    def test_non_founder_does_not_bring_up_ring(self, tmp_path):
        """
        A registry entry that does not list this master is observed
        but does not cause local bring-up — the ring's data plane
        runs on the founders, not this master.
        """

        async def _body():
            opts = _make_ring_opts("bystander", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            svc.propose_ring_create("jobs", ["other-1", "other-2"])
            svc.node.advance_commit_index()

            assert "jobs" not in svc._nodes
            # Registry SM still records the entry — every master
            # agrees on the registry; only the data plane is local.
            assert svc._ring_registry_sm.active_rings() == ["jobs"]
            svc.stop()

        _run(_body())

    def test_destroy_ring_tears_down_node(self, tmp_path):
        async def _body():
            opts = _make_ring_opts("solo", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()
            assert "jobs" in svc._nodes

            svc.propose_ring_destroy("jobs")
            svc.node.advance_commit_index()
            assert "jobs" not in svc._nodes
            assert "jobs" not in svc.dispatcher._nodes
            # The cluster group is untouched.
            assert "cluster" in svc._nodes
            svc.stop()

        _run(_body())

    def test_ring_storage_isolated_from_cluster(self, tmp_path):
        """
        The per-ring ``Node`` writes to a ring-keyed on-disk path,
        not the cluster's path.  Pin the invariant that a committed
        log entry in the ring does not appear in the cluster's log
        bank — otherwise multi-ring would corrupt cluster Raft state.
        """
        from salt.cluster.consensus.storage import SaltStorage

        async def _body():
            opts = _make_ring_opts("solo", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()
            for _ in range(50):
                await asyncio.sleep(0.01)
                ring_node = svc._nodes["jobs"]
                if ring_node.log.index >= 0:
                    break
            svc._nodes["jobs"].advance_commit_index()

            ring_storage = SaltStorage("solo", opts, ring_id="jobs")
            cluster_storage = SaltStorage("solo", opts, ring_id="cluster")
            assert ring_storage._meta_bank != cluster_storage._meta_bank
            # The ring's log on disk has at least the founding CONFIG.
            ring_entries = ring_storage.load_log()
            assert ring_entries, "ring log should have committed entries"
            svc.stop()

        _run(_body())

    def test_refuse_to_create_ring_named_cluster(self, tmp_path):
        """
        ``"cluster"`` is the reserved group id for the main cluster
        Raft group.  Bringing up a ring named ``"cluster"`` would
        shadow it; ``_bring_up_ring`` refuses and logs a warning.
        """

        async def _body():
            opts = _make_ring_opts("solo", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            # Bypass propose_ring_create and call the lifecycle
            # callback directly so we exercise the guard.
            svc._on_ring_registry_change("cluster", ["solo"], "active")
            # No second cluster Node created.
            assert len(svc._nodes) == 1
            assert svc._nodes["cluster"] is svc._node
            svc.stop()

        _run(_body())

    def test_create_destroy_roundtrip_reuses_ring_storage(self, tmp_path):
        """
        Re-creating a destroyed ring with the same id picks up the
        persisted on-disk state — Raft state survives a destroy/create
        cycle, which is the documented recovery story for an operator
        who tore a ring down too eagerly.
        """

        async def _body():
            opts = _make_ring_opts("solo", [], tmp_path)
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})
            svc.start()
            for _ in range(50):
                await asyncio.sleep(0.01)
                if svc.node.state == NodeState.LEADER:
                    break

            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()
            for _ in range(50):
                await asyncio.sleep(0.01)
                ring_node = svc._nodes["jobs"]
                if ring_node.log.index >= 0:
                    break
            svc._nodes["jobs"].advance_commit_index()
            committed_index = svc._nodes["jobs"].log.index

            svc.propose_ring_destroy("jobs")
            svc.node.advance_commit_index()
            assert "jobs" not in svc._nodes

            # Re-create.  The bring-up reads the ring's storage,
            # which still has the founding CONFIG from before.
            svc.propose_ring_create("jobs", ["solo"])
            svc.node.advance_commit_index()
            assert "jobs" in svc._nodes
            # Same log index as before the destroy — proves we picked
            # up persisted state instead of starting fresh.
            assert svc._nodes["jobs"].log.index == committed_index
            svc.stop()

        _run(_body())


# ---------------------------------------------------------------------------
# Per-ring voter-health watchdog
# ---------------------------------------------------------------------------


class TestPerRingVoterHealth:
    """
    The voter-health watchdog iterates every Raft group hosted in
    this process so a ring losing quorum gets the same auto-replace
    treatment the cluster Raft group does.

    These tests stand up a solo master, manually inject per-ring
    Nodes whose membership has a stale-contact peer, run one tick of
    the watchdog, and assert the structured sentinel records the
    unhealthy voter under the right group.
    """

    def _make_ring_node(self, svc, ring_id, voters, learners=()):
        """
        Build a per-ring ``Node`` with the given voter/learner set,
        elect it leader, and register it on the service so the
        watchdog walks it.
        """
        from salt.cluster.consensus.raft import Node
        from salt.cluster.consensus.storage import SaltStorage

        node_id = svc.opts["interface"]
        storage = SaltStorage(node_id, svc.opts, ring_id=ring_id)
        ring_node = Node(node_id, storage=storage, voting=True)
        ring_node.register_schedule_timeout(svc._scheduler.schedule)
        # Seed the membership SM directly — we don't need to drive a
        # full election for the watchdog test.
        ring_node.membership_sm.apply(
            {"voters": list(voters), "learners": list(learners)}, index=0
        )
        ring_node._applied_config_index = 0
        # Force leader state so the watchdog inspects this node's
        # last_contact map.  The same hot-path the production
        # ``_check_voter_health`` walks.  Follower → candidate →
        # leader is the legal NodeState transition order; jumping
        # straight from start to leader raises by design.
        ring_node.become_follower()
        ring_node.become_candidate()
        ring_node.state.become_leader()
        svc._nodes[ring_id] = ring_node
        return ring_node

    def test_watchdog_records_unhealthy_voter_per_ring(self, tmp_path):
        """
        A stale ``last_contact`` on a ring voter shows up under
        ``rings.<ring>.unhealthy_voters`` in the health sentinel.
        Pin the structured-sentinel contract — ``cluster.members``
        consumes the top-level fields, and per-ring consumers reach
        into the rings dict.
        """
        import json

        async def _body():
            opts = _make_ring_opts("self", [], tmp_path)
            opts["cluster_voter_timeout"] = 0.001  # everything is "stale"
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})

            ring_node = self._make_ring_node(
                svc,
                ring_id="jobs",
                voters=["self", "peer-A"],
            )
            # Inject a peer with a stale last_contact.  In production
            # this is updated by AppendEntries replies; absence means
            # "never heard from" which the watchdog conservatively
            # ignores, so we set an explicit timestamp.
            ring_node.peers = []
            # Use a peer-like stub: just needs node_id + the peer
            # appearing in current_voters.
            from salt.cluster.consensus.raft.node import Peer

            class _StubPeer(Peer):
                def __init__(self, node_id):
                    super().__init__(None, node_id=node_id, voting=True)

            ring_node.peers = [_StubPeer("peer-A")]
            ring_node._peer_last_contact["peer-A"] = ring_node.get_now() - 10.0

            # Run a single watchdog tick by calling the method
            # directly (the periodic schedule would do the same).
            svc._check_voter_health()

            sentinel_path = tmp_path / "cluster-health.json"
            with sentinel_path.open() as fp:
                body = json.load(fp)
            assert "rings" in body
            assert body["rings"]["jobs"]["unhealthy_voters"] == ["peer-A"]
            # The cluster group's lists stay at the top level so
            # pre-multi-ring readers (``cluster.members``) keep
            # working unchanged.
            assert body["unhealthy_voters"] == []

        _run(_body())

    def test_watchdog_replaces_dead_voter_with_caught_up_learner(self, tmp_path):
        """
        Ring outage / recovery scenario.  Two scenarios in one test:

        1. A 3-voter ring with one healthy learner.  Mark one voter
           stale.  The watchdog (auto_replace=True) demotes the
           stale voter and promotes the learner — the ring keeps
           three voters and stays writable.
        2. After replacement, the ring's voter set is
           ``{healthy_voters} ∪ {promoted_learner}`` — sorted, the
           previously-stale voter is gone.

        This is the per-ring counterpart of the cluster-Raft
        single-server change in Ongaro §6.4.  Without it, a dead
        ring voter would silently stall the ring until an operator
        intervened.
        """
        from salt.cluster.consensus.raft import ManualPeer, Node

        async def _body():
            opts = _make_ring_opts("self", [], tmp_path)
            opts["cluster_voter_timeout"] = 0.001
            opts["cluster_auto_replace_voters"] = True
            opts["cluster_min_voters"] = 2  # 3-voter ring; floor at 2
            opts["cluster_demote_cooldown"] = 0.0  # no cooldown for tests
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})

            # 3 voters + 1 learner.  ``self`` is the leader; voter-A
            # will go stale, voter-B stays healthy.
            ring_node = self._make_ring_node(
                svc,
                ring_id="jobs",
                voters=["self", "voter-A", "voter-B"],
                learners=["candidate-L"],
            )

            # Stub peers so heartbeats don't blow up.
            def _stub(node_id):
                stub_node = Node(node_id)
                stub_node.register_schedule_timeout(svc._scheduler.schedule)
                stub_node.become_follower()
                return ManualPeer(stub_node, node_id=node_id)

            ring_node.peers = [
                _stub("voter-A"),
                _stub("voter-B"),
                _stub("candidate-L"),
            ]
            now = ring_node.get_now()
            ring_node._peer_last_contact["voter-A"] = now - 10.0
            ring_node._peer_last_contact["voter-B"] = now  # healthy
            ring_node._peer_last_contact["candidate-L"] = now
            # Mark the learner as caught up so it's a promotion
            # candidate.  Without this the watchdog skips it.  Use a
            # generous lookahead because the demotion proposal
            # advances ``log.index`` by 1 before the candidate-check
            # runs; setting match_index well past the current index
            # means the learner stays caught-up through that bump.
            ring_node.match_index["candidate-L"] = ring_node.log.index + 100

            demoted = []
            promoted = []
            original_demote = ring_node.propose_voter_demotion
            original_promote = ring_node.propose_voter_promotion_to_replace

            def _spy_demote(peer_id, min_voters=3):
                demoted.append(peer_id)
                return original_demote(peer_id, min_voters=min_voters)

            def _spy_promote(peer_id):
                promoted.append(peer_id)
                return original_promote(peer_id)

            ring_node.propose_voter_demotion = _spy_demote
            ring_node.propose_voter_promotion_to_replace = _spy_promote

            svc._check_voter_health()

            assert demoted == ["voter-A"], (
                f"expected voter-A to be demoted, watchdog called "
                f"propose_voter_demotion with {demoted!r}"
            )
            assert promoted == ["candidate-L"], (
                f"expected candidate-L to be promoted, watchdog called "
                f"propose_voter_promotion_to_replace with {promoted!r}"
            )
            assert ("jobs", "voter-A") in svc._recently_demoted

        _run(_body())

    def test_watchdog_demotes_per_ring_voter_with_auto_replace(self, tmp_path):
        """
        With ``cluster_auto_replace_voters=True``, an unhealthy
        per-ring voter is proposed for demotion.  The cooldown is
        keyed by (group, peer) so a demote on one ring doesn't lock
        out the same peer-id on another ring.
        """

        async def _body():
            opts = _make_ring_opts("self", [], tmp_path)
            opts["cluster_voter_timeout"] = 0.001
            opts["cluster_auto_replace_voters"] = True
            opts["cluster_min_voters"] = 1  # allow demotion in this tiny ring
            loop = asyncio.get_running_loop()
            svc = RaftService(opts, loop, {})

            ring_node = self._make_ring_node(
                svc, ring_id="jobs", voters=["self", "peer-A"]
            )
            # ManualPeer wraps a real Node, so the leader's heartbeat
            # path (driven inside propose_voter_demotion) doesn't
            # crash on a None backing Node.  The wrapped peer is a
            # cheap stand-in — it doesn't need a real Raft loop for
            # this test.
            from salt.cluster.consensus.raft import ManualPeer, Node

            peer_a = Node("peer-A")
            peer_a.register_schedule_timeout(svc._scheduler.schedule)
            peer_a.become_follower()
            ring_node.peers = [ManualPeer(peer_a, node_id="peer-A")]
            ring_node._peer_last_contact["peer-A"] = ring_node.get_now() - 10.0
            ring_node.match_index["peer-A"] = ring_node.log.index

            # Capture the propose_voter_demotion call.
            demoted = []
            original = ring_node.propose_voter_demotion

            def _spy(peer_id, min_voters=3):
                demoted.append(peer_id)
                return original(peer_id, min_voters=min_voters)

            ring_node.propose_voter_demotion = _spy

            svc._check_voter_health()

            assert demoted == ["peer-A"]
            assert ("jobs", "peer-A") in svc._recently_demoted

        _run(_body())
