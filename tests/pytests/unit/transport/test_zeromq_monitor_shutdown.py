"""
Regression test for ``ZeroMQSocketMonitor.stop()`` leaving its
``consume()`` task pending on event-loop teardown.

Observed on salt-minion SIGTERM::

    Task was destroyed but it is pending!
    task: <Task pending name='...' coro=<ZeroMQSocketMonitor.consume() ...>>

``stop()`` cancelled the consume task but, being a sync call, could not
drive the loop long enough for the cancellation to be delivered.  The
task stayed in the ``cancelling`` state and asyncio printed the
destroy-pending GC warning when the loop was torn down.

After the fix, ``stop()`` sets ``task._log_destroy_pending = False`` on
the cancelled task so the GC warning is suppressed.  The task is still
cancelled; the underlying monitor socket is still closed; only the noisy
user-visible warning on SIGTERM teardown is gone.
"""

import asyncio

import pytest

import salt.transport.zeromq


class _FakeMonitorSocket:
    """Minimal zmq socket stand-in for the monitor path."""

    def __init__(self):
        self._closed = False

    async def poll(self):
        # Never return "ready" -- the consume loop sleeps between polls.
        await asyncio.sleep(0.5)
        return 0

    async def recv_multipart(self):  # pragma: no cover
        raise AssertionError("poll() returns 0; recv_multipart should not run")

    def close(self, *_, **__):
        self._closed = True


class _FakeSocket:
    """Minimal zmq ``Socket`` stand-in for ``ZeroMQSocketMonitor``."""

    def __init__(self):
        self._monitor_socket = _FakeMonitorSocket()
        self.disabled = False

    def get_monitor_socket(self):
        return self._monitor_socket

    def disable_monitor(self):
        self.disabled = True


@pytest.mark.core_test
async def test_stop_suppresses_pending_consume_task_warning():
    """
    ``ZeroMQSocketMonitor.stop()`` must leave the cancelled
    ``consume()`` task in a state that does NOT trigger
    ``Task was destroyed but it is pending!`` on loop teardown.
    """
    socket = _FakeSocket()
    monitor = salt.transport.zeromq.ZeroMQSocketMonitor(socket)

    loop = asyncio.get_running_loop()
    monitor.start_io_loop(loop)
    assert monitor._monitor_task is not None
    task = monitor._monitor_task

    # Yield so the consume task actually starts and awaits poll().
    await asyncio.sleep(0)

    monitor.stop()

    # The task was cancelled synchronously, but the cancellation has
    # not yet been delivered to the coroutine -- this is exactly the
    # window where a loop teardown would surface
    # "Task was destroyed but it is pending!".  The regression contract
    # is that the GC warning is disarmed.
    assert (
        task._log_destroy_pending is False
    ), "stop() must suppress the pending-destroy warning on the consume task"

    # Give asyncio a turn so the cancellation is cleanly delivered for
    # the rest of the test suite.
    await asyncio.sleep(0)
    assert task.cancelled() or task.done()
