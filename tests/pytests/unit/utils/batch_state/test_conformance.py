"""
Conformance harness for :mod:`salt.utils.batch_state`.

The scenarios in :mod:`._scenarios` are the behavioral specification
for :func:`salt.utils.batch_state.progress_batch`.  This module runs
them.

Until Phase 1 step 1 lands an implementation of ``progress_batch``,
the parametrized :func:`test_scenario` runs are marked ``xfail``.
Removing the mark is the signal that Phase 1 step 1 is complete.

The two non-parametrized tests
(:func:`test_scenarios_unique_names` and
:func:`test_scenarios_cover_real_tests`) run today and guard against
sloppy scenario drift: duplicate names, and ``covers`` references that
point at sync-batch tests that no longer exist.
"""

import importlib

import pytest

from salt.utils.batch_state import progress_batch
from tests.pytests.unit.utils.batch_state._scenarios import SCENARIOS

SYNC_TEST_MODULE = "tests.pytests.unit.cli.test_batch"


def _resolve_sync_test(test_id):
    """
    Resolve a sync-batch test id to an attribute of the sync-batch
    test module.  Returns ``None`` if the id does not exist, so the
    caller can produce a useful assertion message.
    """
    mod = importlib.import_module(SYNC_TEST_MODULE)
    return getattr(mod, test_id, None)


def test_scenarios_unique_names():
    """Every scenario has a unique name — parametrize ids must be distinct."""
    names = [s.name for s in SCENARIOS]
    assert len(names) == len(set(names)), f"duplicate scenario name(s) in {names}"


def test_scenarios_cover_real_tests():
    """
    Every ``covers`` reference resolves to a real sync-batch test.
    Catches scenario-to-sync-test drift at collection time instead of
    during a frantic review of Phase 2.
    """
    missing = []
    for scenario in SCENARIOS:
        for test_id in scenario.covers:
            if _resolve_sync_test(test_id) is None:
                missing.append((scenario.name, test_id))
    assert not missing, (
        "Scenarios reference sync-batch tests that no longer exist: " f"{missing}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_scenario(scenario):
    """
    Replay a scenario through progress_batch, asserting the returned
    Action and any requested post-call state fields.
    """
    state = scenario.initial
    for step_index, step in enumerate(scenario.steps):
        action = progress_batch(state, step.new_returns, now=step.now)
        assert action == step.expected, (
            f"scenario {scenario.name!r}, step {step_index}: action mismatch\n"
            f"  expected: {step.expected}\n"
            f"  got:      {action}"
        )
        for field, expected_value in step.state_after.items():
            assert state[field] == expected_value, (
                f"scenario {scenario.name!r}, step {step_index}: "
                f"state[{field!r}] mismatch\n"
                f"  expected: {expected_value}\n"
                f"  got:      {state[field]}"
            )
