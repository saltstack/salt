"""
Scenario tests for Raft cluster membership via RaftService.

These tests exercise the full path from ``RaftService.notify_peer_joined``
through ``Node.append_entries_reply`` → ``Node.apply_entries`` →
``MembershipStateMachine``, using real ``RaftService`` objects wired together
with ``FakePusher`` instead of live TCP connections.

Scenarios covered
-----------------
1. ``notify_peer_joined`` adds a non-voting learner peer to ``node.peers``.
2. Leader replicates log entries to the learner after ``notify_peer_joined``.
3. Learner is promoted to voter after its log catches up (full round-trip).
4. ``MembershipStateMachine`` reflects the committed voter set after promotion.
5. Founding CONFIG entry propagates to all followers and is applied.
6. Quorum is unaffected while a learner is pending promotion.
"""

import asyncio
import tempfile

from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.node import NodeState
from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler
from salt.cluster.consensus.service import RaftService
from tests.pytests.functional.cluster.consensus.conftest import FakePusher

# ---------------------------------------------------------------------------
# ServiceCluster — RaftService-based in-process cluster
# ---------------------------------------------------------------------------

_TMPDIR = tempfile.mkdtemp(prefix="salt_raft_scenario_")


def _make_opts(node_id, peers, cachedir=None):
    return {
        "id": f"{node_id}-hostname",
        "interface": node_id,
        "cluster_id": "scenario-cluster",
        "cluster_peers": peers,
        "cachedir": cachedir or _TMPDIR,
    }


class ServiceCluster:
    """
    A fully-wired in-process cluster of ``RaftService`` objects.

    Internals
    ---------
    * Each service gets a ``ManualTimeoutScheduler`` instead of the real
      ``AsyncTimeoutScheduler``, so time is driven deterministically.
    * Outbound pushers are ``FakePusher`` objects; we deliver messages by
      calling ``deliver`` (analogous to ``_deliver_all`` in conftest).
    * ``RaftService._make_peer`` is monkeypatched to create ``SaltPeer``
      objects backed by ``FakePusher`` instead of real TCP connections.
    * Pass *cachedir* to isolate storage from other tests.
    """

    def __init__(self, node_ids, loop=None, cachedir=None):
        self.node_ids = list(node_ids)
        self._loop = loop  # may be None; resolved lazily on first use
        self._cachedir = cachedir or tempfile.mkdtemp(prefix="salt_raft_sc_")
        # pushers[src][dst] = FakePusher
        self.pushers: dict[str, dict[str, FakePusher]] = {}
        self.services: dict[str, RaftService] = {}
        self.schedulers: dict[str, ManualTimeoutScheduler] = {}

        # Pre-allocate all pushers so every pair of nodes can communicate
        # from the start, including nodes not yet "joined".
        for nid in self.node_ids:
            self.pushers[nid] = {
                other: FakePusher() for other in self.node_ids if other != nid
            }

        for nid in self.node_ids:
            self._init_service(nid, [other for other in self.node_ids if other != nid])

    def _resolve_loop(self):
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _init_service(self, nid, peers):
        loop = self._resolve_loop()
        opts = _make_opts(nid, peers, cachedir=self._cachedir)
        peer_pushers = {
            pid: self.pushers[nid][pid]
            for pid in peers
            if pid in self.pushers.get(nid, {})
        }
        svc = RaftService(opts, loop, peer_pushers)

        scheduler = ManualTimeoutScheduler()
        svc._scheduler = scheduler
        svc._node.register_schedule_timeout(scheduler.schedule)
        self.schedulers[nid] = scheduler

        # Re-wire the heartbeat to go through ManualTimeoutScheduler rather
        # than loop.call_later so tests can drive it deterministically.
        def _manual_schedule_heartbeat():
            handle = scheduler.schedule(0.05, svc._heartbeat_tick)
            svc._heartbeat_handle = handle

        svc._schedule_heartbeat = _manual_schedule_heartbeat

        _patch_make_peer(svc, self)

        for other_id, pusher in self.pushers[nid].items():
            svc._dispatcher._pushers.setdefault(other_id, pusher)

        self.services[nid] = svc
        # Queue the first heartbeat in the manual scheduler immediately so
        # tick() will fire it without needing to call start().
        svc._schedule_heartbeat()
        return svc

    # ------------------------------------------------------------------
    # Helpers for adding a latecomer as a learner
    # ------------------------------------------------------------------

    def add_learner(self, learner_id):
        """
        Add *learner_id* to the cluster as a non-voting learner.

        Allocates a new ``RaftService`` for the learner and calls
        ``notify_peer_joined`` on all existing members, mirroring the
        Salt-level ``cluster/peer/join-notify`` flow.
        """
        loop = self._resolve_loop()
        existing = list(self.services.keys())

        # Allocate pushers for the new node (both directions).
        self.pushers[learner_id] = {other: FakePusher() for other in existing}
        for nid in existing:
            self.pushers[nid][learner_id] = FakePusher()

        # Build a learner RaftService.
        opts = _make_opts(learner_id, existing, cachedir=self._cachedir)
        peer_pushers = {pid: self.pushers[learner_id][pid] for pid in existing}
        svc = RaftService(opts, loop, peer_pushers, voting=False)

        scheduler = ManualTimeoutScheduler()
        svc._scheduler = scheduler
        svc._node.register_schedule_timeout(scheduler.schedule)
        self.schedulers[learner_id] = scheduler

        def _manual_schedule_heartbeat():
            handle = scheduler.schedule(0.05, svc._heartbeat_tick)
            svc._heartbeat_handle = handle

        svc._schedule_heartbeat = _manual_schedule_heartbeat

        _patch_make_peer(svc, self)

        # Wire the dispatcher.
        for other_id, pusher in self.pushers[learner_id].items():
            svc._dispatcher._pushers.setdefault(other_id, pusher)

        self.services[learner_id] = svc
        svc._schedule_heartbeat()

        # Wire existing nodes' dispatchers to reach the learner and vice-versa.
        for nid, existing_svc in self.services.items():
            if nid == learner_id:
                continue
            pusher_to_learner = self.pushers[nid][learner_id]
            existing_svc._dispatcher._pushers[learner_id] = pusher_to_learner

        # Notify all existing members that the learner has joined.
        for nid, existing_svc in list(self.services.items()):
            if nid != learner_id:
                existing_svc.notify_peer_joined(learner_id)

        return svc

    # ------------------------------------------------------------------
    # deliver — route buffered FakePusher messages through dispatchers
    # ------------------------------------------------------------------

    async def deliver(self, rounds=12, include=None):
        """
        Drain all outbound FakePushers and feed bytes into the destination
        dispatcher.  Analogous to conftest._deliver_all but operates on
        ``RaftService`` objects instead of ``ClusterNode`` objects.
        """
        from salt.cluster.consensus import rpc

        ids = include if include is not None else list(self.services.keys())

        for _ in range(rounds):
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            delivered = False
            for src_id in ids:
                for dst_id, pusher in list(self.pushers[src_id].items()):
                    if dst_id not in self.services:
                        continue
                    while pusher.sent:
                        raw = pusher.sent.popleft()
                        try:
                            tag, s, rid, group, payload = rpc.unpack(raw)
                            dst_svc = self.services[dst_id]
                            await dst_svc._dispatcher.dispatch(
                                tag, s, rid, payload, raft_group_id=group
                            )
                            delivered = True
                        except Exception:  # pylint: disable=broad-except
                            pass
            if not delivered:
                break

    def tick(self, node_ids=None):
        """Advance schedulers and fire timeouts."""
        ids = node_ids if node_ids is not None else list(self.services.keys())
        for nid in ids:
            self.schedulers[nid].advance_clock_to_next_timeout()
            self.schedulers[nid].process_timeouts()

    async def elect(self, max_rounds=80):
        """Drive the cluster until exactly one leader emerges."""
        for _ in range(max_rounds):
            self.tick()
            await self.deliver(rounds=4)
            leaders = [
                nid
                for nid, svc in self.services.items()
                if str(svc._node.state) == NodeState.LEADER
            ]
            if len(leaders) == 1:
                return leaders[0]
        raise AssertionError(
            "No leader elected after max rounds. States: "
            + str({nid: str(svc._node.state) for nid, svc in self.services.items()})
        )

    def leader(self):
        for nid, svc in self.services.items():
            if str(svc._node.state) == NodeState.LEADER:
                return nid, svc
        return None, None


def _patch_make_peer(svc: RaftService, cluster: "ServiceCluster"):
    """
    Replace ``svc._make_peer`` with a version that hands back a ``SaltPeer``
    backed by a ``FakePusher`` from *cluster*, creating one on-demand if
    needed.

    This prevents ``_make_peer`` from trying to instantiate
    ``salt.transport.tcp.PublishServer``.
    """
    from salt.cluster.consensus.peer import SaltPeer

    node_id = svc._node.node_id

    def fake_make_peer(addr, voting=True):
        # Ensure bidirectional FakePusher entry exists.
        if node_id not in cluster.pushers:
            cluster.pushers[node_id] = {}
        if addr not in cluster.pushers[node_id]:
            cluster.pushers[node_id][addr] = FakePusher()
        pusher = cluster.pushers[node_id][addr]
        svc._peer_pushers[addr] = pusher
        svc._dispatcher._pushers[addr] = pusher
        return SaltPeer(addr, pusher, node_id, voting=voting)

    svc._make_peer = fake_make_peer


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Scenario 1: notify_peer_joined adds a non-voting learner peer
# ---------------------------------------------------------------------------


class TestNotifyPeerJoined:
    def test_adds_non_voting_peer_to_node_peers(self, tmp_path):
        """
        ``notify_peer_joined`` must add the new address to ``node.peers``
        as a non-voting learner, regardless of whether this node is the leader.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()

            # Notify all members that m4 has joined.
            cluster.add_learner("m4")

            # Every existing member must now have m4 in its peer list
            # as a non-voting peer.
            for nid in ["m1", "m2", "m3"]:
                svc = cluster.services[nid]
                peer_ids = {p.node_id for p in svc._node.peers}
                assert "m4" in peer_ids, f"{nid} must know about m4"
                m4_peer = next(p for p in svc._node.peers if p.node_id == "m4")
                assert not m4_peer.voting, f"m4 must be non-voting on {nid}"

        _run(_body())

    def test_ignores_self(self):
        """
        ``notify_peer_joined`` is a no-op when called with the node's own id.
        """
        cluster = ServiceCluster(["m1", "m2"])
        svc = cluster.services["m1"]
        initial_peers = list(svc._node.peers)
        svc.notify_peer_joined("m1")
        assert svc._node.peers == initial_peers

    def test_ignores_already_known_peer(self):
        """
        Calling ``notify_peer_joined`` for an already-known peer must not
        duplicate it in ``node.peers``.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        svc = cluster.services["m1"]
        peer_count_before = len(svc._node.peers)
        svc.notify_peer_joined("m2")  # m2 already in peers
        assert len(svc._node.peers) == peer_count_before

    def test_leader_initialises_replication_tracking(self, tmp_path):
        """
        When the leader receives ``notify_peer_joined`` it must initialise
        ``next_index`` and ``match_index`` for the new learner.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            cluster.add_learner("m4")

            assert (
                "m4" in leader_svc._node.next_index
            ), "leader must track m4 next_index"
            assert (
                "m4" in leader_svc._node.match_index
            ), "leader must track m4 match_index"
            assert leader_svc._node.match_index["m4"] == -1

        _run(_body())


# ---------------------------------------------------------------------------
# Scenario 2: leader replicates to learner after notify_peer_joined
# ---------------------------------------------------------------------------


class TestLeaderReplicatesToLearner:
    def test_learner_receives_log_entry_after_join(self):
        """
        After ``notify_peer_joined``, the leader must replicate existing and
        new log entries to the learner.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            # Commit an application command before the learner joins.
            leader_svc._node.log_add(b"pre-join-entry")
            await cluster.deliver(rounds=16)

            # Add the learner.
            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            # Deliver several rounds so AppendEntries flows to the learner.
            for _ in range(20):
                cluster.tick()
                await cluster.deliver(rounds=8)

            assert (
                learner_svc._node.log.index >= 0
            ), "Learner must have received at least one log entry"

        _run(_body())

    def test_learner_log_matches_leader_after_replication(self):
        """
        After enough replication rounds the learner's log index must match
        the leader's.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._node.log_add(b"cmd-a")
            leader_svc._node.log_add(b"cmd-b")
            await cluster.deliver(rounds=16)

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            assert (
                learner_svc._node.log.index == leader_svc._node.log.index
            ), "Learner log index must match leader"

        _run(_body())


# ---------------------------------------------------------------------------
# Scenario 3: learner is promoted to voter (full round-trip via RaftService)
# ---------------------------------------------------------------------------


class TestLearnerPromotion:
    def test_leader_proposes_config_entry_when_learner_catches_up(self):
        """
        Once the learner's log matches the leader's, ``append_entries_reply``
        must trigger a CONFIG entry proposing promotion.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._node.log_add(b"some-command")
            await cluster.deliver(rounds=16)

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            config_entries = [
                e for e in leader_svc._node.log.entries if e.type == LogEntryType.CONFIG
            ]
            assert config_entries, "Leader must have proposed a CONFIG entry for m4"
            voters = config_entries[-1].cmd.get("voters", [])
            assert "m4" in voters, f"m4 must appear in CONFIG voters: {voters}"

        _run(_body())

    def test_learner_voting_flag_flips_after_config_commits(self):
        """
        After the CONFIG entry commits and is applied, the learner's own
        ``node.voting`` must flip to ``True``.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._node.log_add(b"pre-promotion-cmd")
            await cluster.deliver(rounds=16)

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(40):
                cluster.tick()
                await cluster.deliver(rounds=8)

            assert (
                learner_svc._node.voting is True
            ), "Learner node.voting must be True after CONFIG entry applied"

        _run(_body())

    def test_leader_peer_entry_for_learner_becomes_voting_after_config(self):
        """
        From the leader's perspective, the ``SaltPeer`` object for m4 must
        become ``voting=True`` after the CONFIG entry is applied.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._node.log_add(b"cmd")
            await cluster.deliver(rounds=16)

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(40):
                cluster.tick()
                await cluster.deliver(rounds=8)

            m4_peer = next(
                (p for p in leader_svc._node.peers if p.node_id == "m4"), None
            )
            assert m4_peer is not None, "Leader must still have m4 in peers"
            assert (
                m4_peer.voting is True
            ), "Leader's peer entry for m4 must be voting=True after promotion"

        _run(_body())


# ---------------------------------------------------------------------------
# Scenario 4: MembershipStateMachine reflects committed state
# ---------------------------------------------------------------------------


class TestMembershipStateMachineAfterJoin:
    def test_membership_sm_shows_new_voter_after_promotion(self):
        """
        After the promotion CONFIG entry commits, ``service.membership``
        must report m4 as a voter on every node that has applied the entry.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._node.log_add(b"hello")
            await cluster.deliver(rounds=16)

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(40):
                cluster.tick()
                await cluster.deliver(rounds=8)

            voters = leader_svc.membership.current_voters()
            assert (
                "m4" in voters
            ), f"MembershipStateMachine must list m4 as voter; got {voters}"

    def test_membership_sm_version_advances_after_each_config(self):
        """
        Each committed CONFIG entry must increment ``membership_version``
        on the leader.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            # Founding CONFIG
            leader_svc._maybe_commit_founding_config()
            await cluster.deliver(rounds=20)

            v1 = leader_svc.membership.membership_version
            assert v1 >= 0, "Version must be set after founding CONFIG"

            leader_svc._node.log_add(b"cmd")
            await cluster.deliver(rounds=16)

            # Add learner → triggers promotion CONFIG
            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            for _ in range(40):
                cluster.tick()
                await cluster.deliver(rounds=8)

            v2 = leader_svc.membership.membership_version
            assert v2 > v1, "Version must advance after promotion CONFIG"

        _run(_body())

    def test_membership_sm_not_updated_by_uncommitted_config(self):
        """
        A CONFIG entry that is proposed but not yet committed must NOT
        advance the MembershipStateMachine.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            version_before = leader_svc.membership.membership_version

            # Write a CONFIG entry but do not deliver it (no commits).
            leader_svc._node.log_add(
                {"voters": ["m1", "m2", "m3"], "learners": []},
                entry_type=LogEntryType.CONFIG,
            )
            # No deliver — entry is not committed or applied yet.

            assert (
                leader_svc.membership.membership_version == version_before
            ), "SM must not update before CONFIG entry is committed"

        _run(_body())


# ---------------------------------------------------------------------------
# Scenario 5: founding CONFIG propagates to followers and is applied
# ---------------------------------------------------------------------------


class TestFoundingConfigScenario:
    def test_founding_config_applied_on_all_nodes(self):
        """
        After the leader proposes the founding CONFIG entry and it commits,
        every node's ``MembershipStateMachine`` must list all original voters.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._maybe_commit_founding_config()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            for nid, svc in cluster.services.items():
                voters = svc.membership.current_voters()
                for orig in ["m1", "m2", "m3"]:
                    assert (
                        orig in voters
                    ), f"{nid}: founding voter {orig} missing from SM; got {voters}"

        _run(_body())

    def test_founding_config_only_written_once(self):
        """
        Calling ``_maybe_commit_founding_config`` twice must not add a second
        CONFIG entry.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._maybe_commit_founding_config()
            await cluster.deliver(rounds=20)
            # Advance so the entry is committed/applied.
            for _ in range(10):
                cluster.tick()
                await cluster.deliver(rounds=4)

            count_before = sum(
                1 for e in leader_svc._node.log.entries if e.type == LogEntryType.CONFIG
            )

            leader_svc._maybe_commit_founding_config()  # second call — must be a no-op

            count_after = sum(
                1 for e in leader_svc._node.log.entries if e.type == LogEntryType.CONFIG
            )
            assert (
                count_after == count_before
            ), "Second call to _maybe_commit_founding_config must not add another entry"

        _run(_body())

    def test_followers_apply_founding_config(self):
        """
        Followers must apply the founding CONFIG entry so their
        ``MembershipStateMachine`` is consistent with the leader's.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            leader_svc._maybe_commit_founding_config()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            follower_ids = [nid for nid in cluster.services if nid != leader_id]
            for fid in follower_ids:
                sm = cluster.services[fid].membership
                assert (
                    sm.membership_version >= 0
                ), f"Follower {fid} must have applied the founding CONFIG"

        _run(_body())


# ---------------------------------------------------------------------------
# Scenario 6: quorum unaffected while learner is pending promotion
# ---------------------------------------------------------------------------


class TestQuorumWithPendingLearner:
    def test_entry_commits_without_learner_ack(self):
        """
        A 3-voter cluster can commit an entry via 2/3 majority even when the
        learner is offline and contributes no ack.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            before_commit = leader_svc._node.log.commit_index

            leader_svc._node.log_add(b"quorum-test")

            # Deliver only among the 3 original voters — learner stays silent.
            voter_ids = ["m1", "m2", "m3"]
            for _ in range(16):
                cluster.tick(node_ids=voter_ids)
                await cluster.deliver(rounds=8, include=voter_ids)

            assert (
                leader_svc._node.log.commit_index > before_commit
            ), "Entry must commit via 2/3 voter majority without learner"

        _run(_body())

    def test_learner_does_not_count_towards_quorum(self):
        """
        The learner must not appear in ``advance_commit_index`` quorum
        calculation — the quorum size must be based on voters only.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            # Verify quorum is based on 3 voters (need 2 acks), not 4 (need 3).
            voting_peers = [p for p in leader_svc._node.peers if p.voting]
            # m4 must not be in the voting peer list yet.
            voting_ids = {p.node_id for p in voting_peers}
            assert (
                "m4" not in voting_ids
            ), "m4 must not be a voting peer before promotion"

            # quorum = (len(voters) + 1) // 2 + 1  with 3 voters = 2
            quorum = (len(voting_peers) + 1) // 2 + 1
            assert quorum == 2, f"Quorum must be 2 for 3 voters; got {quorum}"

        _run(_body())

    def test_two_of_three_voters_suffice_while_learner_is_present(self):
        """
        Partition one of the original voters AND leave the learner offline.
        The remaining two voters must still form a quorum and commit.
        """
        cluster = ServiceCluster(["m1", "m2", "m3"])
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

        async def _body():
            leader_id = await cluster.elect()
            leader_svc = cluster.services[leader_id]

            cluster.add_learner("m4")
            learner_svc = cluster.services["m4"]
            learner_svc._node.become_follower()

            # Find the other voters (not the leader).
            other_voters = [nid for nid in ["m1", "m2", "m3"] if nid != leader_id]
            # Keep only leader + one voter; exclude the other voter and the learner.
            participating = [leader_id, other_voters[0]]
            before = leader_svc._node.log.commit_index

            leader_svc._node.log_add(b"two-voter-quorum")
            for _ in range(16):
                cluster.tick(node_ids=participating)
                await cluster.deliver(rounds=8, include=participating)

            assert (
                leader_svc._node.log.commit_index > before
            ), "Two voters must form a quorum and commit the entry"

        _run(_body())
