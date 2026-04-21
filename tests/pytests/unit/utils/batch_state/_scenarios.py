"""
Conformance scenarios for ``salt.utils.batch_state.progress_batch``.

Each :class:`Scenario` is a declarative spec: an initial BatchState
dict plus an ordered sequence of :class:`Step` s.  A Step captures one
call into :func:`progress_batch`: the ``new_returns`` passed in, the
``now`` clock value, the :class:`Action` it should return, and
optional post-call state assertions on specific BatchState fields.

Scenarios live in their own module so they can be consumed by more
than one test suite — the Phase 1 conformance runner here, and (in
Phase 2) the same scenarios replayed against the refactored sync
driver to prove behavioral parity.

Conventions
-----------

* Minion ids are ``m1``, ``m2``, ... in the order they appear in
  ``all_minions``.  Scenarios assume FIFO dispatch (the first minion
  in ``pending`` is the first to go out).
* ``_ret()`` builds a minimal realistic return payload.  Scenarios
  that care about specific return fields (retcode dicts, failed flags)
  pass them explicitly.
* ``covers`` lists ids of existing sync-batch unit tests whose
  behavior this scenario mirrors.  The harness verifies each id
  resolves so renamed sync tests can't silently unmoor a scenario.
"""

import dataclasses

from salt.utils.batch_state import Action


def make_state(
    *,
    minions,
    batch_size,
    batch_wait=0,
    timeout=60,
    gather_job_timeout=10,
    failhard=False,
    fun="test.ping",
    arg=None,
    tgt="*",
    tgt_type="glob",
    driver="master",
    jid="20260101000000000000",
    created=0.0,
    user="root",
):
    """
    Build a fresh BatchState dict for use as a scenario's ``initial``.

    Deliberately verbose: one factory, all fields visible, so a reader
    of a scenario never has to guess what the default state looks like.
    """
    return {
        "jid": jid,
        "all_minions": list(minions),
        "pending": list(minions),
        "active": {},
        "done": {},
        "failed": {},
        "wait": [],
        "batch_size": batch_size,
        "fun": fun,
        "arg": list(arg or []),
        "kwargs": {},
        "tgt": tgt,
        "tgt_type": tgt_type,
        "failhard": failhard,
        "batch_wait": batch_wait,
        "timeout": timeout,
        "gather_job_timeout": gather_job_timeout,
        "last_progress": created,
        "created": created,
        "halted": False,
        "halted_reason": None,
        "driver": driver,
        "ret": "",
        "user": user,
    }


def _ret(value=True, retcode=0, **extra):
    """Build a realistic minion-return payload."""
    return {"ret": value, "retcode": retcode, **extra}


@dataclasses.dataclass(frozen=True)
class Step:
    """
    One call into :func:`salt.utils.batch_state.progress_batch`.

    ``new_returns`` and ``now`` map directly to the function's
    arguments.  ``expected`` is the :class:`Action` the call must
    return.  ``state_after`` is a dict of BatchState field names to
    their expected post-call values — list only the fields that are
    the point of the scenario; unlisted fields are not asserted.
    """

    expected: Action
    now: float = 0.0
    new_returns: dict = dataclasses.field(default_factory=dict)
    state_after: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Scenario:
    """Declarative conformance scenario."""

    name: str
    description: str
    initial: dict
    steps: tuple
    covers: tuple = ()


# ---------------------------------------------------------------------------
# Seed scenarios.  Each one is intentionally small and focused on a single
# behavior.  When progress_batch() lands in Phase 1 step 1 these become its
# executable specification.
# ---------------------------------------------------------------------------

SCENARIOS = (
    Scenario(
        name="initial_dispatch_fills_first_sub_batch",
        description=(
            "First call with no new returns publishes the first batch_size "
            "minions and records their dispatch timestamps in active."
        ),
        initial=make_state(
            minions=["m1", "m2", "m3", "m4"],
            batch_size=2,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": ["m3", "m4"],
                    "active": {"m1": 1.0, "m2": 1.0},
                    "done": {},
                    "failed": {},
                    "halted": False,
                },
            ),
        ),
        covers=("test_single_jid_across_batch_iterations",),
    ),
    Scenario(
        name="subsequent_dispatch_fills_next_sub_batch",
        description=(
            "When the active slots return, progress_batch moves them to "
            "done and dispatches the next pending minions in the same call."
        ),
        initial=make_state(
            minions=["m1", "m2", "m3", "m4"],
            batch_size=2,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=2.0,
                new_returns={"m1": _ret(), "m2": _ret()},
                expected=Action(
                    publish=["m3", "m4"],
                    finished_minions={"m1": _ret(), "m2": _ret()},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": [],
                    "active": {"m3": 2.0, "m4": 2.0},
                    "done": {"m1": _ret(), "m2": _ret()},
                },
            ),
        ),
        covers=("test_single_jid_across_batch_iterations",),
    ),
    Scenario(
        name="last_partial_sub_batch_dispatches_all_remaining",
        description=(
            "When fewer minions remain than batch_size, progress_batch "
            "dispatches everything that's left in one call."
        ),
        initial=make_state(
            minions=["m1", "m2", "m3"],
            batch_size=2,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=2.0,
                new_returns={"m1": _ret(), "m2": _ret()},
                expected=Action(
                    publish=["m3"],
                    finished_minions={"m1": _ret(), "m2": _ret()},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": [],
                    "active": {"m3": 2.0},
                },
            ),
        ),
    ),
    Scenario(
        name="failhard_on_nonzero_retcode_halts_dispatch",
        description=(
            "With failhard=True, a return whose retcode > 0 sets halted "
            "and prevents further publishes even if slots are available."
        ),
        initial=make_state(
            minions=["m1", "m2", "m3", "m4"],
            batch_size=2,
            failhard=True,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=2.0,
                new_returns={"m1": _ret(retcode=1)},
                expected=Action(
                    publish=[],
                    finished_minions={"m1": _ret(retcode=1)},
                    timed_out_minions=[],
                    halted=True,
                    halted_reason="failhard",
                ),
                state_after={
                    "pending": ["m3", "m4"],
                    "done": {"m1": _ret(retcode=1)},
                    "halted": True,
                    "halted_reason": "failhard",
                },
            ),
        ),
        covers=("test_single_jid_with_failhard",),
    ),
    Scenario(
        name="retcode_dict_collapses_to_max_for_failhard",
        description=(
            "A return whose retcode is itself a dict (one entry per "
            "sub-call) is evaluated by its maximum value.  Max > 0 plus "
            "failhard triggers halt."
        ),
        initial=make_state(
            minions=["m1", "m2"],
            batch_size=2,
            failhard=True,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=2.0,
                new_returns={
                    "m1": {
                        "ret": True,
                        "retcode": {"test.ping": 0, "test.retcode": 42},
                    },
                },
                expected=Action(
                    publish=[],
                    finished_minions={
                        "m1": {
                            "ret": True,
                            "retcode": {"test.ping": 0, "test.retcode": 42},
                        },
                    },
                    timed_out_minions=[],
                    halted=True,
                    halted_reason="failhard",
                ),
                state_after={"halted": True, "halted_reason": "failhard"},
            ),
        ),
        covers=("test_run_retcode_dict_takes_max",),
    ),
    Scenario(
        name="batch_wait_blocks_next_dispatch_until_cooldown_expires",
        description=(
            "batch_wait puts a per-slot cooldown stamp in state['wait'] "
            "when a minion returns.  While the stamp is in the future "
            "the slot is not available, so pending minions stay pending."
        ),
        initial=make_state(
            minions=["m1", "m2", "m3", "m4"],
            batch_size=2,
            batch_wait=30,
        ),
        steps=(
            Step(
                now=0.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=1.0,
                new_returns={"m1": _ret(), "m2": _ret()},
                expected=Action(
                    publish=[],
                    finished_minions={"m1": _ret(), "m2": _ret()},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": ["m3", "m4"],
                    "active": {},
                    "done": {"m1": _ret(), "m2": _ret()},
                    "wait": [31.0, 31.0],
                },
            ),
            Step(
                now=15.0,
                expected=Action(
                    publish=[],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={"pending": ["m3", "m4"], "wait": [31.0, 31.0]},
            ),
            Step(
                now=32.0,
                expected=Action(
                    publish=["m3", "m4"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": [],
                    "active": {"m3": 32.0, "m4": 32.0},
                    "wait": [],
                },
            ),
        ),
        covers=("test_run_batch_wait_delays_next_dispatch",),
    ),
    Scenario(
        name="timeout_moves_nonresponsive_minion_to_failed",
        description=(
            "An active minion whose dispatch timestamp is older than "
            "now - (timeout + gather_job_timeout) is moved from active "
            "to failed with reason 'timeout'."
        ),
        initial=make_state(
            minions=["m1", "m2"],
            batch_size=2,
            timeout=60,
            gather_job_timeout=10,
        ),
        steps=(
            Step(
                now=0.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=100.0,  # 100s elapsed, limit is 70s
                expected=Action(
                    publish=[],
                    finished_minions={},
                    timed_out_minions=["m1", "m2"],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "active": {},
                    "failed": {"m1": "timeout", "m2": "timeout"},
                },
            ),
        ),
    ),
    Scenario(
        name="normal_completion_leaves_halted_false",
        description=(
            "When the last active minion returns and pending is empty, "
            "halted stays False.  The driver detects completion via "
            "is_batch_done(state), not via action.halted."
        ),
        initial=make_state(
            minions=["m1", "m2"],
            batch_size=2,
        ),
        steps=(
            Step(
                now=1.0,
                expected=Action(
                    publish=["m1", "m2"],
                    finished_minions={},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
            ),
            Step(
                now=2.0,
                new_returns={"m1": _ret(), "m2": _ret()},
                expected=Action(
                    publish=[],
                    finished_minions={"m1": _ret(), "m2": _ret()},
                    timed_out_minions=[],
                    halted=False,
                    halted_reason=None,
                ),
                state_after={
                    "pending": [],
                    "active": {},
                    "done": {"m1": _ret(), "m2": _ret()},
                    "halted": False,
                    "halted_reason": None,
                },
            ),
        ),
        covers=("test_single_jid_single_batch",),
    ),
)
