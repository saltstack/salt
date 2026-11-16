"""Regression tests for the resiliency ``user_properties`` stash merge.

Earlier, two write paths disagreed:

  * ``conftest.stash_result`` merged into the first ``"resiliency"``
    tuple;
  * ``Topology._stash_result`` unconditionally APPENDED a new tuple,
    and ``_extract_stash`` returned the FIRST tuple.

A scenario that seeded partial fields via ``stash_result`` (outcome +
notes) then let ``assert_reconnect`` append the real deltas via
``Topology._stash_result`` wrote TWO tuples; the real deltas lost to
the partial seed and ``results.jsonl`` carried a default-sentinel row
(``fd_delta=0 rss_kb_delta=0``) even though ``pytest.fail`` had the
real numbers.

These tests pin:
  1. ``Topology._stash_result`` merges into any existing tuple (parity
     with ``stash_result``);
  2. ``_extract_stash`` merges every ``"resiliency"`` tuple, keeping a
     ``failed`` outcome sticky even if a later write downgrades it;
  3. ``_skipped_for_topology`` continues to read the separate
     ``"resiliency_skipped_for_topology"`` key.

Pure-python only -- no docker, no compose.  Lives under ``lib/`` so
the resiliency pytest.ini picks it up, but takes no fixtures that
would summon the compose stack.
"""

from __future__ import annotations

from tests.resiliency import conftest
from tests.resiliency.lib.topology import Topology


class _FakeItem:
    """Minimal stand-in for ``pytest.Item`` -- the stash helpers only
    poke ``user_properties``.
    """

    def __init__(self) -> None:
        self.user_properties: list = []


def test_topology_stash_merges_into_existing_tuple():
    """A prior partial seed from ``stash_result`` must be merged over,
    not shadowed by a second appended tuple.
    """
    item = _FakeItem()
    conftest.stash_result(
        item,
        scenario="leak_check",
        outcome="failed",
        fault_seconds=10,
        notes="pre-seed",
    )
    Topology._stash_result(
        item,
        scenario="leak_check",
        outcome="failed",
        reconnect_seconds=-1,
        attempts=4,
        missing=["minion-c"],
        fd_delta=53,
        rss_kb_delta=1840,
        fault_seconds=10,
        notes="rss_kb_per_min=900 threshold=200",
    )
    resiliency_tuples = [v for k, v in item.user_properties if k == "resiliency"]
    assert len(resiliency_tuples) == 1, resiliency_tuples
    merged = resiliency_tuples[0]
    assert merged["fd_delta"] == 53
    assert merged["rss_kb_delta"] == 1840
    assert merged["outcome"] == "failed"
    assert merged["missing"] == ["minion-c"]


def test_extract_stash_merges_stray_duplicate_tuples():
    """If some future writer bypasses the helpers and appends a raw
    duplicate tuple, ``_extract_stash`` still rolls them up.
    """
    item = _FakeItem()
    item.user_properties.append(
        (
            "resiliency",
            {
                "scenario": "s",
                "outcome": "failed",
                "fd_delta": 7,
                "rss_kb_delta": 50,
            },
        )
    )
    item.user_properties.append(
        (
            "resiliency",
            {
                "scenario": "s",
                "outcome": "recovered",
                "fd_delta": 0,
                "rss_kb_delta": 0,
            },
        )
    )
    merged = conftest._extract_stash(item)
    # "failed" is sticky -- a later "recovered" must not overwrite it.
    assert merged["outcome"] == "failed"
    # Non-outcome fields follow last-writer-wins so a progress-updating
    # caller can refine the row.
    assert merged["fd_delta"] == 0
    assert merged["rss_kb_delta"] == 0


def test_extract_stash_handles_single_assert_reconnect_write():
    """The common path (pure ``assert_reconnect`` test, no prior seed)
    must still produce the exact dict assert_reconnect wrote.
    """
    item = _FakeItem()
    Topology._stash_result(
        item,
        scenario="ping_200",
        outcome="recovered",
        reconnect_seconds=7,
        attempts=3,
        missing=[],
        fd_delta=11,
        rss_kb_delta=222,
        fault_seconds=5,
        notes="ok",
    )
    merged = conftest._extract_stash(item)
    assert merged == {
        "scenario": "ping_200",
        "outcome": "recovered",
        "reconnect_seconds": 7,
        "attempts": 3,
        "missing": [],
        "fd_delta": 11,
        "rss_kb_delta": 222,
        "fault_seconds": 5,
        "notes": "ok",
    }


def test_extract_stash_empty_when_nothing_stashed():
    assert conftest._extract_stash(_FakeItem()) == {}


def test_skipped_for_topology_uses_separate_key():
    """The topology-skip marker lives under its own key and must not
    collide with the resiliency-row stash.
    """
    item = _FakeItem()
    item.user_properties.append(("resiliency_skipped_for_topology", True))
    assert conftest._skipped_for_topology(item) is True
    # And the resiliency stash stays empty so _extract_stash short-
    # circuits to defaults, not to a partial row.
    assert conftest._extract_stash(item) == {}


def test_stash_result_merges_when_prior_dict_present():
    """``conftest.stash_result`` keeps its original merge-into-first
    semantics so an ``assert_reconnect`` seed followed by a scenario
    refinement collapses into one row.
    """
    item = _FakeItem()
    Topology._stash_result(
        item,
        scenario="x",
        outcome="recovered",
        fd_delta=4,
        rss_kb_delta=12,
    )
    conftest.stash_result(item, notes="post-refine", fd_delta=5)
    resiliency_tuples = [v for k, v in item.user_properties if k == "resiliency"]
    assert len(resiliency_tuples) == 1
    merged = resiliency_tuples[0]
    assert merged["fd_delta"] == 5  # later write wins
    assert merged["rss_kb_delta"] == 12  # untouched
    assert merged["notes"] == "post-refine"
    assert merged["outcome"] == "recovered"


# ---------------------------------------------------------------------------
# Hook-phase gating: results.jsonl must not be seeded by passing setup
# ---------------------------------------------------------------------------
#
# The call phase is the only phase whose user_properties stash reflects
# a scenario's real verdict -- ``assert_reconnect`` runs in the test
# body, so setup phase sees an empty stash.  Earlier the
# ``pytest_runtest_makereport`` hook fired for any ``report.when ==
# "setup"`` with ``report.passed == True`` and wrote an empty-sentinel
# row with ``outcome="recovered"`` before the call phase ran.  That row
# pinned ``_resiliency_recorded = True``; the call-phase hook then
# early-returned and the real deltas / pytest.fail verdict silently
# dropped.
#
# These tests pin: passing setup NEVER writes; failing setup DOES write
# (a fixture explosion must still surface as ``setup_error``); the call
# phase is the sole writer for a test whose setup passed.


class _FakeReport:
    def __init__(
        self,
        when,
        passed=False,
        failed=False,
        skipped=False,
        longreprtext="",
    ):
        self.when = when
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.longreprtext = longreprtext


class _FakePytestItem:
    """Pytest item with the attribute surface the hook touches."""

    def __init__(self, nodeid="tests/resiliency/test_x.py::test_y"):
        self.nodeid = nodeid
        self.user_properties: list = []
        self._closest_markers: dict = {}

    def get_closest_marker(self, name):
        return self._closest_markers.get(name)


def _run_hook_for_report(item, report, written_rows):
    """Invoke ``pytest_runtest_makereport``'s body for ``report``.

    The real hook is a ``hookwrapper`` so it yields to an outcome.  We
    simulate the outcome by patching ``_append_jsonl_row`` to capture
    rows into ``written_rows``.  The hook also reads
    ``os.environ["TOPOLOGY"]``; set it before calling.
    """

    # Replace _append_jsonl_row so we don't need RESULTS_FILE / disk.
    original = conftest._append_jsonl_row
    conftest._append_jsonl_row = written_rows.append
    try:
        # Mimic the hookwrapper plumbing: run the generator manually.
        # ``outcome.get_result()`` returns the ``report`` we feed it.
        class _FakeOutcome:
            def get_result(self):
                return report

        gen = conftest.pytest_runtest_makereport(item, call=None)
        try:
            next(gen)  # advance past the ``outcome = yield``
        except StopIteration:
            return
        try:
            gen.send(_FakeOutcome())
        except StopIteration:
            pass
    finally:
        conftest._append_jsonl_row = original


def test_hook_does_not_emit_row_on_passing_setup(monkeypatch):
    """A passing setup phase MUST NOT write a row.

    Writing here would pin the row to an empty-sentinel
    ``recovered`` + fd_delta=0 + rss_kb_delta=0 and set
    ``_resiliency_recorded = True`` so the call-phase hook would
    early-return -- silently dropping the real
    ``assert_reconnect`` verdict and deltas.
    """
    monkeypatch.setenv("TOPOLOGY", "single")
    item = _FakePytestItem()
    written: list = []
    _run_hook_for_report(item, _FakeReport("setup", passed=True), written)
    assert written == []
    assert not getattr(item, "_resiliency_recorded", False)


def test_hook_emits_setup_error_row_on_setup_failure(monkeypatch):
    """A fixture explosion (failed setup) MUST write a ``setup_error``
    row so the harness doesn't silently swallow it.
    """
    monkeypatch.setenv("TOPOLOGY", "single")
    item = _FakePytestItem()
    written: list = []
    _run_hook_for_report(
        item,
        _FakeReport("setup", failed=True, longreprtext="boom: fixture blew up"),
        written,
    )
    assert len(written) == 1
    assert written[0]["outcome"] == "setup_error"
    assert item._resiliency_recorded is True


def test_hook_emits_real_deltas_on_call_phase(monkeypatch):
    """The call-phase hook is the sole writer when setup passed.

    After ``assert_reconnect`` has populated the stash with real
    deltas, the call-phase hook rolls them into ``results.jsonl``
    with the correct outcome.
    """
    monkeypatch.setenv("TOPOLOGY", "single")
    item = _FakePytestItem()
    # Simulate passing setup: hook returns without writing.
    pre: list = []
    _run_hook_for_report(item, _FakeReport("setup", passed=True), pre)
    assert pre == []

    # Scenario's call body fires assert_reconnect which stashes real fields.
    Topology._stash_result(
        item,
        scenario="leak_check",
        outcome="failed",
        reconnect_seconds=5,
        attempts=2,
        missing=[],
        fd_delta=66,
        rss_kb_delta=628,
        fault_seconds=90,
        notes="rss_kb_per_min=418 threshold=200 reason=fd_accumulation",
    )

    # Call phase fires with report.failed=True (pytest.fail was raised).
    written: list = []
    _run_hook_for_report(
        item,
        _FakeReport("call", failed=True, longreprtext="Failed: ..."),
        written,
    )
    assert len(written) == 1
    row = written[0]
    assert row["scenario"] == "leak_check"
    assert row["outcome"] == "failed"
    assert row["fd_delta"] == 66
    assert row["rss_kb_delta"] == 628
    assert "fd_accumulation" in row["notes"]
