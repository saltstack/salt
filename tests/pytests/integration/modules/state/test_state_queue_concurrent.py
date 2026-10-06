"""
Regression test for state queue concurrent execution bug.

This test verifies that queued jobs execute sequentially, not concurrently.
The bug was caused by using create_task() instead of await in the state queue
processing logic, which caused all queued jobs to execute simultaneously.
"""

import time

import pytest

import salt.utils.files


@pytest.fixture(scope="module")
def counter_sls(base_env_state_tree_root_dir, tmp_path_factory):
    """
    Create an SLS that increments a counter and records timestamps.

    This is used to verify jobs execute sequentially by checking that
    timestamps don't overlap.
    """
    sls_name = "queue_counter"
    sls_dir = base_env_state_tree_root_dir
    sls_file = sls_dir / f"{sls_name}.sls"
    log_file = tmp_path_factory.mktemp("queue_test") / "execution.log"

    # State that:
    # 1. Records START with timestamp
    # 2. Sleeps to make execution time measurable
    # 3. Records END with timestamp
    sls_content = f"""
counter_state:
  cmd.run:
    - name: |
        echo "START:$(date +%s.%N)" >> "{log_file}"
        sleep 0.2
        echo "END:$(date +%s.%N)" >> "{log_file}"
    - shell: /bin/bash
"""

    with salt.utils.files.fopen(sls_file, "w", encoding="utf-8") as f:
        f.write(sls_content)

    yield sls_name, log_file


def test_multiple_queued_states_execute_sequentially(
    salt_cli, salt_minion, counter_sls
):
    """
    Regression test: multiple queued jobs must execute sequentially, not concurrently.

    This verifies the fix for a bug where create_task() caused all queued jobs
    to execute simultaneously instead of one at a time.

    The test:
    1. Queues multiple state.apply commands rapidly
    2. Verifies all jobs execute
    3. Verifies execution times don't overlap (sequential, not concurrent)
    """
    sls_name, log_file = counter_sls

    # Clean up
    if log_file.exists():
        log_file.unlink()

    # Queue 3 jobs rapidly - they should all queue up
    for i in range(3):
        # Use pillar to make each job slightly unique
        salt_cli.run(
            "state.sls",
            sls_name,
            f"pillar={{job_id: {i}}}",
            "queue=True",
            minion_tgt=salt_minion.id,
            _timeout=1,  # Don't wait for completion
        )
        time.sleep(0.05)  # Tiny delay

    # Wait for all jobs to complete
    # Sequential: 3 jobs * 0.2s = 0.6s + overhead
    # Give it plenty of time
    time.sleep(5)

    # Verify the log exists
    assert log_file.exists(), "No jobs executed"

    content = log_file.read_text().strip()
    lines = content.splitlines()

    # Parse execution events
    events = []
    for line in lines:
        if ":" in line:
            event_type, timestamp_str = line.split(":", 1)
            try:
                timestamp = float(timestamp_str)
                events.append((event_type, timestamp))
            except ValueError:
                pass  # Skip malformed lines

    # Count executions
    starts = [e for e in events if e[0] == "START"]
    ends = [e for e in events if e[0] == "END"]

    # All 3 jobs should have executed
    assert len(starts) == 3, f"Expected 3 job starts, got {len(starts)}"
    assert len(ends) == 3, f"Expected 3 job completions, got {len(ends)}"

    # Verify sequential execution: no overlapping time ranges
    # Build ranges of (start_time, end_time)
    ranges = []
    for i, start_event in enumerate(starts):
        if i < len(ends):
            ranges.append((start_event[1], ends[i][1]))

    # Sort by start time
    ranges.sort()

    # Check for overlaps
    for i in range(len(ranges) - 1):
        curr_start, curr_end = ranges[i]
        next_start, next_end = ranges[i + 1]

        # Next job should start AFTER previous job ends (allow 10ms tolerance)
        if next_start < (curr_end - 0.01):
            pytest.fail(
                f"CONCURRENT EXECUTION DETECTED! Job {i} ended at {curr_end:.3f} "
                f"but job {i+1} started at {next_start:.3f}. "
                f"Jobs should execute sequentially with the fix applied."
            )

    print("✓ All 3 jobs executed sequentially without overlap")
