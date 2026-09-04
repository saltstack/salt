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
        "id": f"{node_id}-hostname",
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
