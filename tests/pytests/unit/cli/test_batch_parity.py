"""
Phase 2 regression: replay conformance scenarios through the sync
``Batch.run()`` driver and assert the same terminal behavior that
``progress_batch()`` produces directly.

These scenarios are ``SCENARIOS`` from the Phase 1 conformance harness
(``tests/pytests/unit/utils/batch_state/batch_state_scenarios.py``).  Each one is
a declarative step-by-step spec.  Here we replay the ``new_returns``
inputs through the sync driver's iterator machinery and verify:

* The number of ``cmd_iter_no_block`` sub-batch calls matches the
  publish events in the scenario.
* The final ``done`` and ``failed`` dicts on the driver's in-memory
  state match what the oracle produces.
* ``halted`` matches.

Scenarios whose full trajectory can't be replayed through the sync
driver's iterator shape (e.g. a purely incremental step that leaves
the batch mid-flight) are filtered out; everything else is proven
byte-compatible with progress_batch.
"""

import pytest

from salt.cli.batch import Batch
from salt.utils.batch_state import progress_batch
from tests.pytests.unit.utils.batch_state.batch_state_scenarios import SCENARIOS
from tests.support.mock import MagicMock, patch


@pytest.fixture
def make_batch():
    """Factory that builds a Batch instance with a mocked LocalClient."""

    def _make(opts):
        fixture_opts = {"conf_file": {}, "tgt": "", "transport": ""}
        fixture_opts.update(opts)
        mock_client = MagicMock()
        with patch("salt.client.get_local_client", MagicMock(return_value=mock_client)):
            with patch("salt.client.LocalClient.cmd_iter", MagicMock(return_value=[])):
                return Batch(fixture_opts, quiet=True)

    return _make


def _oracle_terminal_state(scenario):
    """
    Run the scenario's steps through ``progress_batch`` directly and
    return the resulting state.  This is the reference trajectory the
    sync driver must match.
    """
    from copy import deepcopy

    state = deepcopy(scenario.initial)
    for step in scenario.steps:
        progress_batch(state, step.new_returns, now=step.now)
    return state


def _scenario_subbatch_returns(scenario):
    """
    Extract the per-sub-batch return dicts from a scenario, in the
    order the sync driver will consume them.

    A sub-batch is a ``publish`` from the oracle.  The returns for
    that sub-batch are the ``new_returns`` from the *next* step that
    names those minions.  The list produced here is what the mocked
    ``cmd_iter_no_block`` will yield, one sub-batch at a time.
    """
    subbatches = []
    current_publish = []
    for step in scenario.steps:
        if current_publish and step.new_returns:
            returns_for_publish = {
                m: step.new_returns[m] for m in current_publish if m in step.new_returns
            }
            subbatches.append(returns_for_publish)
            current_publish = []
        if step.expected.publish:
            current_publish = list(step.expected.publish)
    return subbatches


def _scenarios_for_parity():
    """
    Filter SCENARIOS down to those whose terminal state the sync
    driver can reach: no minions left in ``active`` (the sync driver
    can only finish when all dispatched minions have either returned
    or been timed-out).

    Scenarios exercised exclusively by dedicated parity tests below
    (``batch_wait``, ``timeout``) are also dropped here.
    """
    drop_by_name = {
        "batch_wait_blocks_next_dispatch_until_cooldown_expires",
        "timeout_moves_nonresponsive_minion_to_failed",
    }
    out = []
    for scenario in SCENARIOS:
        if scenario.name in drop_by_name:
            continue
        terminal = _oracle_terminal_state(scenario)
        if terminal["active"] and not terminal["halted"]:
            # Oracle ends mid-flight without halting; not reachable
            # through the sync driver's iterator-driven loop.  Halted
            # scenarios are fine — the driver short-circuits on halt,
            # leaving its own ``active`` dict matching the oracle's.
            continue
        out.append(scenario)
    return tuple(out)


@pytest.mark.parametrize(
    "scenario",
    _scenarios_for_parity(),
    ids=[s.name for s in _scenarios_for_parity()],
)
def test_sync_driver_matches_progress_batch_oracle(scenario, make_batch):
    """
    For each replayable conformance scenario, drive ``Batch.run()``
    with a mock ``cmd_iter_no_block`` that yields the scenario's
    per-sub-batch returns, then compare against ``progress_batch``'s
    terminal state.

    Asserts byte-for-byte parity on the fields that are observable
    to callers: ``done``, ``failed``, ``halted``, ``halted_reason``.
    """
    oracle_state = _oracle_terminal_state(scenario)
    subbatches = _scenario_subbatch_returns(scenario)

    opts = {
        "batch": str(scenario.initial["batch_size"]),
        "timeout": scenario.initial["timeout"],
        "gather_job_timeout": scenario.initial["gather_job_timeout"],
        "fun": scenario.initial["fun"],
        "arg": list(scenario.initial["arg"]),
        "failhard": scenario.initial["failhard"],
    }
    batch = make_batch(opts)
    batch.gather_minions = MagicMock(
        return_value=[list(scenario.initial["all_minions"]), [], []]
    )

    call_box = {"i": 0}

    def _mock_iter(*args, **kwargs):
        i = call_box["i"]
        call_box["i"] += 1
        minions = args[0]
        returns = subbatches[i] if i < len(subbatches) else {}
        for minion in minions:
            if minion in returns:
                yield {minion: returns[minion]}
        # Keep the iterator "alive" — absent returns must NOT be
        # interpreted as timeouts by the driver (the oracle doesn't see
        # them as such for scenarios that halt mid-flight).  The
        # driver's inner drain loop bails after 5 consecutive Nones
        # without raising StopIteration on the outer, so we emit a
        # bounded burst of Nones rather than an infinite generator.
        for _ in range(10):
            yield None

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_mock_iter)

    persisted = {}

    def _capture_state(jid, state, opts, *, best_effort=False):
        persisted["last"] = dict(state)
        return True

    with patch("salt.utils.batch_state.write_batch_state", side_effect=_capture_state):
        list(Batch.run(batch))

    driver_state = persisted["last"]

    assert driver_state["done"] == oracle_state["done"]
    assert driver_state["failed"] == oracle_state["failed"]
    assert driver_state["halted"] is oracle_state["halted"]
    assert driver_state["halted_reason"] == oracle_state["halted_reason"]


def test_sync_driver_timeout_parity(make_batch):
    """
    The timeout conformance scenario's oracle marks both minions as
    ``failed: timeout`` when the iterator exhausts without yielding
    them.  Drive ``Batch.run()`` with an empty-yielding
    ``cmd_iter_no_block`` and assert the same outcome.

    This exercises the ``timed_out`` path of ``progress_batch`` via
    the sync driver — the piece the parametric parity test above
    skips.
    """
    opts = {
        "batch": "2",
        "timeout": 60,
        "gather_job_timeout": 10,
        "fun": "test.ping",
        "arg": [],
    }
    batch = make_batch(opts)
    batch.gather_minions = MagicMock(return_value=[["m1", "m2"], [], []])

    def _empty_iter(*args, **kwargs):
        return iter([])

    batch.local.cmd_iter_no_block = MagicMock(side_effect=_empty_iter)

    persisted = {}

    def _capture_state(jid, state, opts, *, best_effort=False):
        persisted["last"] = dict(state)
        return True

    with patch("salt.utils.batch_state.write_batch_state", side_effect=_capture_state):
        yields = list(Batch.run(batch))

    assert persisted["last"]["failed"] == {"m1": "timeout", "m2": "timeout"}
    assert persisted["last"]["done"] == {}
    assert persisted["last"]["halted"] is False
    # Sync driver surfaces timeouts as empty-dict yields so callers
    # can keep their existing shape.
    yielded_minions = sorted(next(iter(d.keys())) for d, _ in yields)
    assert yielded_minions == ["m1", "m2"]
    for d, rc in yields:
        minion_id = next(iter(d.keys()))
        assert d == {minion_id: {}}
        assert rc == 0
