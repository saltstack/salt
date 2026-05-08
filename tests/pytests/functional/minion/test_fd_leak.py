"""
    tests.pytests.functional.minion.test_fd_leak
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Integration guard for file-descriptor behavior when a minion repeatedly fails
    to connect to a master (``MinionManager._connect_minion`` retry loop).

    We assert the **process** FD count (via ``psutil.Process().num_fds()`` on Linux)
    does not show patterns consistent with **unbounded growth** from that reconnect
    churn—not that the count never moves. Transport teardown is **asynchronous**
    (e.g. ``destroy_async`` / ``close_async`` yields to the I/O loop), so FDs may
    drop **after** a sample interval. A strict rule like "any sample over baseline
    + N" therefore false-fails on CI: one interval can still include sockets mid-close.

    The failure conditions are intentionally split:

    - **Consecutive rises:** after a settle period, we compare each sample to the
      **previous** sample. Several **back-to-back increases** indicate a staircase
      (the kind of sawtooth leak this test was written for), not a one-tick lag from
      async teardown.

    - **Hard cap vs baseline:** a single sample may not exceed baseline by a large
      margin, so an abrupt large drift still fails without waiting for three steps.

    Constants below encode those thresholds for this module only.
"""

import psutil
import pytest

import salt.ext.tornado.gen
import salt.minion

# Thresholds for the heuristic described in the module docstring.
_FD_LEAK_HARD_CAP_ABOVE_BASELINE = 25
_FD_LEAK_CONSEC_INCREASES_FAIL = 3

_SETTLE_SEC = 2.0
_MONITOR_CYCLES = 5
_CYCLE_SEC = 2.0


@pytest.fixture(scope="module")
def minion_config_overrides(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fd_leak")
    return {
        "master": "127.0.0.1",
        "master_port": 12345,
        "acceptance_wait_time": 0.1,
        "acceptance_wait_time_max": 0.1,
        "random_startup_delay": 0,
        "multimaster": False,
        "request_channel_timeout": 1,
        "auth_timeout": 1,
        "request_channel_tries": 1,
        "auth_tries": 1,
        "pki_dir": str(tmp_path / "pki"),
        "cachedir": str(tmp_path / "cache"),
        "sock_dir": str(tmp_path / "sock"),
        "conf_file": str(tmp_path / "minion"),
    }


@pytest.mark.skip_unless_on_linux
def test_minion_connection_failure_no_fd_leak(io_loop, minion_opts):
    """
    When the master is unreachable, the minion's connect/retry path must not leak
    file descriptors without bound.

    Teardown on that path is **async** (transport ``close_async`` runs on the
    ``IOLoop``). FD counts can therefore **blur** across our 2s sampling windows: a
    benign spike does not imply a leak. We still fail fast on a **clear staircase**
    (several consecutive sample-to-sample increases) or on a **large** jump vs the
    post-settle baseline—strict signals for regression, aligned with asynchronous
    close semantics rather than banning every transient bump.
    """
    proc = psutil.Process()

    # We want to use MinionManager because it has the retry loop
    manager = salt.minion.MinionManager(minion_opts)
    # Ensure MinionManager uses our local io_loop
    manager.io_loop = io_loop

    minion = manager._create_minion_object(
        minion_opts,
        minion_opts["auth_timeout"],
        False,
        io_loop=manager.io_loop,
    )

    timeout = _SETTLE_SEC + _MONITOR_CYCLES * _CYCLE_SEC + 8

    async def run_monitoring():
        manager.io_loop.spawn_callback(manager._connect_minion, minion)

        await salt.ext.tornado.gen.sleep(_SETTLE_SEC)
        initial_fds = proc.num_fds()
        prev_fds = initial_fds
        consecutive_increases = 0

        for i in range(_MONITOR_CYCLES):
            await salt.ext.tornado.gen.sleep(_CYCLE_SEC)
            current_fds = proc.num_fds()

            if current_fds > initial_fds + _FD_LEAK_HARD_CAP_ABOVE_BASELINE:
                pytest.fail(
                    f"FD drift vs baseline exceeded hard cap: iteration {i}: "
                    f"{current_fds} > {initial_fds + _FD_LEAK_HARD_CAP_ABOVE_BASELINE} "
                    f"(baseline {initial_fds}, cap +{_FD_LEAK_HARD_CAP_ABOVE_BASELINE})"
                )

            if current_fds > prev_fds:
                consecutive_increases += 1
            else:
                consecutive_increases = 0

            if consecutive_increases >= _FD_LEAK_CONSEC_INCREASES_FAIL:
                pytest.fail(
                    f"Sustained FD leak (consecutive rises): iteration {i}: "
                    f"{consecutive_increases} consecutive increases, "
                    f"current={current_fds} prev={prev_fds} baseline={initial_fds}"
                )

            prev_fds = current_fds

    try:
        io_loop.run_sync(run_monitoring, timeout=timeout)
    finally:
        minion.destroy()
