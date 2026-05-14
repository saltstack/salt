"""
Regression test for FD leak in job thread event loops (Fix #2).

Bug: salt/minion.py _thread_return() and _thread_multi_return() created
event loops but never closed them, leaking file descriptors.

Fix: Added loop.close() in finally blocks of both functions

This test reproduces the scenario where running multiple queued jobs
(threading mode) would leak FDs because each job thread's event loop
was never closed.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_queued_jobs_threading_mode_no_fd_leak(
    salt_master, salt_minion_factory, salt_client
):
    """
    Regression test: Run multiple queued jobs in threading mode without FD leak.

    Before fix (salt/minion.py):
        def _thread_return(...):
            loop = asyncio.new_event_loop()
            ...
            # BUG: loop.close() never called - leaks FDs

    After fix:
        def _thread_return(...):
            loop = asyncio.new_event_loop()
            try:
                ...
            finally:
                loop.close()  # FIX: Close event loop

    This test specifically uses threading mode (multiprocessing=False) to
    exercise the code path that was leaking.
    """
    import psutil

    # Create minion with threading mode (multiprocessing=False)
    config_overrides = {
        "multiprocessing": False,  # Use threading instead of multiprocessing
    }
    minion = salt_minion_factory.salt_minion_daemon(
        "test-minion-threading",
        overrides=config_overrides,
    )

    with minion.started():
        # Get minion PID
        minion_pid = minion.pid
        if minion_pid is None:
            pytest.skip("Cannot get minion PID")

        try:
            process = psutil.Process(minion_pid)
        except psutil.NoSuchProcess:
            pytest.skip("Minion process not found")

        # Get baseline FD count
        initial_fds = process.num_fds()

        # Run 20 queued jobs - each creates a thread with an event loop
        # Without the fix, each thread leaks ~2-3 FDs
        job_count = 20
        jids = []

        for i in range(job_count):
            jid = salt_client.cmd_async(minion.id, "test.ping", kwarg={"queue": True})
            jids.append(jid)
            time.sleep(0.1)

        # Wait for all jobs to complete
        timeout = 60
        start_wait = time.time()
        completed_count = 0
        seen_jids = set()

        while completed_count < job_count and (time.time() - start_wait) < timeout:
            for jid in jids:
                if jid in seen_jids:
                    continue
                try:
                    ret = salt_client.get_returns(jid, minion.id, timeout=1)
                    if ret:
                        completed_count += 1
                        seen_jids.add(jid)
                except Exception:  # pylint: disable=broad-except
                    pass
            time.sleep(0.5)

        assert (
            completed_count == job_count
        ), f"Only {completed_count}/{job_count} jobs completed"

        # Aggressive garbage collection to clean up Python objects
        import gc

        for _ in range(10):
            gc.collect()
            time.sleep(1)

        # Check final FD count
        final_fds = process.num_fds()
        leaked_fds = final_fds - initial_fds

        # With loop.close(), leak should be minimal (allow ~15 FDs for legitimate usage)
        assert (
            leaked_fds <= 15
        ), f"FD leak detected: {leaked_fds} FDs leaked after {job_count} queued jobs"


def test_single_queued_job_closes_loop(salt_master, salt_minion_factory, salt_client):
    """
    Test that even a single queued job properly closes its event loop.

    This is a minimal test to verify the fix is applied correctly.
    """
    import psutil

    # Create minion with threading mode
    config_overrides = {
        "multiprocessing": False,
    }
    minion = salt_minion_factory.salt_minion_daemon(
        "test-minion-single",
        overrides=config_overrides,
    )

    with minion.started():
        minion_pid = minion.pid
        if minion_pid is None:
            pytest.skip("Cannot get minion PID")

        try:
            process = psutil.Process(minion_pid)
        except psutil.NoSuchProcess:
            pytest.skip("Minion process not found")

        initial_fds = process.num_fds()

        # Run single queued job
        jid = salt_client.cmd_async(minion.id, "test.ping", kwarg={"queue": True})

        # Wait for completion
        timeout = 30
        start_wait = time.time()
        completed = False

        while not completed and (time.time() - start_wait) < timeout:
            try:
                ret = salt_client.get_returns(jid, minion.id, timeout=1)
                if ret:
                    completed = True
            except Exception:  # pylint: disable=broad-except
                pass
            time.sleep(0.5)

        assert completed, "Job did not complete"

        # Aggressive GC
        import gc

        for _ in range(5):
            gc.collect()
            time.sleep(0.5)

        final_fds = process.num_fds()
        leaked_fds = final_fds - initial_fds

        # Single job should have minimal or no leak
        assert leaked_fds <= 5, f"FD leak from single job: {leaked_fds} FDs"
