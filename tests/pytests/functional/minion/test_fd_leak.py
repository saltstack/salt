import os
import shutil
import tempfile

import psutil
import pytest

import salt.config
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.minion


@pytest.mark.skip_unless_on_linux
def test_minion_connection_failure_no_fd_leak():
    """
    Verify that a minion's file descriptors do not grow when it fails to connect to the master.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        opts = salt.config.minion_config(None)
        opts["master"] = "127.0.0.1"
        opts["master_port"] = 12345
        opts["acceptance_wait_time"] = 0.1
        opts["acceptance_wait_time_max"] = 0.1
        opts["random_startup_delay"] = 0
        opts["multimaster"] = False
        opts["request_channel_timeout"] = 1
        opts["auth_timeout"] = 1
        opts["request_channel_tries"] = 1
        opts["auth_tries"] = 1

        opts["pki_dir"] = os.path.join(tmpdir, "pki")
        opts["cachedir"] = os.path.join(tmpdir, "cache")
        opts["sock_dir"] = os.path.join(tmpdir, "sock")
        opts["conf_file"] = os.path.join(tmpdir, "minion")

        os.makedirs(opts["pki_dir"])
        os.makedirs(opts["cachedir"])
        os.makedirs(opts["sock_dir"])

        proc = psutil.Process()

        # Use a local IOLoop for the test
        io_loop = salt.ext.tornado.ioloop.IOLoop()

        # We want to use MinionManager because it has the retry loop
        manager = salt.minion.MinionManager(opts)
        # Ensure MinionManager uses our local io_loop
        manager.io_loop = io_loop

        minion = manager._create_minion_object(
            opts,
            opts["auth_timeout"],
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
            io_loop.close()
    finally:
        shutil.rmtree(tmpdir)
