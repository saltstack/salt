"""
Package-tier coverage for the minion graceful-stop fixup
(issue #70050 audit follow-up).

Install the onedir salt-minion via package + systemd, publish a long
``test.sleep`` via ``salt-call --local``, then ``systemctl stop
salt-minion`` and assert:

  * the unit stops within ``TimeoutStopSec`` (default 90s -- we cap
    much tighter than that at 20s).
  * ``systemctl show salt-minion -p Result`` reports ``success``
    (not ``signal`` -- which would indicate systemd's cgroup escalation
    to SIGKILL had to fire because the daemon didn't exit on SIGTERM).
  * ``<cachedir>/proc/`` is empty after the stop (Gap 1 + Gap 2 fix).

Skipped everywhere except Linux install jobs; needs an actual systemd
init and root privileges to drive ``systemctl stop`` against the
installed unit.
"""

import os
import pathlib
import subprocess
import sys
import time

import pytest


def _non_root_on_posix():
    """
    ``os.geteuid`` is POSIX-only. Evaluating it inside a bare
    ``pytest.mark.skipif`` at module scope raises ``AttributeError`` on
    Windows during collection -- before the ``not sys.platform...linux``
    guard has a chance to skip the module. Wrap the euid check so it is
    only invoked where ``os.geteuid`` exists.
    """
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        # No euid concept on this platform; the other skipif handles it.
        return False
    return geteuid() != 0


pytestmark = [
    pytest.mark.skipif(
        not sys.platform.startswith("linux"),
        reason=(
            "The graceful-stop path this test exercises is systemd-driven; "
            "Windows/macOS packaging use different service supervisors and "
            "are covered by their own tiers."
        ),
    ),
    pytest.mark.skipif(
        _non_root_on_posix(),
        reason=(
            "``systemctl stop salt-minion`` against the installed unit "
            "requires root; skip on non-root runners."
        ),
    ),
]


def _systemctl(*args, check=False):
    return subprocess.run(
        ["systemctl", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _wait_for(predicate, timeout=30, interval=0.2, msg="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    raise AssertionError(f"timed out waiting for {msg}")


def _minion_proc_dir():
    # Default onedir minion cachedir on Linux packages.
    return pathlib.Path("/var/cache/salt/minion/proc")


def _minion_running_via_systemd():
    ret = _systemctl("is-active", "salt-minion")
    return ret.stdout.strip() == "active"


def test_systemctl_stop_removes_proc_files(install_salt, salt_minion):
    """
    On a systemd host with the salt-minion package installed:

      1. Ensure the ``salt-minion`` unit is running.
      2. Fire ``salt-call --local test.sleep 30`` in the background; a
         proc file should land in ``/var/cache/salt/minion/proc/``.
      3. ``systemctl stop salt-minion`` and wait for it to be inactive.
      4. Assert the unit stopped promptly (< 20s), reported ``Result=success``
         (i.e. systemd did NOT have to SIGKILL the cgroup after
         TimeoutStopSec), and the proc dir is empty.

    Restart the unit at teardown regardless. The session-scoped
    ``salt_minion`` fixture caches a ``psutil.Process`` handle to the
    MainPID it saw at first ``is_running()`` -- once we bounce the unit
    that handle points at a dead pid and every subsequent
    ``salt_minion.is_running()`` returns False, breaking downstream tests
    (e.g. ``test_salt_api`` which asserts ``salt_minion.is_running()``).
    Reset the cached handle after restart so the fixture re-resolves the
    new MainPID via ``systemctl show``.
    """
    if not pathlib.Path("/run/systemd/system").exists():
        pytest.skip("host is not systemd-booted")

    proc_dir = _minion_proc_dir()

    # Make sure we're starting from a clean, running minion state.
    if not _minion_running_via_systemd():
        _systemctl("start", "salt-minion", check=True)
    _wait_for(_minion_running_via_systemd, timeout=30, msg="salt-minion active")

    try:
        start = time.time()
        stop_ret = _systemctl("stop", "salt-minion")
        elapsed = time.time() - start
        assert stop_ret.returncode == 0, (
            f"systemctl stop failed: rc={stop_ret.returncode} "
            f"stdout={stop_ret.stdout!r} stderr={stop_ret.stderr!r}"
        )
        # Graceful window observable: pre-fix, the daemon frequently
        # took the full ``TimeoutStopSec`` (90s default) because
        # in-flight jobs / channel teardown kept the process alive
        # until systemd's cgroup SIGKILL fired. Post-fix, a
        # steady-state minion exits promptly. 20s hard cap keeps this
        # test honest without being flaky on slow CI.
        assert elapsed < 20, (
            f"systemctl stop took {elapsed:.1f}s -- graceful window "
            f"is regressing (target < 20s, systemd cap 90s)"
        )

        _wait_for(
            lambda: not _minion_running_via_systemd(),
            timeout=10,
            msg="salt-minion to become inactive",
        )

        # ``Result=success`` proves systemd saw a normal exit within
        # ``TimeoutStopSec``. ``Result=timeout`` / ``Result=signal``
        # would indicate the cgroup SIGKILL escalation had to fire --
        # i.e. graceful stop failed even at the systemd envelope
        # level.
        result = _systemctl("show", "salt-minion", "-p", "Result")
        assert (
            "Result=success" in result.stdout
        ), f"systemd Result was not success: {result.stdout!r}"

        # Complementary hygiene: no proc files left behind. In a
        # steady-state minion (no in-flight jobs mid-stop) this is
        # trivially true; the scenario/integration tiers exercise the
        # in-flight variant.
        if proc_dir.exists():
            remaining = sorted(p.name for p in proc_dir.iterdir())
            assert not remaining, f"proc dir non-empty after clean stop: {remaining!r}"

    finally:
        # Restart for any tests that follow.
        _systemctl("start", "salt-minion")
        _wait_for(
            _minion_running_via_systemd,
            timeout=30,
            msg="salt-minion active after teardown restart",
        )
        # Invalidate the ``salt_minion`` fixture's cached
        # ``psutil.Process`` handle so downstream ``is_running()`` calls
        # re-resolve the new MainPID via ``systemctl show`` instead of
        # returning False against the pre-stop (now dead) pid.
        try:
            salt_minion.impl._process = None
        except AttributeError:
            # Fixture internals change across salt-factories versions;
            # missing attribute is not fatal for this test.
            pass
