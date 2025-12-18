"""
Test process name behavior with multiprocessing enabled and disabled.
"""


def test_process_name_no_pollution_when_multiprocessing_disabled(
    salt_master_factory,
):
    """
    Test that process names don't accumulate _thread_return strings
    when multiprocessing is disabled (issue #68553).

    When multiprocessing=False, jobs run in threads in the main process.
    This test ensures that the process name doesn't keep appending
    "Minion._thread_return" with each job execution.
    """
    # Create a fresh master for this test
    master = salt_master_factory.salt_master_daemon("test-process-name-master")

    # Create a fresh minion with multiprocessing=False
    minion = master.salt_minion_daemon(
        "test-process-name-minion-no-mp",
        overrides={"multiprocessing": False},
    )

    cli = master.salt_cli()

    with master.started(), minion.started():
        # Execute multiple jobs to ensure the process name doesn't accumulate
        for i in range(3):
            ret = cli.run("test.ping", minion_tgt=minion.id)
            assert ret.returncode == 0
            assert ret.data is True

        # Get the minion's PID directly from the fixture
        minion_pid = minion.pid
        assert minion_pid, "Minion PID not available"

        # Get the process info using the actual PID
        ret = cli.run("ps.proc_info", minion_pid, minion_tgt=minion.id)
        assert ret.returncode == 0, f"Failed to get process info for PID {minion_pid}"

        # Get the process command line
        proc_info = ret.data
        cmdline = " ".join(proc_info.get("cmdline", []))

        # The process name should not contain _thread_return at all
        # when multiprocessing=False, as we skip the appendproctitle call
        assert "_thread_return" not in cmdline, (
            f"Process cmdline should not contain '_thread_return' when "
            f"multiprocessing=False, but got: {cmdline}"
        )

        # Verify the process is a salt-minion process
        assert (
            "salt-minion" in cmdline
            or "salt_minion" in cmdline
            or "cli_salt_minion" in cmdline
        )


def test_process_name_normal_when_multiprocessing_enabled(
    salt_master_factory,
):
    """
    Test that process names work normally when multiprocessing is enabled.

    When multiprocessing=True (default), jobs run in separate processes,
    so the main minion process name should remain clean.
    """
    # Create a fresh master for this test
    master = salt_master_factory.salt_master_daemon("test-process-name-master-mp")

    # Create a fresh minion with multiprocessing=True
    minion = master.salt_minion_daemon(
        "test-process-name-minion-with-mp",
        overrides={"multiprocessing": True},
    )

    cli = master.salt_cli()

    with master.started(), minion.started():
        # Execute a job
        ret = cli.run("test.ping", minion_tgt=minion.id)
        assert ret.returncode == 0
        assert ret.data is True

        # Get the minion's PID directly from the fixture
        minion_pid = minion.pid
        assert minion_pid, "Minion PID not available"

        # Get the process info using the actual PID
        ret = cli.run("ps.proc_info", minion_pid, minion_tgt=minion.id)
        assert ret.returncode == 0, f"Failed to get process info for PID {minion_pid}"

        # Get the process command line
        proc_info = ret.data
        cmdline = " ".join(proc_info.get("cmdline", []))

        # Verify the process is a salt-minion process
        assert (
            "salt-minion" in cmdline
            or "salt_minion" in cmdline
            or "cli_salt_minion" in cmdline
        )

        # The main minion process should NOT accumulate _thread_return when multiprocessing=True
        # because jobs run in separate child processes
        assert "_thread_return" not in cmdline, (
            f"Main process cmdline should not contain '_thread_return' when "
            f"multiprocessing=True, but got: {cmdline}"
        )


def test_process_name_includes_minion_process_manager(
    salt_master_factory,
):
    """
    Test that the process name includes MinionProcessManager.

    This verifies that minion process managers append their name to the
    process title even when running in MainProcess (e.g., with --disable-keepalive).
    """
    # Create a fresh master for this test
    master = salt_master_factory.salt_master_daemon("test-process-name-master-pm")

    # Create a fresh minion
    minion = master.salt_minion_daemon(
        "test-process-name-minion-pm",
    )

    cli = master.salt_cli()

    with master.started(), minion.started():
        # Execute a job to ensure minion is fully running
        ret = cli.run("test.ping", minion_tgt=minion.id)
        assert ret.returncode == 0
        assert ret.data is True

        # Get the minion's PID directly from the fixture
        minion_pid = minion.pid
        assert minion_pid, "Minion PID not available"

        # Get the process info using the actual PID
        ret = cli.run("ps.proc_info", minion_pid, minion_tgt=minion.id)
        assert ret.returncode == 0, f"Failed to get process info for PID {minion_pid}"

        # Get the process command line
        proc_info = ret.data
        cmdline = " ".join(proc_info.get("cmdline", []))

        # The process title should include either MinionProcessManager or MultiMinionProcessManager
        # This validates the fix for minion process managers to append their name
        # even when running in MainProcess
        has_minion_pm = (
            "MinionProcessManager" in cmdline or "MultiMinionProcessManager" in cmdline
        )
        assert has_minion_pm, (
            f"Process cmdline should contain 'MinionProcessManager' or "
            f"'MultiMinionProcessManager', but got: {cmdline}"
        )
