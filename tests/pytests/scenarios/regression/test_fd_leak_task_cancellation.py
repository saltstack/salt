"""
Regression test for FD leak from uncancelled tasks in SyncWrapper (Fix #4).

Bug: SyncWrapper.close() didn't cancel pending asyncio tasks before closing
the event loop, leading to "Task was destroyed but it is pending!" warnings
and file descriptor leaks.

Fix: Added task cancellation, async generator shutdown, and executor shutdown
in salt/utils/asynchronous.py SyncWrapper.close()

This test exercises scenarios that create background tasks and async generators.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_async_operations_task_cancellation_no_leak(
    salt_master, salt_minion, salt_client
):
    """
    Regression test: Async operations with proper task cancellation.

    Before fix (salt/utils/asynchronous.py SyncWrapper.close()):
        io_loop.close(all_fds=True)
        # BUG: Pending tasks not cancelled - leaks FDs and emits warnings

    After fix:
        # Cancel all pending tasks
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending_tasks:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
        # Shutdown async generators
        loop.run_until_complete(loop.shutdown_asyncgens())
        # Shutdown executor
        loop.run_until_complete(loop.shutdown_default_executor())
        io_loop.close(all_fds=True)

    This test uses operations that create async tasks and generators.
    """
    import psutil

    minion_pid = salt_minion.pid
    if minion_pid is None:
        pytest.skip("Cannot get minion PID")

    try:
        process = psutil.Process(minion_pid)
    except psutil.NoSuchProcess:
        pytest.skip("Minion process not found")

    initial_fds = process.num_fds()

    # Run operations that create async tasks/generators
    # State operations involve complex async activity
    operation_count = 25
    for i in range(operation_count):
        # test.sleep creates async operations
        ret = salt_client.cmd(
            salt_minion.id,
            "test.sleep",
            [0.01],  # Very short sleep
        )
        time.sleep(0.05)

    # Aggressive garbage collection to trigger SyncWrapper cleanup
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With comprehensive task cancellation and shutdown, leak should be minimal
    assert (
        leaked_fds <= 15
    ), f"FD leak from pending tasks: {leaked_fds} FDs after {operation_count} operations"
