"""
tests.pytests.functional.utils.test_process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's process utility module
"""

import asyncio
import os
import pathlib
import time

import pytest

import salt.utils.process


class Process(salt.utils.process.SignalHandlingProcess):
    def run(self):
        pass


@pytest.fixture
def process_manager():
    _process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        yield _process_manager
    finally:
        _process_manager.terminate()


@pytest.mark.skipif(
    "grains['osfinger'] == 'Rocky Linux-8' and grains['osarch'] == 'aarch64'",
    reason="Temporarily skip on Rocky Linux 8 Arm64",
)
def test_process_manager_60749(process_manager):
    """
    Regression test for issue #60749
    """

    process_manager.add_process(Process)
    process_manager.check_children()


def _get_num_fds(pid):
    "Determine the number of open fds for a process, linux only."
    return len(list(pathlib.Path(f"/proc/{pid}/fd").iterdir()))


@pytest.mark.skip_unless_on_linux
def test_subprocess_list_fds():
    pid = os.getpid()
    process_list = salt.utils.process.SubprocessList()

    before_num = _get_num_fds(pid)

    def target():
        pass

    process = salt.utils.process.SignalHandlingProcess(target=target)
    process.start()

    process_list.add(process)
    time.sleep(0.3)

    num = _get_num_fds(pid)
    assert num == before_num + 2
    start = time.time()
    while time.time() - start < 1:
        process_list.cleanup()
        if not process_list.processes:
            break
    assert len(process_list.processes) == 0
    assert _get_num_fds(pid) == num - 2


async def test_process_manager_run_async():
    """
    Test that ProcessManager.run() is now an async coroutine.
    This tests the conversion from Tornado @gen.coroutine to async/await.
    """
    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        # Verify run() is an async coroutine
        import inspect

        assert inspect.iscoroutinefunction(process_manager.run)

        # Create a task to run the process manager asynchronously
        task = asyncio.create_task(process_manager.run(asynchronous=True))

        # Let it run briefly
        await asyncio.sleep(0.5)

        # Verify the task is running
        assert not task.done()

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        process_manager.terminate()


async def test_process_manager_run_uses_asyncio_sleep():
    """
    Test that ProcessManager.run() uses asyncio.sleep() instead of gen.sleep().
    """
    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        # Start the async run
        task = asyncio.create_task(process_manager.run(asynchronous=True))

        # Wait a bit to ensure it's looping with asyncio.sleep
        await asyncio.sleep(0.1)

        # Verify it's still running (would hang if gen.sleep was used incorrectly)
        assert not task.done()

        # Clean up
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        process_manager.terminate()


def test_process_manager_run_synchronous():
    """
    Test that ProcessManager.run() can still run synchronously.
    """
    process_manager = salt.utils.process.ProcessManager(wait_for_kill=5)
    try:
        # When asynchronous=False, it should use time.sleep and exit quickly
        # since there are no processes
        import threading

        ran = []

        def run_sync():
            # This should complete quickly since there are no processes
            asyncio.run(process_manager.run(asynchronous=False))
            ran.append(True)

        thread = threading.Thread(target=run_sync)
        thread.start()
        thread.join(timeout=2)

        # Should have completed
        assert not thread.is_alive()
        assert ran == [True]
    finally:
        process_manager.terminate()
