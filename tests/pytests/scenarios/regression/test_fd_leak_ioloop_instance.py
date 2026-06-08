"""
Regression test for FD leak from auto-created IOLoop instances (Fix #5).

Bug: IOLoop.current() auto-creates a default IOLoop instance if one doesn't exist.
These auto-created IOLoops can leak file descriptors if not properly closed.

Fix: Changed to IOLoop.current(instance=False) in salt/utils/asynchronous.py
current_ioloop() context manager to prevent auto-creation.

This test exercises operations that use the current_ioloop context manager.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_ioloop_no_autocreate_no_leak(salt_master, salt_minion, salt_client):
    """
    Regression test: Operations using current_ioloop don't auto-create IOLoops.

    Before fix (salt/utils/asynchronous.py current_ioloop()):
        orig_loop = tornado.ioloop.IOLoop.current()
        # BUG: Auto-creates default IOLoop if none exists - leaks FDs

    After fix:
        orig_loop = tornado.ioloop.IOLoop.current(instance=False)
        # Returns None instead of auto-creating - prevents leaks

    The current_ioloop context manager is used by SyncWrapper, so any
    operation using SyncWrapper exercises this code path.
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

    # Run many operations that use SyncWrapper (which uses current_ioloop)
    # Each operation could potentially auto-create an IOLoop without the fix
    operation_count = 30
    for i in range(operation_count):
        # Multiple different operations to exercise various SyncWrapper usages
        if i % 3 == 0:
            ret = salt_client.cmd(salt_minion.id, "test.ping")
        elif i % 3 == 1:
            ret = salt_client.cmd(salt_minion.id, "test.version")
        else:
            ret = salt_client.cmd(
                salt_minion.id,
                "event.fire",
                [{"op": i}, f"test/ioloop/{i}"],
            )
        time.sleep(0.05)

    # Aggressive garbage collection
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With instance=False, no auto-created IOLoops leak
    assert (
        leaked_fds <= 15
    ), f"FD leak from IOLoop auto-creation: {leaked_fds} FDs after {operation_count} operations"
