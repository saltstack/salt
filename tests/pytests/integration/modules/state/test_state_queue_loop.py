import time
import pytest
import salt.utils.files

@pytest.fixture(scope="module")
def loop_sls(base_env_state_tree_root_dir, tmp_path_factory):
    sls_name = "loop_check"
    sls_dir = base_env_state_tree_root_dir
    sls_file = sls_dir / f"{sls_name}.sls"
    target_path = tmp_path_factory.mktemp("state_queue_loop") / "run_count.txt"

    # Use cmd.run to append to a file so we can count executions
    sls_content = f"""
    loop_check_run:
      cmd.run:
        - name: echo "Ran" >> {target_path}
    """
    with salt.utils.files.fopen(sls_file, "w", encoding="utf-8") as f:
        f.write(sls_content)

    yield sls_name, target_path

def test_state_queue_no_loop(salt_cli, salt_minion, loop_sls):
    """
    Test that state.apply with queue=True does NOT enter an infinite loop
    of re-queueing itself.
    """
    sls_name, target_path = loop_sls

    # Ensure target doesn't exist
    if target_path.exists():
        target_path.unlink()

    # Run state with queue=True
    # Since nothing else is running, it should queue (maybe?) or run immediately.
    # The current implementation queues if it sees ITSELF running (the bug).
    # If fixed, it should run ONCE.
    # Note: If no other job is running, `_check_queue` logic says:
    # "If queue=True... check prior... if none... run immediately (don't queue)".
    # Wait, if it runs immediately, it doesn't use the queue logic?
    #
    # If it runs immediately, `_check_queue` returns None.
    # Then `state.apply` runs.
    #
    # The loop happens when the job is IN THE QUEUE (e.g. because we forced it or blocked it).
    #
    # So we must FORCE it to queue first.
    # We can do this by running a blocking job first.

    # 1. Start blocking job (sleep 5s)
    # 2. Start target job (queue=True) -> Queued.
    # 3. Wait for blocking job to finish.
    # 4. Target job starts.
    # 5. Monitor for multiple executions.

    # Reuse the logic from test_state_queue.py regarding blocking job?
    # Simpler: Just run a background sleep via salt_cli
    
    # Run blocking job
    block_proc = salt_cli.run("cmd.run", "sleep 5", minion_tgt=salt_minion.id, start_timeout=10)
    # (This waits... wait, cmd.run blocks the cli but does it block the minion state run?
    # cmd.run is an execution module. state.apply checks running STATES.
    # Does cmd.run block state.apply? Usually no, unless we check 'running' globally.
    # state.apply checks 'state.*'.
    # So we need a STATE blocking job.
    
    # Create blocking state
    # We can just use cmd.run "sleep 5" inside a state.
    
    start = time.time()
    
    # We'll use fire-and-forget or just threading to start blocking state
    import threading
    import subprocess
    import sys

    def run_blocking():
        cmd = [
            sys.executable,
            salt_cli.script_name,
            "-c",
            str(salt_cli.config_dir),
            salt_minion.id,
            "state.single",
            "cmd.run",
            "name=sleep 5",
        ]
        subprocess.run(cmd, capture_output=True)

    t = threading.Thread(target=run_blocking)
    t.start()

    # Wait for it to be running
    job_running = False
    while time.time() - start < 10:
        ret = salt_cli.run("saltutil.is_running", "state.*", minion_tgt=salt_minion.id)
        if ret.data and isinstance(ret.data, list) and len(ret.data) > 0: # simplified check
             job_running = True
             break
        time.sleep(0.5)
    
    assert job_running, "Blocking state failed to start"

    # Now run our test state with queue=True
    ret = salt_cli.run("state.apply", sls_name, "queue=True", minion_tgt=salt_minion.id)
    
    # It should say queued
    assert "queued" in ret.stdout.lower() or "queued" in str(ret.data).lower()

    # Wait for blocking thread
    t.join()

    # Now wait for execution
    # It should run ONCE.
    # Wait for file to exist
    start_wait = time.time()
    while time.time() - start_wait < 20:
        if target_path.exists():
            break
        time.sleep(0.5)
    
    assert target_path.exists(), "Target state never ran"

    # Now wait a bit more to see if it loops
    time.sleep(5)

    # Check execution count
    content = target_path.read_text().strip().splitlines()
    count = len(content)
    
    assert count == 1, f"State ran {count} times! Infinite loop detected."
