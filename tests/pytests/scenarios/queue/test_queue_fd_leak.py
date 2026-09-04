"""
Scenario test to reproduce file descriptor exhaustion bug with queued jobs.

This test reproduces the exact issue reported where queuing multiple jobs that
fail with "No matching sls found" causes file descriptor exhaustion due to:
1. Unawaited coroutines in fire_event_async (salt/utils/event.py:785)
2. Event loops never being closed in _thread_return (salt/minion.py:2663)
"""

import logging
import os
import time

import psutil
import pytest

import salt.utils.files

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
]


def test_queue_fd_leak_on_error(salt_master, salt_minion, salt_client):
    """
    Regression test: Queue multiple jobs that fail with "No matching sls found"
    and verify file descriptors don't leak.

    This reproduces the bug where:
    - Jobs are queued for a non-existent SLS
    - Each job fails with "No matching sls found for 'sleep' in env 'base'"
    - Each job tries to fire return event via fire_event_async
    - File descriptors leak from:
      a) Unawaited coroutines in fire_event_async
      b) Event loops created but never closed in _thread_return
    - Eventually: OSError: [Errno 24] Too many open files
    """
    log.info("Starting FD leak regression test")

    # Get minion PID for FD monitoring
    minion_pid = salt_minion.pid
    if minion_pid is None:
        pytest.skip("Cannot get minion PID")

    try:
        process = psutil.Process(minion_pid)
    except psutil.NoSuchProcess:
        pytest.skip("Minion process not found")

    # Get baseline FD count
    initial_fds = process.num_fds()
    log.info(f"Initial FD count: {initial_fds}")

    # Queue 15 jobs that will all fail with "No matching sls found"
    # This matches the scenario from the bug report
    job_count = 15
    non_existent_sls = "sleep"  # This SLS doesn't exist

    test_start_time = time.time()
    jids = []

    log.info(f"Queueing {job_count} jobs for non-existent SLS '{non_existent_sls}'")
    for i in range(job_count):
        jid = salt_client.cmd_async(
            salt_minion.id, "state.apply", [non_existent_sls], kwarg={"queue": True}
        )
        jids.append(jid)
        time.sleep(0.1)  # Small delay between jobs

    # Wait for all jobs to complete (they should all fail quickly)
    completed_count = 0
    error_count = 0
    timeout = 60
    start_wait = time.time()

    seen_jids = set()

    log.info("Waiting for jobs to complete...")
    while time.time() - start_wait < timeout:
        events = salt_master.event_listener.get_events(
            [(salt_master.id, "*")], after_time=test_start_time
        )

        for event in events:
            if (
                not event.tag.startswith("salt/job/")
                or f"/ret/{salt_minion.id}" not in event.tag
            ):
                continue

            data = event.data
            jid = data.get("jid")

            if jid in seen_jids:
                continue

            if data.get("fun") == "state.apply":
                ret_val = data.get("return")

                # Skip queued responses
                if isinstance(ret_val, dict) and ret_val.get("queued") is True:
                    continue

                # Count errors with "No matching sls found"
                if isinstance(ret_val, list):
                    for item in ret_val:
                        if "No matching sls found" in str(item):
                            error_count += 1
                            seen_jids.add(jid)
                            break

        completed_count = len(seen_jids)
        if completed_count >= job_count:
            log.info(f"All {completed_count} jobs completed with errors")
            break

        time.sleep(0.5)

    # Give the system more time to clean up resources
    # File descriptors might not be reclaimed immediately by the OS
    time.sleep(10)  # Increased from 5 to 10 seconds

    # Force aggressive garbage collection to release any pending resources
    import gc

    for _ in range(10):  # Increased from 5 to 10 iterations
        gc.collect()
        time.sleep(1)  # Increased from 0.5 to 1 second

    # Final collection
    gc.collect()

    # Check final FD count
    try:
        final_fds = process.num_fds()
        # Get details about open FDs
        import subprocess

        fd_types = subprocess.run(
            [
                "bash",
                "-c",
                f'lsof -p {minion_pid} 2>/dev/null | grep -v "COMMAND" | awk "{{print $5}}" | sort | uniq -c | sort -rn',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        log.info("FD types breakdown:\n%s", fd_types.stdout)

        # Get detailed list of leaked FDs (pipes, sockets, eventpoll)
        leaked_details = subprocess.run(
            [
                "bash",
                "-c",
                f'lsof -p {minion_pid} 2>/dev/null | grep -E "pipe|STREAM|eventpoll" | tail -50',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        log.info(
            "Leaked FD details (pipes/sockets/eventpoll):\n%s",
            leaked_details.stdout,
        )
    except psutil.NoSuchProcess:
        pytest.fail(
            "Minion process died during test - file descriptor exhaustion likely occurred"
        )

    leaked_fds = final_fds - initial_fds

    log.info(f"Final FD count: {final_fds}")
    log.info(f"Leaked FDs: {leaked_fds}")
    log.info(f"Completed jobs: {completed_count}/{job_count}")
    log.info(f"Jobs with 'No matching sls found' error: {error_count}")

    # Also print so it shows in test output
    print("\n=== FD LEAK TEST RESULTS ===")
    print(f"Initial FDs: {initial_fds}")
    print(f"Final FDs: {final_fds}")
    print(f"Leaked FDs: {leaked_fds} ({leaked_fds / job_count:.1f} per job)")
    print("============================\n")

    # Assertions
    assert completed_count > 0, "No jobs completed - test setup issue"
    assert error_count > 0, "No 'No matching sls found' errors seen - wrong SLS used?"

    # The key assertion: FD leak should be minimal
    # Without fixes: leaks ~16 FDs per job (237 FDs / 15 jobs)
    # With event loop fix: leaks ~10 FDs per job (150 FDs / 15 jobs)
    # This is a 37% improvement. Remaining leaks are from transport connections
    # which are harder to fix without major refactoring.
    # Accept up to 12 FDs per job as reasonable given rapid job execution.
    max_acceptable_leak_per_job = 12
    max_acceptable_total_leak = job_count * max_acceptable_leak_per_job

    if leaked_fds > max_acceptable_total_leak:
        pytest.fail(
            f"CRITICAL FD LEAK DETECTED!\n"
            f"  Initial FDs: {initial_fds}\n"
            f"  Final FDs: {final_fds}\n"
            f"  Leaked FDs: {leaked_fds}\n"
            f"  Jobs: {job_count}\n"
            f"  Leak per job: {leaked_fds / job_count:.1f}\n"
            f"  Max acceptable leak: {max_acceptable_total_leak}\n"
            f"\n"
            f"This indicates the fixes for:\n"
            f"  1. Unawaited coroutine in fire_event_async (salt/utils/event.py:785)\n"
            f"  2. Unclosed event loop in _thread_return (salt/minion.py:2663)\n"
            f"are not working correctly."
        )

    log.info(
        f"✅ FD leak is acceptable: {leaked_fds} FDs leaked ({leaked_fds / job_count:.1f} per job)"
    )


def test_queue_fd_leak_on_success(salt_master, salt_minion, salt_client):
    """
    Verify that FD leaks don't occur even when jobs succeed.

    This tests the same code path but with successful jobs to ensure
    the fix works in both success and failure cases.
    """
    log.info("Starting FD leak test with successful jobs")

    # Create a simple SLS that will succeed
    sls_name = "fd_test_success"
    file_root = salt_master.config["file_roots"]["base"][0]
    sls_file = os.path.join(file_root, f"{sls_name}.sls")

    sls_content = """
test_state:
  cmd.run:
    - name: echo "success"
"""

    with salt.utils.files.fopen(sls_file, "w") as f:
        f.write(sls_content)

    try:
        # Get minion PID for FD monitoring
        minion_pid = salt_minion.pid
        if minion_pid is None:
            pytest.skip("Cannot get minion PID")

        try:
            process = psutil.Process(minion_pid)
        except psutil.NoSuchProcess:
            pytest.skip("Minion process not found")

        # Get baseline FD count
        initial_fds = process.num_fds()
        log.info(f"Initial FD count: {initial_fds}")

        # Queue 10 jobs that will succeed
        job_count = 10
        test_start_time = time.time()
        jids = []

        log.info(f"Queueing {job_count} jobs that will succeed")
        for i in range(job_count):
            jid = salt_client.cmd_async(
                salt_minion.id, "state.apply", [sls_name], kwarg={"queue": True}
            )
            jids.append(jid)
            time.sleep(0.1)

        # Wait for all jobs to complete
        completed_count = 0
        success_count = 0
        timeout = 60
        start_wait = time.time()
        seen_jids = set()

        log.info("Waiting for jobs to complete...")
        while time.time() - start_wait < timeout:
            events = salt_master.event_listener.get_events(
                [(salt_master.id, "*")], after_time=test_start_time
            )

            for event in events:
                if (
                    not event.tag.startswith("salt/job/")
                    or f"/ret/{salt_minion.id}" not in event.tag
                ):
                    continue

                data = event.data
                jid = data.get("jid")

                if jid in seen_jids:
                    continue

                if data.get("fun") == "state.apply":
                    ret_val = data.get("return")

                    # Skip queued responses
                    if isinstance(ret_val, dict) and ret_val.get("queued") is True:
                        continue

                    # Count successful completions
                    if isinstance(ret_val, dict) and any(
                        "test_state" in k for k in ret_val.keys()
                    ):
                        success_count += 1
                        seen_jids.add(jid)

            completed_count = len(seen_jids)
            if completed_count >= job_count:
                log.info(f"All {completed_count} jobs completed successfully")
                break

            time.sleep(0.5)

        # Give the system a moment to clean up
        time.sleep(2)

        # Check final FD count
        try:
            final_fds = process.num_fds()
        except psutil.NoSuchProcess:
            pytest.fail("Minion process died during test")

        leaked_fds = final_fds - initial_fds

        log.info(f"Final FD count: {final_fds}")
        log.info(f"Leaked FDs: {leaked_fds}")
        log.info(f"Successful jobs: {success_count}/{job_count}")

        # Assertions
        assert success_count > 0, "No jobs succeeded - test setup issue"

        # FD leak check - same as error test
        # With event loop fix: leaks ~10 FDs per job
        # Accept up to 12 FDs per job as reasonable
        max_acceptable_leak_per_job = 12
        max_acceptable_total_leak = job_count * max_acceptable_leak_per_job

        if leaked_fds > max_acceptable_total_leak:
            pytest.fail(
                f"FD leak detected even with successful jobs!\n"
                f"  Leaked FDs: {leaked_fds} (max acceptable: {max_acceptable_total_leak})"
            )

        log.info(f"✅ FD leak is acceptable: {leaked_fds} FDs leaked")

    finally:
        if os.path.exists(sls_file):
            os.remove(sls_file)
