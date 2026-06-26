"""
tests.pytests.functional.utils.test_process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test salt's process utility module
"""

import os
import pathlib
import subprocess
import sys
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


def test_process_preimports_multiprocessing_connection_68573(tmp_path):
    """
    Regression test for issue #68573.

    multiprocessing.popen_fork.Popen.wait() does a lazy
    ``from multiprocessing.connection import wait`` on first use. When a
    second SIGTERM is delivered during the shutdown path that handler
    re-enters salt.utils.process.ProcessManager.kill_children -> join(0),
    which tries the same import while the module is partially
    initialised, producing::

        ImportError: cannot import name 'wait' from partially initialized
        module 'multiprocessing.connection'

    Importing salt.utils.process must therefore eagerly import
    multiprocessing.connection so the module is fully initialised before
    any signal handler can run.

    Must run in a fresh subprocess: in-process pytest pollutes
    sys.modules with multiprocessing.connection long before this test
    runs.
    """
    # Make the subprocess load the same salt package the test imports.
    # Locally, this might be the editable install in the venv; in CI it is
    # the in-tree code. Both cases work because we explicitly prepend the
    # directory containing the salt package to sys.path.
    salt_module = pathlib.Path(salt.utils.process.__file__).resolve()
    code_dir = salt_module.parent.parent.parent
    script = tmp_path / "check_preimport.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(code_dir)!r})\n"
        "assert 'multiprocessing.connection' not in sys.modules, (\n"
        "    'precondition failed: multiprocessing.connection already imported'\n"
        ")\n"
        "import salt.utils.process  # noqa: F401\n"
        "assert 'multiprocessing.connection' in sys.modules, (\n"
        "    'salt.utils.process must pre-import multiprocessing.connection '\n"
        "    'to avoid a partially-initialised-module ImportError when a '\n"
        "    'reentrant SIGTERM hits Process.join(0); see issue #68573'\n"
        ")\n"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_process_unseeded_logging_options():
    """
    Regression test for issue #68332.
    """

    def target():
        pass

    salt._logging.set_logging_options_dict.__options_dict__ = None
    proc = salt.utils.process.Process(target=target)
    proc.start()
    proc.join()
    assert proc.exitcode == 0
