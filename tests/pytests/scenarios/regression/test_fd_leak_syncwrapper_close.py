"""
Regression test for FD leak in SyncWrapper close via __getattr__ (Fix #3).

Bug: Calling .close() on SyncWrapper instances through __getattr__ may not
properly trigger event loop cleanup in SyncWrapper.close().

Fix: Explicitly call SyncWrapper.close() instead of relying on __getattr__
in salt/utils/event.py close_pub() and close_pull()

This test reproduces the scenario where event bus cleanup would leak FDs.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_event_bus_cleanup_no_fd_leak(salt_master, salt_minion, salt_client):
    """
    Regression test: Event bus operations with proper SyncWrapper cleanup.

    Before fix (salt/utils/event.py):
        def close_pub(self):
            self.subscriber.close()  # Goes through __getattr__ - may not clean up loop

    After fix:
        def close_pub(self):
            if isinstance(self.subscriber, SyncWrapper):
                SyncWrapper.close(self.subscriber)  # Explicit - ensures cleanup

    This test exercises event bus operations that create/destroy event instances.
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

    # Fire many events - each involves event bus pub/pull operations
    # These operations create SyncWrapper instances that need proper cleanup
    event_count = 40
    for i in range(event_count):
        # Fire custom events which exercise event bus
        ret = salt_client.cmd(
            salt_minion.id,
            "event.fire",
            [{"iteration": i}, f"test/syncwrapper/{i}"],
        )
        time.sleep(0.05)

    # Aggressive garbage collection
    import gc

    for _ in range(10):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With explicit SyncWrapper.close(), leak should be minimal
    assert (
        leaked_fds <= 15
    ), f"FD leak from SyncWrapper cleanup: {leaked_fds} FDs after {event_count} events"
