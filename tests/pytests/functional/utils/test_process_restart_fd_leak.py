"""
tests.pytests.functional.utils.test_process_restart_fd_leak
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regression test for the file-descriptor leak in
``salt.utils.process.ProcessManager.restart_process``.

Every time a supervised subprocess exits (for example the master's
``FileserverUpdate`` process, which exits and is restarted once per
``fileserver_interval`` seconds), ``restart_process`` spawns a fresh
child but never calls ``Process.close()`` on the dead one. The dead
``multiprocessing.popen_fork.Popen`` object holds two pipe fds
(``parent_r`` / ``parent_w``, opened by ``os.pipe()`` in
``Popen._launch``) that are only released when the ``Popen`` is
finalized. Because ``SignalHandlingProcess`` establishes a reference
cycle at construction time (its ``_after_fork_methods`` list captures
the instance itself for ``_setup_signals``), that finalization does
not happen deterministically -- the master accumulates two leaked pipe
fds per restart until it hits ``max_open_files``.

Observed on a running local salt-master container over 24h in Prometheus
(``salt_master_process_fds{process="FileserverUpdate"}``): steady +4 fd
growth per hour aligned with the ``fileserver_interval=3600`` restart
cycle (2 fds leaked in the master parent, inherited by the new child at
fork, plus 2 more allocated for the new child's pipes).

This test drives ``ProcessManager.restart_process()`` directly and
asserts the parent's fd count stays flat across many restarts.
"""

import os
import pathlib
import time

import pytest

import salt.utils.process


class QuickSignalProc(salt.utils.process.SignalHandlingProcess):
    """Short-lived SignalHandlingProcess used to exercise restart_process().

    Uses SignalHandlingProcess (not plain Process) because that is what
    the master actually spawns for FileserverUpdate / Maintenance and it
    is the reference cycle introduced by ``SignalHandlingProcess.__new__``
    that defeats deterministic Popen finalization.
    """

    def run(self):
        # Exit almost immediately -- restart_process() only runs on dead
        # children, so we want each restart to complete quickly.
        time.sleep(0.05)


def _fd_count(pid):
    return len(list(pathlib.Path(f"/proc/{pid}/fd").iterdir()))


def _wait_dead(process, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not process.is_alive():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.skip_unless_on_linux
def test_restart_process_does_not_leak_pipe_fds():
    """
    ``ProcessManager.restart_process`` must not leak the dead child's
    ``multiprocessing.popen_fork.Popen`` pipe fds. Regression test for
    the FileserverUpdate fd leak observed on production masters: ~+2
    pipe fds per restart cycle in the parent, compounded across the
    hourly ``fileserver_interval`` boundary and every other subprocess
    the ProcessManager supervises.
    """
    pid = os.getpid()
    pm = salt.utils.process.ProcessManager(name="TestRestartLeak")
    try:
        process = pm.add_process(QuickSignalProc, name="Short")
        assert _wait_dead(process), "Initial child never exited"

        # Establish a stable baseline after one full fork+exit cycle so
        # any one-shot Popen state (resource_tracker pipe, semaphore
        # tracker sentinel, ...) is already accounted for.
        baseline = _fd_count(pid)

        iterations = 20
        for _ in range(iterations):
            current_pid = process.pid
            pm.restart_process(current_pid)
            # add_process leaves the new process as the sole entry
            new_pid, mapping = next(iter(pm._process_map.items()))
            process = mapping["Process"]
            assert _wait_dead(process), "Restarted child never exited"

        after = _fd_count(pid)
        delta = after - baseline
        # Pre-fix behaviour on Python 3.14: exactly +2 fds per restart
        # (a fresh pipe pair whose parent-side ends stay open in the
        # ProcessManager). Allow a small slack for unrelated fd churn
        # from logging, gc, etc., but anything close to
        # ``2 * iterations`` is the leak.
        assert delta < iterations, (
            f"ProcessManager.restart_process leaked {delta} fds across "
            f"{iterations} restarts (baseline={baseline}, after={after}); "
            f"expected << {iterations}. Each restart is leaking the dead "
            f"child's Popen parent_r/parent_w pipe fds."
        )
    finally:
        pm.terminate()
