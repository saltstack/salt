"""Regression tests for the ``assert_reconnect`` leak-gate opt-outs.

Pins the semantics introduced for the fault-scenario false-positive wave
(see ``agents/reports/fault_leak_calibration.md``):

  * The default gate trips on BOTH fd accumulation AND slope above
    :data:`RSS_LEAK_KB_PER_MIN` -- a real leak signal (e.g. Agent C's
    ``ping_200_concurrent`` fd+53 / ~1.8 MB) must still fail.
  * ``allow_fd_accumulation=True`` disables only the fd branch.
  * ``allow_bulk_rss=True`` disables only the bulk-RSS branch.
  * ``allow_fault_rss=True`` disables both -- the fault-work opt-out
    used by the 12 scenarios enumerated in the calibration report.

Pure-python only.  Stubs ``sample_minions`` so no docker/compose is
summoned.  Lives under ``lib/`` so the resiliency pytest.ini picks it
up.
"""

from __future__ import annotations

import pytest

from tests.resiliency.durations import (
    LEAK_BULK_RSS_KB,
    MIN_FD_DELTA_PER_MINION,
    RSS_LEAK_KB_PER_MIN,
)
from tests.resiliency.lib.topology import MinionSample, Topology


class _FakeItem:
    def __init__(self) -> None:
        self.user_properties: list = []


class _FakeSpec:
    """Minimal stand-in for :class:`TopologySpec` for the gate logic.

    ``assert_reconnect`` reads ``spec.minion_ids``, ``spec.masters``,
    ``spec.minion_containers`` -- nothing else.  Five minions is the
    cluster5 shape used by Agent C's real-leak catalogue.
    """

    def __init__(self, n_minions: int = 5) -> None:
        self.minion_ids = tuple(f"minion-{i}" for i in range(n_minions))
        self.masters = ("master-1",)
        self.minion_containers = tuple(f"c-minion-{i}" for i in range(n_minions))


def _build_topology(
    monkeypatch: pytest.MonkeyPatch,
    after_sample: MinionSample,
    n_minions: int = 5,
) -> Topology:
    """Build a Topology whose ``sample_minions`` returns ``after_sample``.

    All other side-effecting helpers are stubbed to match a successful
    first-sweep recovery so the gate decision is reached in one pass.
    """
    topology = Topology.__new__(Topology)
    topology.spec = _FakeSpec(n_minions)
    topology._workload_pgid = None

    monkeypatch.setattr(topology, "sample_minions", lambda: after_sample)
    monkeypatch.setattr(topology, "pause_workload", lambda: None)
    monkeypatch.setattr(topology, "resume_workload", lambda: None)
    monkeypatch.setattr(
        topology,
        "salt_ping_all",
        lambda master, timeout=15: {mid: True for mid in topology.spec.minion_ids},
    )
    # Settle sleep is wasted wall time in a unit test -- 2s per call
    # times every scenario -> ~20s.  Monkeypatch the sleep inside
    # topology so the gate reaches the decision immediately.
    monkeypatch.setattr("tests.resiliency.lib.topology.time.sleep", lambda s: None)
    return topology


def test_leak_gate_fails_on_real_ping_200_signature(monkeypatch):
    """Agent C's ping_200_concurrent signature (cluster5 fd+53, +1840 KB
    over a ~120s fault) must still trip the default gate.

    fd_delta=53 > MIN_FD_DELTA_PER_MINION*5=10 -> leak_fd True
    rss_per_min = 1840*60/120 = 920 > 200 -> rss_per_min gate True
    bulk gate doesn't matter since fd gate trips first
    """
    before = MinionSample(fds=0, rss_kb=0)
    after = MinionSample(fds=53, rss_kb=1840)
    topology = _build_topology(monkeypatch, after)
    item = _FakeItem()
    with pytest.raises(pytest.fail.Exception) as excinfo:
        topology.assert_reconnect(
            scenario="ping_200_concurrent",
            fault_sec=120,
            before=before,
            window_sec=30,
            item=item,
        )
    msg = str(excinfo.value)
    assert "fd_delta=53" in msg
    assert "reason=fd_accumulation" in msg


def test_allow_fault_rss_lets_fault_work_through(monkeypatch):
    """A fault scenario producing fd+30 / +4 MB over 60s -- the
    ``fs_master_srv_remount`` shape -- must PASS when
    ``allow_fault_rss=True`` is set.

    Both branches would fire at default:
      fd_delta=30 > 10 -> leak_fd True (default)
      rss_delta_kb=4000 < LEAK_BULK_RSS_KB=5000 -> leak_bulk False
    But slope 4000*60/60 = 4000 > 200.  So default would fail on fd
    branch; we check that allow_fault_rss suppresses that.
    """
    before = MinionSample(fds=0, rss_kb=0)
    after = MinionSample(fds=30, rss_kb=4000)
    topology = _build_topology(monkeypatch, after)
    item = _FakeItem()
    # Must pass (no exception) with fault_rss opt-out.
    topology.assert_reconnect(
        scenario="fs_master_srv_remount",
        fault_sec=60,
        before=before,
        window_sec=30,
        item=item,
        allow_fault_rss=True,
    )
    # And the result tuple reports a recovered outcome, not failed.
    resiliency_tuples = [v for k, v in item.user_properties if k == "resiliency"]
    assert len(resiliency_tuples) == 1
    assert resiliency_tuples[0]["outcome"] == "recovered"
    assert resiliency_tuples[0]["fd_delta"] == 30
    assert resiliency_tuples[0]["rss_kb_delta"] == 4000


def test_allow_fault_rss_does_not_help_a_real_leak(monkeypatch):
    """Even a fault test that sets ``allow_fault_rss=True`` must still
    fail reconnect if minions don't come back.  The opt-out only
    silences the RETENTION branches, not reachability.
    """
    before = MinionSample(fds=0, rss_kb=0)
    after = MinionSample(fds=0, rss_kb=0)
    topology = Topology.__new__(Topology)
    topology.spec = _FakeSpec()
    topology._workload_pgid = None
    monkeypatch.setattr(topology, "sample_minions", lambda: after)
    monkeypatch.setattr(topology, "pause_workload", lambda: None)
    monkeypatch.setattr(topology, "resume_workload", lambda: None)
    # None of the minions respond -> no coverage -> reconnect fails.
    monkeypatch.setattr(topology, "salt_ping_all", lambda master, timeout=15: {})
    monkeypatch.setattr("tests.resiliency.lib.topology.time.sleep", lambda s: None)
    # Use a very short window to make the test quick.
    monkeypatch.setattr("tests.resiliency.lib.topology.time.monotonic", _fast_time())
    item = _FakeItem()
    with pytest.raises(pytest.fail.Exception) as excinfo:
        topology.assert_reconnect(
            scenario="unreachable_post_fault",
            fault_sec=30,
            before=before,
            window_sec=5,
            item=item,
            allow_fault_rss=True,
        )
    assert "did not answer test.ping" in str(excinfo.value)


def test_allow_fd_accumulation_alone_leaves_bulk_gate_live(monkeypatch):
    """A test that only wants to waive the fd branch must still catch
    bulk retention above :data:`LEAK_BULK_RSS_KB`.
    """
    # +6 MB (above 5 MB bulk threshold) with 0 fd delta.
    before = MinionSample(fds=0, rss_kb=0)
    after = MinionSample(fds=0, rss_kb=6000)
    topology = _build_topology(monkeypatch, after)
    item = _FakeItem()
    with pytest.raises(pytest.fail.Exception) as excinfo:
        topology.assert_reconnect(
            scenario="only_fd_waived",
            fault_sec=30,
            before=before,
            window_sec=10,
            item=item,
            allow_fd_accumulation=True,
        )
    assert "reason=bulk_rss_retention" in str(excinfo.value)


def test_allow_bulk_rss_alone_leaves_fd_gate_live(monkeypatch):
    """Parity with ``allow_fd_accumulation``: ``allow_bulk_rss`` still
    trips on fd accumulation.  This pre-existed; the new flags must
    not regress it.
    """
    # fd+20 (over threshold 10 for 5 minions) with a slope that
    # also tips the per-minute gate.
    before = MinionSample(fds=0, rss_kb=0)
    after = MinionSample(fds=20, rss_kb=500)
    topology = _build_topology(monkeypatch, after)
    item = _FakeItem()
    with pytest.raises(pytest.fail.Exception) as excinfo:
        topology.assert_reconnect(
            scenario="only_bulk_waived",
            fault_sec=30,
            before=before,
            window_sec=10,
            item=item,
            allow_bulk_rss=True,
        )
    assert "reason=fd_accumulation" in str(excinfo.value)


def _fast_time():
    """Monotonic clock that advances 10s on each call -- used to drive
    the ``while time.monotonic() < deadline`` loop to its deadline in
    O(1) ticks inside reachability-failure tests.
    """
    t = [0.0]

    def _now() -> float:
        t[0] += 10.0
        return t[0]

    return _now


def test_default_threshold_still_catches_fd_at_boundary(monkeypatch):
    """Sanity: the fd gate itself fires at ``fd_delta > fd_threshold``.
    For 5 minions * MIN_FD_DELTA_PER_MINION=2, the threshold is 10.
    fd_delta=11 should trip; fd_delta=10 should not.
    """
    # fd_delta=10 -- at threshold, NOT above.
    before = MinionSample(fds=0, rss_kb=0)
    after_at = MinionSample(fds=10, rss_kb=500)
    topology_at = _build_topology(monkeypatch, after_at)
    # 500 KB / 60s * 60 = 500 KB/min > 200, slope trips.  But fd
    # delta 10 is NOT > 10.  Bulk doesn't trip.  So test should pass.
    topology_at.assert_reconnect(
        scenario="fd_at_threshold",
        fault_sec=30,
        before=before,
        window_sec=10,
        item=_FakeItem(),
    )

    # fd_delta=11 -- one above the threshold.  Slope + fd both trip.
    after_over = MinionSample(fds=11, rss_kb=500)
    topology_over = _build_topology(monkeypatch, after_over)
    with pytest.raises(pytest.fail.Exception):
        topology_over.assert_reconnect(
            scenario="fd_over_threshold",
            fault_sec=30,
            before=before,
            window_sec=10,
            item=_FakeItem(),
        )


# Reference the imported constants so the module is covered.  Env
# overrides (``RESILIENCY_RSS_LEAK_KB_PER_MIN`` etc) may shift these
# values in CI, so the test only asserts the expected relative
# ordering, not absolute defaults.
def test_constants_form_meaningful_gate():
    # A bulk-RSS retention signal must be strictly tighter (in KB)
    # than the minute-normalised slope floor -- otherwise every
    # scenario that crosses the per-minute threshold would also cross
    # the bulk threshold and the two gates would collapse.
    assert LEAK_BULK_RSS_KB > RSS_LEAK_KB_PER_MIN
    # fd threshold per minion must be a small positive int.
    assert MIN_FD_DELTA_PER_MINION >= 1
