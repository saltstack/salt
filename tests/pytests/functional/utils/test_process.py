"""
tests.pytests.functional.utils.test_process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's process utility module
"""

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
