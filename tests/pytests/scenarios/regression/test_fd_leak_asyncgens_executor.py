"""
Regression test for FD leak from unclosed async generators and executor (Fix #8).

Bug: SyncWrapper.close() didn't call shutdown_asyncgens() and
shutdown_default_executor() before closing the event loop, causing
ResourceWarning and file descriptor leaks.

Fix: Added shutdown_asyncgens() and shutdown_default_executor() calls
in salt/utils/asynchronous.py SyncWrapper.close() before closing the loop

This test exercises operations that use async generators and the executor.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_async_generators_executor_shutdown_no_leak(
    salt_master, salt_minion, salt_client
):
    """
    Regression test: Async generators and executor are properly shut down.

    Before fix (salt/utils/asynchronous.py SyncWrapper.close()):
        io_loop.close(all_fds=True)
        # BUG: Async generators not shut down - ResourceWarning
        # BUG: Executor not shut down - thread/FD leaks

    After fix:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        io_loop.close(all_fds=True)

    These shutdowns must happen BEFORE closing the loop to properly
    clean up async generators and executor threads.
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

    # Run operations that may use async generators and executor
    # File operations, state operations, and module loading use these features
    operation_count = 30
    for i in range(operation_count):
        # Mix of operations that exercise async features
        if i % 3 == 0:
            # File operations may use async I/O
            ret = salt_client.cmd(
                salt_minion.id,
                "file.file_exists",
                ["/etc/hosts"],
            )
        elif i % 3 == 1:
            # Module listing may use async operations
            ret = salt_client.cmd(salt_minion.id, "sys.list_functions", ["test"])
        else:
            # test.sleep uses async operations
            ret = salt_client.cmd(salt_minion.id, "test.sleep", [0.01])
        time.sleep(0.05)

    # Aggressive garbage collection to trigger SyncWrapper cleanup
    # This is when async generators and executor would leak without proper shutdown
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With shutdown_asyncgens() and shutdown_default_executor(), no leaks
    assert (
        leaked_fds <= 15
    ), f"FD leak from asyncgens/executor: {leaked_fds} FDs after {operation_count} operations"
