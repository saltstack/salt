"""
Functional regression tests for ``salt.utils.files`` lock helpers.
"""

import multiprocessing
import os
import time

import pytest

import salt.exceptions
import salt.utils.files

pytestmark = [
    # POSIX-specific by design: the original #68931 race depends on one
    # process unlink()ing the lock file while another process has it open
    # for stat. Windows blocks that with a sharing violation, so the
    # TOCTOU window the bug exploited does not exist there and the
    # ``wait_lock`` callers in the original traceback (minion queue lock,
    # state.apply) only run on POSIX in practice.
    pytest.mark.skip_on_windows,
]


def _churn_worker(lock_fn, stop_at, results, idx):
    """
    Tight create/remove loop on the lock path. The goal is to keep the path
    flipping between "exists as a regular file" and "missing" so that any
    other process running the pre-check in ``wait_lock`` is highly likely
    to observe ``os.path.exists()=True`` followed by
    ``os.path.isfile()=False``.
    """
    errors = []
    iterations = 0
    open_flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    while time.monotonic() < stop_at:
        try:
            fd = os.open(lock_fn, open_flags)
            os.close(fd)
            os.remove(lock_fn)
            iterations += 1
        except FileExistsError:
            continue
        except FileNotFoundError:
            continue
        except OSError as exc:  # pragma: no cover
            errors.append(f"churn {idx}: {exc!r}")
            break
    results.put(("churn", idx, iterations, errors))


def _wait_lock_worker(lock_fn, stop_at, results, idx):
    """
    Repeatedly try to acquire ``wait_lock`` on the contended path. Any
    "exists and is not a file" failure is recorded for the parent to
    surface.
    """
    errors = []
    iterations = 0
    while time.monotonic() < stop_at:
        try:
            with salt.utils.files.wait_lock(lock_fn, lock_fn=lock_fn, timeout=5):
                pass
            iterations += 1
        except salt.exceptions.FileLockError as exc:
            msg = str(exc)
            if "exists and is not a file" in msg:
                errors.append(f"waiter {idx}: {msg}")
                break
            # Lock contention timeouts or unrelated errors are not what
            # this regression test is asserting about; let the loop
            # continue.
    results.put(("waiter", idx, iterations, errors))


def test_wait_lock_concurrent_acquire_release_does_not_raise_not_a_file(tmp_path):
    """
    Regression test for #68931.

    The pre-check in ``wait_lock`` used to call ``os.path.exists`` followed
    by ``os.path.isfile`` as two separate ``stat`` calls. When a second
    process removed the lock file between those two stats, ``exists()``
    returned True and ``isfile()`` returned False, and the helper raised
    ``FileLockError: lock_fn ... exists and is not a file`` against a path
    that had only ever been a regular file.

    Drive the race with one tight-loop child that churns the lock path
    (create / remove) and two waiters that call ``wait_lock`` on the same
    path. With the old two-stat pre-check the waiters reliably observe
    the "exists and is not a file" failure within the test window; with
    the fix in place they only ever see contention timeouts.
    """
    lock_fn = str(tmp_path / "queue.lock")
    duration = 5.0
    stop_at = time.monotonic() + duration

    ctx = multiprocessing.get_context("fork")
    results = ctx.Queue()
    workers = [
        ctx.Process(target=_churn_worker, args=(lock_fn, stop_at, results, 0)),
        ctx.Process(target=_wait_lock_worker, args=(lock_fn, stop_at, results, 0)),
        ctx.Process(target=_wait_lock_worker, args=(lock_fn, stop_at, results, 1)),
    ]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=duration + 30)
        assert not w.is_alive(), "worker did not exit in time"
        assert w.exitcode == 0, f"worker exited with {w.exitcode}"

    collected = []
    while not results.empty():
        collected.append(results.get_nowait())

    assert len(collected) == len(workers), f"missing worker results: {collected}"

    churn_iters = 0
    all_errors = []
    for role, _idx, iterations, errors in collected:
        if role == "churn":
            churn_iters = iterations
        all_errors.extend(errors)

    assert not all_errors, (
        "wait_lock raised a spurious 'exists and is not a file' error "
        f"during concurrent churn: {all_errors}"
    )
    # Sanity: the churn worker actually flipped the lock path many times.
    # A run that produced no churn iterations would not have meaningfully
    # exercised the TOCTOU window.
    assert churn_iters > 100, (
        f"churn worker only ran {churn_iters} iterations; the test did "
        "not produce enough contention to cover the race"
    )
