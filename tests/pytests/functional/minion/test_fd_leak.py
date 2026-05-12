"""
    tests.pytests.functional.minion.test_fd_leak
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Verify that a minion's file descriptors do not grow when it fails to connect to the master.
"""

import asyncio

import psutil
import pytest
import tornado.gen

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
    # Populated inside ``run_monitoring`` so ``MinionManager`` is constructed while the
    # pytest IOLoop is running. Otherwise ``MinionManager.__init__`` may create a fresh
    # asyncio loop, schedule ``ProcessManager.run`` on it, and nothing ever drives that
    # loop — leaving pending tasks and unclosed transports at teardown.
    ctx = {}

    async def run_monitoring():
        manager = salt.minion.MinionManager(minion_opts)
        ctx["manager"] = manager
        minion = manager._create_minion_object(
            minion_opts,
            minion_opts["auth_timeout"],
            False,
            io_loop=manager.io_loop,
        )
        ctx["minion"] = minion
        ctx["connect_task"] = asyncio.create_task(manager._connect_minion(minion))

        # Wait for initial jump in FDs
        await tornado.gen.sleep(2)
        initial_fds = proc.num_fds()

        # Monitor for a few more cycles
        for i in range(5):
            await tornado.gen.sleep(2)
            current_fds = proc.num_fds()
            # Sawtooth pattern showed +6 every cycle in reproduction
            if current_fds > initial_fds + 5:
                pytest.fail(
                    f"FD leak detected! Iteration {i}: {current_fds} > {initial_fds}"
                )

    async def _await_cancelled(task):
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.05)

    async def _cancel_stray_loop_tasks():
        """
        ``MinionManager`` / ``AsyncAuth`` schedule ``ProcessManager.run`` and
        ``_authenticate`` with ``create_task``; cancelling ``_connect_minion``
        alone does not cancel those coroutines, which then trip teardown warnings.
        """
        current = asyncio.current_task()
        loop = asyncio.get_running_loop()
        to_cancel = []
        for task in list(asyncio.all_tasks(loop)):
            if task is current:
                continue
            coro = task.get_coro()
            if coro is None:
                continue
            qualname = getattr(coro, "__qualname__", "")
            if qualname.endswith("ProcessManager.run") or qualname.endswith(
                "_authenticate"
            ):
                to_cancel.append(task)
                task.cancel()
        if to_cancel:
            await asyncio.gather(*to_cancel, return_exceptions=True)
        await asyncio.sleep(0.05)

    try:
        io_loop.run_sync(run_monitoring, timeout=20)
    finally:
        connect_task = ctx.get("connect_task")
        if connect_task is not None and not connect_task.done():
            connect_task.cancel()

            async def _drain_connect():
                await _await_cancelled(connect_task)

            try:
                io_loop.run_sync(_drain_connect, timeout=10)
            except Exception:  # pylint: disable=broad-except
                pass
        minion = ctx.get("minion")
        if minion is not None:
            minion.destroy()
        manager = ctx.get("manager")
        if manager is not None:
            manager.process_manager.stop_restarting()
            manager.process_manager.kill_children()
        try:
            io_loop.run_sync(_cancel_stray_loop_tasks, timeout=15)
        except Exception:  # pylint: disable=broad-except
            pass
