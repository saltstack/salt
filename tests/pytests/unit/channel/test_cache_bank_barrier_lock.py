"""
Unit tests for the NEW-4 barrier lock serialising
``_handle_delegate_cache_write`` (executor-thread) against
``_release_cache_bank_barrier`` / ``_drain_cache_bank_barrier``
(event-loop-thread).

The reviewer corrected the primary's test methodology: the test
MUST exercise ACTUAL concurrency with ``threading.Barrier(2)`` or
similar, NOT a sleep-inside-the-lock pattern (which just serialises
and proves nothing about check-and-act atomicity).

See ``salt/channel/server.py::_handle_delegate_cache_write``,
``_release_cache_bank_barrier``, ``_drain_cache_bank_barrier``,
and the ``_locked`` helper split.
"""

import threading
import time

import pytest

import salt.cache._cluster_replicator as _crep
from salt.channel.server import MasterPubServerChannel
from tests.support.mock import patch


@pytest.fixture
def opts():
    return {"id": "master-A", "cluster_id": "cluster-A"}


def _make_channel(opts):
    ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
    ch.opts = opts
    ch._cache_bank_barriers = {}
    return ch


def test_barrier_lock_is_plain_threading_lock_not_rlock(opts):
    """
    Reviewer correction #4: the lock is a PLAIN ``threading.Lock``,
    not an ``RLock``.  Walking the code: no caller holds the lock
    across a nested acquire; ``_drain_cache_bank_barrier`` snapshots
    under the lock and then calls ``_release_cache_bank_barrier``
    which re-acquires -- that is explicitly NOT re-entrant.
    """
    ch = _make_channel(opts)
    lock = ch._ensure_cache_bank_barrier_lock()
    # Plain Lock lacks ``_is_owned`` / ``_count`` -- RLock has them.
    # Simpler: verify the class name.
    assert (
        type(lock).__name__ == "lock"
    ), f"expected threading.Lock, got {type(lock).__name__}"


def test_check_and_enqueue_atomic_under_concurrent_release(opts):
    """
    Reviewer-mandated actual-concurrency test (``threading.Barrier(2)``).
    Thread A calls ``_handle_delegate_cache_write`` and reaches the
    barrier check; thread B calls ``_release_cache_bank_barrier``
    concurrently.  In both orderings:

    * If A enqueues first: the release drains A's payload and applies
      it via the free-function handler.
    * If B releases first: A's check sees barrier inactive, falls
      through to the free-function handler and applies live.

    NEVER: A's delta is silently dropped.
    """
    ch = _make_channel(opts)
    ch._cache_bank_barriers["sess-1"] = {"grains": []}

    applied = []

    def _fake_handler(_opts, payload):
        applied.append(payload)

    start = threading.Barrier(2)
    thread_a_payload = {"bank": "grains/minion-1", "key": "k", "data": "v"}

    def _thread_a():
        start.wait()
        with patch.object(
            _crep, "_handle_delegate_cache_write", side_effect=_fake_handler
        ):
            # ``patch.object`` inside the thread: the module
            # reference is visible because the server-side import
            # re-imports lazily.
            ch._handle_delegate_cache_write(thread_a_payload)

    def _thread_b():
        start.wait()
        with patch.object(
            _crep, "_handle_delegate_cache_write", side_effect=_fake_handler
        ):
            ch._release_cache_bank_barrier("sess-1", "grains")

    ta = threading.Thread(target=_thread_a)
    tb = threading.Thread(target=_thread_b)
    ta.start()
    tb.start()
    ta.join(timeout=5)
    tb.join(timeout=5)
    assert not ta.is_alive()
    assert not tb.is_alive()

    # Count how many times the free-function handler was invoked
    # with our payload.  In either ordering:
    # - B releases first, A applies live -> 1 call with thread_a_payload.
    # - A enqueues under barrier, B drains -> 1 call with thread_a_payload.
    hits = [p for p in applied if p is thread_a_payload]
    assert len(hits) == 1, f"expected 1 hit, got {len(hits)} (applied={applied!r})"


def test_drain_during_enqueue_does_not_mutate_during_iteration(opts):
    """
    Spin up two threads: one calls ``_queue_cache_bank_delta`` for
    bank=grains/other, the other calls ``_drain_cache_bank_barrier``
    for the whole session.  No ``RuntimeError: dictionary changed
    size during iteration``; the delta either queues (if drain
    hasn't reached that bank's release) or applies live.
    """
    ch = _make_channel(opts)
    ch._cache_bank_barriers["sess-1"] = {f"grains/m{i}": [] for i in range(5)}

    applied = []
    start = threading.Barrier(2)
    delta_payload = {"bank": "grains/m2/subkey", "key": "k", "data": "v"}

    def _fake_handler(_opts, payload):
        applied.append(payload)

    def _enqueue_thread():
        start.wait()
        # Nudge a small delay via time.sleep(0) to give the drain a
        # fighting chance to be mid-iteration when we acquire.
        time.sleep(0)
        with patch.object(
            _crep, "_handle_delegate_cache_write", side_effect=_fake_handler
        ):
            ch._handle_delegate_cache_write(delta_payload)

    def _drain_thread():
        start.wait()
        with patch.object(
            _crep, "_handle_delegate_cache_write", side_effect=_fake_handler
        ):
            ch._drain_cache_bank_barrier("sess-1")

    t1 = threading.Thread(target=_enqueue_thread)
    t2 = threading.Thread(target=_drain_thread)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert not t1.is_alive()
    assert not t2.is_alive()
    # No crash (RuntimeError would have surfaced as thread death
    # with an exception); the payload is applied exactly once.
    hits = [p for p in applied if p is delta_payload]
    assert len(hits) == 1, f"delta_payload applied {len(hits)}x (applied={applied!r})"


def test_locked_variants_assume_lock_held(opts):
    """
    ``_cache_bank_barrier_active_locked`` and
    ``_queue_cache_bank_delta_locked`` do NOT acquire the lock
    themselves; callers must hold it.  A caller that forgets is a
    correctness bug -- this test documents the contract.
    """
    ch = _make_channel(opts)
    ch._cache_bank_barriers["sess-1"] = {"grains": []}
    # The locked variants work when called under the lock -- no-op
    # otherwise but functionally correct on a quiescent dict.
    lock = ch._ensure_cache_bank_barrier_lock()
    with lock:
        assert ch._cache_bank_barrier_active_locked("grains/m1") is True
        ch._queue_cache_bank_delta_locked("grains/m1", {"bank": "grains/m1"})
    assert ch._cache_bank_barriers["sess-1"]["grains"] == [{"bank": "grains/m1"}]


def test_release_runs_handler_outside_lock(opts):
    """
    ``_release_cache_bank_barrier`` snapshots the queue under the
    lock, releases the lock, then replays entries.  Verified here
    by patching the handler to inspect ``lock.locked()`` -- it must
    be False during the replay (otherwise disk/mmap work would
    serialise every executor thread).
    """
    ch = _make_channel(opts)
    ch._cache_bank_barriers["sess-1"] = {"grains": [{"bank": "grains/m1"}]}
    lock = ch._ensure_cache_bank_barrier_lock()

    observed_locked_during_replay = []

    def _handler(_opts, _payload):
        observed_locked_during_replay.append(lock.locked())

    with patch.object(_crep, "_handle_delegate_cache_write", side_effect=_handler):
        ch._release_cache_bank_barrier("sess-1", "grains")

    assert observed_locked_during_replay == [False]


def test_drain_snapshots_under_lock_then_releases(opts):
    """
    ``_drain_cache_bank_barrier`` snapshots the bank list under the
    lock and releases BEFORE looping ``_release_cache_bank_barrier``
    per bank.  If it held the lock across the nested release calls,
    a plain ``threading.Lock`` would deadlock on re-acquire.  The
    test passes iff no deadlock occurs.
    """
    ch = _make_channel(opts)
    ch._cache_bank_barriers["sess-1"] = {f"grains/m{i}": [] for i in range(3)}

    with patch.object(_crep, "_handle_delegate_cache_write", return_value=None):
        # Would deadlock under an unrefactored implementation that
        # held the outer lock across the per-bank release calls.
        ch._drain_cache_bank_barrier("sess-1")

    assert ch._cache_bank_barriers.get("sess-1") is None
