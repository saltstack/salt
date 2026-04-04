"""
    tests.pytests.functional.minion.test_fd_leak
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Verify that a minion's file descriptors do not grow when it fails to connect to the master.
"""

import psutil
import pytest

import salt.ext.tornado.gen
import salt.minion


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
    Verify that a minion's file descriptors do not grow when it fails to connect to the master.
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

    async def run_monitoring():
        manager.io_loop.spawn_callback(manager._connect_minion, minion)

        # Wait for initial jump in FDs
        await salt.ext.tornado.gen.sleep(2)
        initial_fds = proc.num_fds()

        # Monitor for a few more cycles
        for i in range(5):
            await salt.ext.tornado.gen.sleep(2)
            current_fds = proc.num_fds()
            # Sawtooth pattern showed +6 every cycle in reproduction
            if current_fds > initial_fds + 5:
                pytest.fail(
                    f"FD leak detected! Iteration {i}: {current_fds} > {initial_fds}"
                )

    try:
        io_loop.run_sync(run_monitoring, timeout=20)
    finally:
        minion.destroy()
