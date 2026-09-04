"""
Regression test for FD leak in fire_event_async (Fix #1).

Bug: salt/utils/event.py:785 called self.pusher.publish(msg) without await,
creating unawaited coroutines that leak file descriptors.

Fix: Changed to await self.pusher.publish(msg)

This test reproduces the scenario where firing many async events would leak FDs.
"""

import time

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


def test_fire_event_async_no_fd_leak(salt_master, salt_minion, salt_client):
    """
    Regression test: Fire many events asynchronously and verify no FD leak.

    Before fix (salt/utils/event.py:785):
        self.pusher.publish(msg)  # NOT awaited - leaks FDs

    After fix:
        await self.pusher.publish(msg)  # Properly awaited

    This test fires 50 events from the minion and verifies FDs don't leak.
    """
    import psutil

    # Get minion PID
    minion_pid = salt_minion.pid
    if minion_pid is None:
        pytest.skip("Cannot get minion PID")

    try:
        process = psutil.Process(minion_pid)
    except psutil.NoSuchProcess:
        pytest.skip("Minion process not found")

    # Get baseline FD count
    initial_fds = process.num_fds()

    # Fire 50 events - this would leak ~50 FDs without the fix
    event_count = 50
    for i in range(event_count):
        # Use test.ping which fires events internally
        ret = salt_client.cmd(salt_minion.id, "test.ping")
        assert ret[salt_minion.id] is True
        time.sleep(0.05)  # Small delay

    # Force garbage collection multiple times
    import gc

    for _ in range(5):
        gc.collect()
        time.sleep(0.5)

    # Check final FD count
    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # With the fix (await), FD leak should be minimal or zero
    # Allow small margin for legitimate resource usage
    assert (
        leaked_fds <= 10
    ), f"FD leak detected: {leaked_fds} FDs leaked after {event_count} events"


def test_fire_custom_events_no_fd_leak(salt_master, salt_minion, salt_client):
    """
    Test that custom event firing doesn't leak FDs.

    This test specifically exercises the event firing path that was leaking.
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

    # Fire custom events - each goes through fire_event_async
    event_count = 30
    for i in range(event_count):
        ret = salt_client.cmd(
            salt_minion.id,
            "event.fire",
            [{"test_data": f"event_{i}"}, f"test/custom/event/{i}"],
        )
        time.sleep(0.05)

    # Aggressive garbage collection
    import gc

    for _ in range(5):
        gc.collect()
        time.sleep(0.5)

    final_fds = process.num_fds()
    leaked_fds = final_fds - initial_fds

    # Should have minimal leak with awaited publish
    assert (
        leaked_fds <= 10
    ), f"FD leak in custom events: {leaked_fds} FDs leaked after {event_count} events"
