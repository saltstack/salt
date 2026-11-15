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
