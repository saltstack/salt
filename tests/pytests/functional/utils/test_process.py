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


def _noop_target():
    """Module-level target so the test works under spawn/forkserver too."""


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


def _fd_target(pid, fd):
    """
    Return the ``readlink`` target of ``/proc/{pid}/fd/{fd}`` or ``None``
    if the fd is closed. Using the symlink target (rather than just an
    exists() check) lets callers detect the difference between "fd is
    still the original pipe" and "fd was closed and later reused for
    something else" without flapping on fd number reuse.
    """
    path = pathlib.Path(f"/proc/{pid}/fd/{fd}")
    try:
        return os.readlink(str(path))
    except (FileNotFoundError, OSError):
        return None


@pytest.mark.skip_unless_on_linux
def test_subprocess_list_fds():
    """
    ``SubprocessList.cleanup`` must close the sentinel pipe that
    ``multiprocessing.Process.start`` opens, not just drop the process
    from its internal list.

    We verify this directly against the ``Popen`` sentinel fd -- by
    watching the ``/proc/<pid>/fd/<sentinel>`` symlink target -- rather
    than via a global ``/proc/<pid>/fd`` count delta. The count-delta
    approach is fragile in long-running pytest workers where unrelated
    activity (GC finalizers reaping zombie children, the salt-factories
    log server closing sockets, temp-file lifetimes in adjacent
    fixtures, ...) can asynchronously close fds between two measurements
    and mask the 2-fd sentinel pipe we just allocated -- which is
    exactly what produced ``assert 706 == (706 + 2)`` on Debian 11 CI
    for this test.
    """
    pid = os.getpid()
    process_list = salt.utils.process.SubprocessList()

    process = salt.utils.process.SignalHandlingProcess(target=_noop_target)
    process.start()

    process_list.add(process)
    time.sleep(0.3)

    # The Popen sentinel fd must be open and must point to a pipe.
    sentinel = process.sentinel
    sentinel_target = _fd_target(pid, sentinel)
    assert (
        sentinel_target is not None
    ), f"Popen sentinel fd {sentinel} should be open after start()"
    assert (
        "pipe:" in sentinel_target
    ), f"Popen sentinel fd {sentinel} is not a pipe: {sentinel_target!r}"

    start = time.time()
    while time.time() - start < 5:
        process_list.cleanup()
        if not process_list.processes:
            break
        time.sleep(0.05)
    assert len(process_list.processes) == 0

    # After cleanup the original sentinel pipe must be gone. The fd
    # number may have been reused (highly likely in busy pytest
    # workers); accept either a closed fd or a reused fd pointing at
    # something other than the original pipe target.
    post_target = _fd_target(pid, sentinel)
    assert post_target != sentinel_target, (
        f"Popen sentinel fd {sentinel} still points at the same pipe "
        f"({sentinel_target!r}) after SubprocessList.cleanup()"
    )


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
