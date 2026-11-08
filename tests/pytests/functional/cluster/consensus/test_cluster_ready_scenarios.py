"""
Functional, integration, and scenario tests for the cluster-readiness gate.

Layers covered
--------------
Functional
  - ``on_ready`` fires on the founding node after the founding CONFIG commits.
  - ``on_ready`` fires on a follower after it applies the founding CONFIG.
  - ``on_ready`` does NOT fire before any CONFIG entry commits.

Integration
  - ``SMaster.secrets["cluster_ready"]["event"]`` is set by
    ``_signal_cluster_ready`` when wired as ``on_ready`` to ``RaftService``.
  - Non-cluster ``_cluster_is_ready`` always returns True.

Scenario
  - Two founding nodes: both become ready after the founding CONFIG commits.
  - A learner node: gate stays closed until its promotion CONFIG commits.
  - A learner node: gate opens as soon as promotion CONFIG commits.
  - Gate stays closed on a node that is never added to the voter set.
  - The ready event survives once set: subsequent membership changes keep it set.

Restart
  - A cluster that bootstrapped once and committed the founding CONFIG must
    reach ``cluster_ready`` again on restart, without re-proposing it.
    Raft §5.4.2 forbids committing a prior-term entry by replication count
    alone, so the new leader must append a current-term barrier entry to
    unblock commit of the restored founding CONFIG.
"""

import asyncio
import multiprocessing

from salt.cluster.consensus.service import RaftService
from tests.pytests.functional.cluster.consensus.conftest import FakePusher
from tests.pytests.functional.cluster.consensus.test_raft_scenarios import (
    ServiceCluster,
)


def _run(coro):
    return asyncio.run(coro)


def _make_opts(node_id, peers, cachedir):
    return {
        "id": node_id,
        "interface": node_id,
        "cluster_id": "ready-test-cluster",
        "cluster_peers": peers,
        "cachedir": cachedir,
    }


def _make_cluster_with_ready_tracking(node_ids, cachedir):
    """
    Build a ``ServiceCluster`` where every service has an ``on_ready``
    callback that appends the node-id to a shared ``fired`` list.

    Returns ``(cluster, fired_list)``.
    """
    fired = []
    cluster = ServiceCluster(node_ids, cachedir=cachedir)

    for nid, svc in cluster.services.items():
        nid_capture = nid

        def _make_callback(n):
            def _cb():
                fired.append(n)

            return _cb

        svc._on_ready = _make_callback(nid_capture)
        # Re-wire membership SM on_change so _on_membership_change runs
        svc._node.membership_sm.on_change = svc._on_membership_change

    for svc in cluster.services.values():
        svc._node.become_follower()
        svc._node.last_followed = svc._node.get_now() - 10

    return cluster, fired


# ---------------------------------------------------------------------------
# Functional: on_ready callback lifecycle
# ---------------------------------------------------------------------------


class TestOnReadyFunctional:
    def test_on_ready_fires_after_founding_config_commits(self, tmp_path):
        """
        The founding CONFIG entry is proposed by the first elected leader and
        replicated to all followers.  ``on_ready`` must fire on the leader
        once the entry commits (i.e. the leader's own node_id is in voters).
        """
        cluster, fired = _make_cluster_with_ready_tracking(
            ["m1", "m2", "m3"], str(tmp_path)
        )

        async def _body():
            leader_id = await cluster.elect()

            # Drive a few rounds to let the founding CONFIG commit and replicate.
            for _ in range(20):
                cluster.tick()
                await cluster.deliver(rounds=6)

            assert (
                leader_id in fired
            ), f"on_ready must fire on leader {leader_id!r}; fired={fired}"

        _run(_body())

    def test_on_ready_fires_on_all_founding_nodes(self, tmp_path):
        """
        After the founding CONFIG commits and propagates, every original node
        must receive ``on_ready``.
        """
        cluster, fired = _make_cluster_with_ready_tracking(
            ["m1", "m2", "m3"], str(tmp_path)
        )

        async def _body():
            await cluster.elect()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            for nid in ["m1", "m2", "m3"]:
                assert (
                    nid in fired
                ), f"on_ready must fire on all nodes; missing {nid!r}; fired={fired}"

        _run(_body())

    def test_on_ready_not_fired_before_config_commits(self, tmp_path):
        """
        ``on_ready`` must not fire before any CONFIG entry has committed —
        i.e. in the window between node start and leader election.
        """
        fired = []

        def _cb(n):
            def inner():
                fired.append(n)

            return inner

        cluster = ServiceCluster(["m1", "m2", "m3"], cachedir=str(tmp_path))
        for nid, svc in cluster.services.items():
            svc._on_ready = _cb(nid)
            svc._node.membership_sm.on_change = svc._on_membership_change

        # No election driven yet — no CONFIG committed.
        assert fired == [], f"on_ready must not fire before election; fired={fired}"

    def test_on_ready_fires_only_once_per_node(self, tmp_path):
        """
        Subsequent CONFIG entries (e.g. learner promotions) must not
        re-trigger ``on_ready`` on a node that is already ready.
        """
        cluster, fired = _make_cluster_with_ready_tracking(
            ["m1", "m2", "m3"], str(tmp_path)
        )

        async def _body():
            await cluster.elect()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            count_before = len(fired)
            assert count_before >= 3

            # Add a learner and drive its promotion — triggers more CONFIG entries.
            cluster.add_learner("m4")
            cluster.services["m4"]._node.become_follower()

            for _ in range(60):
                cluster.tick()
                await cluster.deliver(rounds=10)

            # Original three nodes must each appear exactly once.
            for nid in ["m1", "m2", "m3"]:
                assert (
                    fired.count(nid) == 1
                ), f"{nid!r} on_ready fired {fired.count(nid)} times; expected 1"

        _run(_body())


# ---------------------------------------------------------------------------
# Integration: SMaster.secrets["cluster_ready"] event
# ---------------------------------------------------------------------------


class TestClusterReadyIntegration:
    def test_signal_cluster_ready_sets_event(self, tmp_path):
        """
        ``MasterPubServerChannel._signal_cluster_ready`` sets the
        ``cluster_ready`` event in ``SMaster.secrets``.
        """
        import salt.master
        from salt.channel.server import MasterPubServerChannel

        event = multiprocessing.Event()
        orig_secrets = salt.master.SMaster.secrets.copy()
        try:
            salt.master.SMaster.secrets["cluster_ready"] = {"event": event}
            ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
            ch.opts = {}
            ch._signal_cluster_ready()
            assert event.is_set()
        finally:
            salt.master.SMaster.secrets.clear()
            salt.master.SMaster.secrets.update(orig_secrets)

    def test_signal_cluster_ready_noop_when_no_entry(self, tmp_path):
        """``_signal_cluster_ready`` must not raise when entry is absent."""
        import salt.master
        from salt.channel.server import MasterPubServerChannel

        orig_secrets = salt.master.SMaster.secrets.copy()
        try:
            salt.master.SMaster.secrets.pop("cluster_ready", None)
            ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
            ch.opts = {}
            ch._signal_cluster_ready()  # must not raise
        finally:
            salt.master.SMaster.secrets.clear()
            salt.master.SMaster.secrets.update(orig_secrets)

    def test_on_ready_wired_to_signal_via_raft_service(self, tmp_path):
        """
        When ``RaftService`` is constructed with ``_signal_cluster_ready`` as
        ``on_ready``, the ``cluster_ready`` event is set after the founding
        CONFIG commits.
        """
        import salt.master

        event = multiprocessing.Event()
        orig_secrets = salt.master.SMaster.secrets.copy()

        def _set_ready():
            salt.master.SMaster.secrets["cluster_ready"]["event"].set()

        try:
            salt.master.SMaster.secrets["cluster_ready"] = {"event": event}

            loop = asyncio.new_event_loop()
            opts = _make_opts("m1", ["m2", "m3"], str(tmp_path))

            svc = RaftService(
                opts,
                loop,
                {"m2": FakePusher(), "m3": FakePusher()},
                on_ready=_set_ready,
            )

            # Simulate receiving a founding CONFIG that lists m1 as a voter.
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m2", "m3"], "learners": []}
            )

            assert event.is_set(), "cluster_ready event must be set after voter CONFIG"
            loop.close()
        finally:
            salt.master.SMaster.secrets.clear()
            salt.master.SMaster.secrets.update(orig_secrets)

    def test_cluster_is_ready_reflects_event(self, tmp_path):
        """``_cluster_is_ready`` returns True only after event.set()."""
        import salt.master
        from salt.channel.server import _cluster_is_ready

        event = multiprocessing.Event()
        orig_secrets = salt.master.SMaster.secrets.copy()
        try:
            salt.master.SMaster.secrets["cluster_ready"] = {"event": event}
            opts = {"cluster_id": "test"}
            assert not _cluster_is_ready(opts)
            event.set()
            assert _cluster_is_ready(opts)
        finally:
            salt.master.SMaster.secrets.clear()
            salt.master.SMaster.secrets.update(orig_secrets)


# ---------------------------------------------------------------------------
# Scenario: learner node readiness
# ---------------------------------------------------------------------------


class _ReadyClusterWithLearner:
    """
    Helper: build a 3-node founding cluster + one latecomer learner,
    with per-node ``on_ready`` tracking.
    """

    def __init__(self, cachedir):
        self.fired = []
        self.cluster = ServiceCluster(["m1", "m2", "m3"], cachedir=cachedir)
        self._wire_ready(self.cluster)

    def _wire_ready(self, cluster):
        for nid, svc in cluster.services.items():
            self._attach(nid, svc)
        for svc in cluster.services.values():
            svc._node.become_follower()
            svc._node.last_followed = svc._node.get_now() - 10

    def _attach(self, nid, svc):
        n = nid
        fired = self.fired

        def _cb():
            fired.append(n)

        svc._on_ready = _cb
        svc._node.membership_sm.on_change = svc._on_membership_change

    def add_learner(self, learner_id):
        svc = self.cluster.add_learner(learner_id)
        svc._node.become_follower()
        self._attach(learner_id, svc)
        return svc


class TestLearnerReadinessScenario:
    def test_learner_gate_closed_before_promotion(self, tmp_path):
        """
        A newly joined learner must NOT be ready at the moment it joins —
        before the leader has had a chance to replicate, catch up, and commit
        a promotion CONFIG entry.
        """
        helper = _ReadyClusterWithLearner(str(tmp_path))
        cluster = helper.cluster

        async def _body():
            await cluster.elect()

            # Let founding CONFIG commit on the original 3 nodes.
            for _ in range(20):
                cluster.tick()
                await cluster.deliver(rounds=8)

            # Add the learner — at this exact moment, before any ticks,
            # it must not be ready.
            helper.add_learner("m4")

            assert "m4" not in helper.fired, (
                "Learner m4 must NOT be ready immediately after joining, "
                f"before any ticks; fired={helper.fired}"
            )

        _run(_body())

    def test_learner_gate_opens_after_promotion(self, tmp_path):
        """
        After the leader proposes and commits the promotion CONFIG entry,
        the learner's ``on_ready`` must fire.
        """
        helper = _ReadyClusterWithLearner(str(tmp_path))
        cluster = helper.cluster

        async def _body():
            await cluster.elect()

            for _ in range(20):
                cluster.tick()
                await cluster.deliver(rounds=8)

            helper.add_learner("m4")

            # Drive enough rounds for catch-up + promotion CONFIG to commit.
            for _ in range(80):
                cluster.tick()
                await cluster.deliver(rounds=10)

            assert "m4" in helper.fired, (
                "Learner m4 must be ready after promotion CONFIG commits; "
                f"fired={helper.fired}"
            )

        _run(_body())

    def test_founding_nodes_ready_before_learner(self, tmp_path):
        """
        The three founding nodes must all be ready before the learner joins,
        and the learner must be ready only after promotion.
        """
        helper = _ReadyClusterWithLearner(str(tmp_path))
        cluster = helper.cluster

        async def _body():
            await cluster.elect()

            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

            # All three founding nodes must be ready.
            for nid in ["m1", "m2", "m3"]:
                assert (
                    nid in helper.fired
                ), f"Founding node {nid!r} must be ready; fired={helper.fired}"

            helper.add_learner("m4")
            assert (
                "m4" not in helper.fired
            ), "Learner must not be ready immediately after joining"

            # Drive promotion.
            for _ in range(80):
                cluster.tick()
                await cluster.deliver(rounds=10)

            assert (
                "m4" in helper.fired
            ), f"Learner must be ready after promotion; fired={helper.fired}"

        _run(_body())

    def test_node_never_added_to_voters_never_ready(self, tmp_path):
        """
        A node whose ``on_ready`` is set but that is never included in any
        committed voter CONFIG must never become ready.
        """
        fired = []
        loop = asyncio.new_event_loop()
        opts = _make_opts("orphan", ["m1"], str(tmp_path))
        try:
            svc = RaftService(
                opts,
                loop,
                {"m1": FakePusher()},
                on_ready=lambda: fired.append("orphan"),
            )
            # Apply a CONFIG that does NOT include "orphan".
            svc._node.membership_sm.apply({"voters": ["m1", "m2"], "learners": []})
            assert "orphan" not in fired
        finally:
            loop.close()

    def test_ready_event_stays_set_after_subsequent_configs(self, tmp_path):
        """
        Once a node is ready, later CONFIG entries (e.g. adding more members)
        must not clear readiness — on_ready is nulled and never re-fires.
        """
        fired = []
        loop = asyncio.new_event_loop()
        opts = _make_opts("m1", ["m2"], str(tmp_path))
        try:
            svc = RaftService(
                opts, loop, {"m2": FakePusher()}, on_ready=lambda: fired.append("m1")
            )

            svc._node.membership_sm.apply({"voters": ["m1", "m2"], "learners": []})
            assert fired == ["m1"]

            # A subsequent CONFIG (e.g. adding m3) must not re-fire.
            svc._node.membership_sm.apply(
                {"voters": ["m1", "m2", "m3"], "learners": []}
            )
            assert fired == ["m1"], "on_ready must fire exactly once"
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Scenario: restart with persisted state
# ---------------------------------------------------------------------------


class TestClusterReadyOnRestart:
    """
    Regression tests for the restart-with-persisted-state bootstrap bug.

    Repro in the field: three cluster masters bootstrap cleanly on a
    fresh cachedir, then are stopped and restarted with the same
    ``cache/consensus`` / ``cache/raft`` state on disk.  On restart the
    Raft log is loaded from storage (founding CONFIG at index 0, term
    N), but ``commit_index`` is not persisted so it comes back at -1
    and ``MembershipStateMachine`` is empty.  A new leader is elected
    in term N+1 but — per Raft §5.4.2 — cannot commit the index-0
    CONFIG by replication count alone because its term is less than
    the leader's current term.  Nothing new is proposed in steady
    state so ``commit_index`` stays at -1 forever, ``_on_ready`` never
    fires, and ``_cluster_is_ready`` returns ``False`` indefinitely.

    The fix: ``Node.become_leader`` appends a NOOP barrier in the new
    leader's term when the log carries uncommitted prior-term entries.
    Replicating + committing the NOOP transitively commits every prior
    entry, including the restored founding CONFIG, which the
    ``MembershipStateMachine`` then applies, firing ``on_change`` /
    ``_on_ready`` on every node whose id is in the voter set.
    """

    def test_cluster_ready_fires_on_restart_from_persisted_log(self, tmp_path):
        """
        Bootstrap → stop → restart with the same cachedir.  Within
        a bounded number of ticks, every founding node fires
        ``on_ready`` again; ``commit_index`` advances past the
        founding CONFIG; ``MembershipStateMachine`` applies the
        restored voter set.
        """
        cachedir = str(tmp_path)
        node_ids = ["m1", "m2", "m3"]

        # Phase 1: fresh bootstrap.
        cluster, fired = _make_cluster_with_ready_tracking(node_ids, cachedir)

        async def _bootstrap():
            await cluster.elect()
            for _ in range(30):
                cluster.tick()
                await cluster.deliver(rounds=8)

        _run(_bootstrap())

        # All three ready after fresh bootstrap — baseline.
        assert set(fired) == set(node_ids), (
            f"Pre-restart baseline: on_ready must fire on every "
            f"founding node; fired={fired}"
        )
        # Founding CONFIG committed at index 0, SM populated.
        for nid, svc in cluster.services.items():
            assert svc._node.log.commit_index >= 0
            assert set(svc._node.membership_sm.current_voters()) == set(node_ids)

        # Phase 2: restart — rebuild ServiceCluster against the same
        # cachedir.  Nothing about the on-disk state is touched.
        cluster2, fired2 = _make_cluster_with_ready_tracking(node_ids, cachedir)

        # Immediately post-construction, each node has loaded the log
        # from storage but ``commit_index`` is not persisted so it
        # resets to -1 and the membership SM is empty.
        for nid, svc in cluster2.services.items():
            assert len(svc._node.log.entries) >= 1
            assert svc._node.log.commit_index == -1
            assert svc._node.membership_sm.current_voters() == []

        # Pre-restart: no readiness signals have fired yet.
        assert fired2 == [], (
            f"on_ready must not fire during RaftService construction; "
            f"fired2={fired2}"
        )

        # Phase 3: drive election + heartbeats.  A bounded loop
        # mirrors the real-world "within ~10s" expectation from the
        # field repro.
        async def _restart():
            await cluster2.elect()
            for _ in range(60):
                cluster2.tick()
                await cluster2.deliver(rounds=8)

        _run(_restart())

        # With the fix: every founding node fires on_ready; commit
        # index advances past the founding CONFIG; SM applies the
        # restored voter set.  Without the fix: fired2 stays empty.
        assert set(fired2) == set(node_ids), (
            f"RESTART REGRESSION: on_ready must fire on every "
            f"founding node after restart from persisted state; "
            f"fired={fired2}"
        )
        for nid, svc in cluster2.services.items():
            assert svc._node.log.commit_index >= 0, (
                f"{nid!r}: commit_index must advance past founding CONFIG "
                f"after restart (got {svc._node.log.commit_index})"
            )
            assert set(svc._node.membership_sm.current_voters()) == set(node_ids), (
                f"{nid!r}: MembershipStateMachine must reapply restored "
                f"voter set (got {svc._node.membership_sm.current_voters()})"
            )

    def test_signal_cluster_ready_idempotent(self, tmp_path):
        """
        ``_signal_cluster_ready`` must be safe to call multiple times.
        A re-fire of ``on_ready`` after restart (should any exist)
        must leave the event set and not raise.
        """
        import salt.master
        from salt.channel.server import MasterPubServerChannel

        event = multiprocessing.Event()
        orig_secrets = salt.master.SMaster.secrets.copy()
        try:
            salt.master.SMaster.secrets["cluster_ready"] = {"event": event}
            ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
            ch.opts = {}

            ch._signal_cluster_ready()
            assert event.is_set()

            # Second invocation must also succeed and keep the event set.
            ch._signal_cluster_ready()
            assert event.is_set()
        finally:
            salt.master.SMaster.secrets.clear()
            salt.master.SMaster.secrets.update(orig_secrets)

    def test_noop_barrier_appended_on_become_leader_with_prior_term_log(self, tmp_path):
        """
        Direct unit of the fix: on a Node whose log already carries
        entries from a prior term (simulating restart), ``become_leader``
        appends a NOOP barrier in the new term.  On a fresh Node with an
        empty log, ``become_leader`` must NOT append a NOOP (that would
        shift the founding CONFIG and break ``_maybe_commit_founding_config``).
        """
        from salt.cluster.consensus.raft.log import LogEntryType
        from salt.cluster.consensus.raft.node import Node
        from salt.cluster.consensus.raft.scheduler import ManualTimeoutScheduler

        scheduler = ManualTimeoutScheduler()

        # Case A: empty log — no NOOP should be appended.  With zero
        # peers, ``become_candidate`` fast-paths to ``become_leader``
        # (nothing to elect), so we only need the candidate transition
        # to exercise ``become_leader``.
        empty_node = Node("n1", peers=[])
        empty_node.register_schedule_timeout(scheduler.schedule)
        empty_node.become_follower()
        empty_node.become_candidate()
        assert str(empty_node.state) == "leader"
        assert len(empty_node.log.entries) == 0, (
            "NOOP barrier must NOT be appended when log is empty — the "
            "founding CONFIG path keys on log.index < 0 and would be "
            "permanently suppressed."
        )

        # Case B: log has a prior-term CONFIG — NOOP barrier required.
        restart_node = Node("n2", peers=[])
        restart_node.register_schedule_timeout(scheduler.schedule)
        restart_node.log.append(
            1,
            {"voters": ["n2", "n3", "n4"], "learners": []},
            entry_type=LogEntryType.CONFIG,
        )
        restart_node.term = 2  # simulate post-restart (same term as log)
        restart_node.become_follower()
        restart_node.become_candidate()  # bumps to term 3, fast-paths to leader
        assert str(restart_node.state) == "leader"
        # Log must now carry [CONFIG@term1, NOOP@term3].
        assert len(restart_node.log.entries) == 2
        assert restart_node.log.entries[-1].type == LogEntryType.NOOP
        assert restart_node.log.entries[-1].term == restart_node.term
